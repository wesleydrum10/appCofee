from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone


class Coupon(models.Model):
    class DiscountType(models.TextChoices):
        FIXED = "FIXED", "Valor fixo"
        PERCENT = "PERCENT", "Percentual"

    code = models.CharField(max_length=30, unique=True)
    description = models.CharField(max_length=180, blank=True)
    discount_type = models.CharField(max_length=10, choices=DiscountType.choices)
    value = models.DecimalField(max_digits=8, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    minimum_order_value = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    starts_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    usage_limit = models.PositiveIntegerField(null=True, blank=True)
    usage_limit_per_user = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["code"]
        constraints = [
            models.CheckConstraint(check=Q(value__gt=0), name="coupons_value_positive"),
            models.CheckConstraint(check=Q(minimum_order_value__gte=0), name="coupons_minimum_non_negative"),
        ]

    def __str__(self):
        return self.code

    def is_valid_now(self):
        now = timezone.now()
        return self.is_active and self.starts_at <= now <= self.expires_at


class CouponUsage(models.Model):
    coupon = models.ForeignKey(Coupon, on_delete=models.PROTECT, related_name="usages")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="coupon_usages")
    order = models.ForeignKey("orders.Order", null=True, blank=True, on_delete=models.SET_NULL, related_name="coupon_usages")
    discount_amount = models.DecimalField(max_digits=8, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
