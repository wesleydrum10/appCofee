from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q


class Cart(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE, related_name="cart")
    session_key = models.CharField(max_length=40, blank=True, db_index=True)
    coupon = models.ForeignKey("coupons.Coupon", null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["session_key"], condition=~Q(session_key=""), name="cart_unique_session")
        ]

    def __str__(self):
        return f"Carrinho #{self.pk}"

    @property
    def subtotal(self):
        return sum((item.subtotal for item in self.items.select_related("product").prefetch_related("addons")), Decimal("0.00"))


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]
        constraints = [
            models.CheckConstraint(check=Q(quantity__gte=1), name="cart_item_quantity_positive"),
            models.CheckConstraint(check=Q(unit_price__gte=0), name="cart_item_unit_price_non_negative"),
        ]

    @property
    def addons_total(self):
        return sum((addon.price for addon in self.addons.all()), Decimal("0.00"))

    @property
    def unit_total(self):
        return self.unit_price + self.addons_total

    @property
    def subtotal(self):
        return self.unit_total * self.quantity


class CartItemAddon(models.Model):
    cart_item = models.ForeignKey(CartItem, on_delete=models.CASCADE, related_name="addons")
    addon = models.ForeignKey("catalog.Addon", on_delete=models.PROTECT)
    price = models.DecimalField(max_digits=8, decimal_places=2)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["cart_item", "addon"], name="cart_unique_item_addon")]
