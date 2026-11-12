from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q


class InventoryItem(models.Model):
    ingredient = models.OneToOneField("catalog.Ingredient", on_delete=models.PROTECT, related_name="inventory_item")
    sku = models.CharField(max_length=40, unique=True)
    unit = models.CharField(max_length=20, default="un")
    quantity_on_hand = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    minimum_quantity = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["ingredient__name"]
        constraints = [
            models.CheckConstraint(check=Q(quantity_on_hand__gte=0), name="inventory_quantity_non_negative"),
            models.CheckConstraint(check=Q(minimum_quantity__gte=0), name="inventory_min_quantity_non_negative"),
        ]

    def __str__(self):
        return f"{self.ingredient} ({self.quantity_on_hand} {self.unit})"


class InventoryMovement(models.Model):
    class Type(models.TextChoices):
        IN = "IN", "Entrada"
        OUT = "OUT", "Saída"
        ADJUST = "ADJUST", "Ajuste"

    item = models.ForeignKey(InventoryItem, on_delete=models.PROTECT, related_name="movements")
    movement_type = models.CharField(max_length=10, choices=Type.choices)
    quantity = models.DecimalField(max_digits=10, decimal_places=3, validators=[MinValueValidator(Decimal("0.001"))])
    note = models.CharField(max_length=180, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_movement_type_display()} {self.quantity} {self.item.unit}"
