from datetime import timedelta
from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True, blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "categories"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Ingredient(models.Model):
    name = models.CharField(max_length=100, unique=True)
    is_essential = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Allergen(models.Model):
    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(unique=True, blank=True)
    is_highlighted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class ProductQuerySet(models.QuerySet):
    def available(self):
        return self.filter(is_active=True, is_available=True, category__is_active=True).filter(Q(stock_quantity__isnull=True) | Q(stock_quantity__gt=0))


class Product(models.Model):
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products")
    name = models.CharField(max_length=140)
    slug = models.SlugField(unique=True, blank=True)
    description = models.TextField()
    image = models.ImageField(upload_to="products/", blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    nutritional_info = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    is_available = models.BooleanField(default=True)
    stock_quantity = models.PositiveIntegerField("Quantidade em estoque", null=True, blank=True, default=None)
    minimum_stock = models.PositiveIntegerField("Estoque mínimo", default=0)
    ingredients = models.ManyToManyField(Ingredient, through="ProductIngredient", related_name="products")
    allergens = models.ManyToManyField(Allergen, through="ProductAllergen", related_name="products")
    addons = models.ManyToManyField("Addon", through="ProductAddon", related_name="products", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ProductQuerySet.as_manager()

    class Meta:
        ordering = ["category__name", "name"]
        indexes = [models.Index(fields=["slug"]), models.Index(fields=["is_active", "is_available"])]
        constraints = [
            models.CheckConstraint(check=Q(price__gt=0), name="catalog_product_price_positive"),
            models.CheckConstraint(condition=Q(stock_quantity__isnull=True) | Q(stock_quantity__gte=0), name="catalog_stock_non_negative"),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("catalog:product_detail", kwargs={"slug": self.slug})

    @property
    def image_url(self):
        from .images import product_image_url

        return product_image_url(self.image.name)

    @property
    def is_new(self):
        return self.created_at >= timezone.now() - timedelta(days=7)

    def __str__(self):
        return self.name


class ProductIngredient(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    ingredient = models.ForeignKey(Ingredient, on_delete=models.PROTECT)
    quantity = models.CharField(max_length=80, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["product", "ingredient"], name="catalog_unique_product_ingredient")
        ]


class ProductAllergen(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    allergen = models.ForeignKey(Allergen, on_delete=models.PROTECT)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["product", "allergen"], name="catalog_unique_product_allergen")]


class Addon(models.Model):
    class Kind(models.TextChoices):
        TOPPING = "TOPPING", "Cobertura"
        FILLING = "FILLING", "Recheio"
        EXTRA = "EXTRA", "Adicional"

    name = models.CharField(max_length=100)
    kind = models.CharField(max_length=20, choices=Kind.choices)
    price = models.DecimalField(max_digits=8, decimal_places=2, validators=[MinValueValidator(Decimal("0.00"))])
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["kind", "name"]
        constraints = [
            models.UniqueConstraint(fields=["name", "kind"], name="catalog_unique_addon_kind"),
            models.CheckConstraint(check=Q(price__gte=0), name="catalog_addon_price_non_negative"),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_kind_display()})"


class ProductAddon(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    addon = models.ForeignKey(Addon, on_delete=models.PROTECT)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["product", "addon"], name="catalog_unique_product_addon")]
