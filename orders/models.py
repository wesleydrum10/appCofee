from decimal import Decimal
from uuid import uuid4

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q


def generate_order_number():
    return f"CAF-{uuid4().hex[:10].upper()}"


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pendente"
        CONFIRMED = "CONFIRMED", "Confirmado"
        PREPARING = "PREPARING", "Preparando"
        READY = "READY", "Pronto"
        DISPATCHED = "DISPATCHED", "Saiu para entrega"
        DELIVERED = "DELIVERED", "Entregue"
        CANCELLED = "CANCELLED", "Cancelado"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="orders")
    number = models.CharField(max_length=20, unique=True, default=generate_order_number)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    address = models.ForeignKey("accounts.Address", null=True, blank=True, on_delete=models.SET_NULL)
    postal_code = models.CharField(max_length=9)
    address_snapshot = models.JSONField(default=dict)
    coupon = models.ForeignKey("coupons.Coupon", null=True, blank=True, on_delete=models.SET_NULL)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    delivery_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    estimated_delivery_minutes = models.PositiveIntegerField(default=45)
    stock_deducted = models.BooleanField(default=False, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["number"]), models.Index(fields=["user", "created_at"])]
        constraints = [
            models.CheckConstraint(check=Q(subtotal__gte=0), name="orders_subtotal_non_negative"),
            models.CheckConstraint(check=Q(discount__gte=0), name="orders_discount_non_negative"),
            models.CheckConstraint(check=Q(delivery_fee__gte=0), name="orders_delivery_fee_non_negative"),
            models.CheckConstraint(check=Q(total__gte=0), name="orders_total_non_negative"),
        ]

    def __str__(self):
        return self.number


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT)
    product_name = models.CharField(max_length=140)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    reserved_stock_quantity = models.PositiveIntegerField(default=0, editable=False)

    class Meta:
        constraints = [
            models.CheckConstraint(check=Q(quantity__gte=1), name="orders_item_quantity_positive"),
            models.CheckConstraint(check=Q(unit_price__gte=0), name="orders_item_unit_price_non_negative"),
        ]


class OrderItemAddon(models.Model):
    order_item = models.ForeignKey(OrderItem, on_delete=models.CASCADE, related_name="addons")
    addon = models.ForeignKey("catalog.Addon", on_delete=models.PROTECT)
    addon_name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=8, decimal_places=2)


class OrderStatusHistory(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="history")
    status = models.CharField(max_length=20, choices=Order.Status.choices)
    payment_status = models.CharField(max_length=20, blank=True)
    note = models.CharField(max_length=180, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    @property
    def event_status(self):
        return self.payment_status or self.status

    @property
    def event_label(self):
        if self.payment_status:
            from payments.models import Payment
            return dict(Payment.Status.choices).get(self.payment_status, self.payment_status)
        return self.get_status_display()
