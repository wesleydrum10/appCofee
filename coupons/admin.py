from django.contrib import admin

from .models import Coupon, CouponUsage
from .forms import CouponForm


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    form = CouponForm
    list_display = ["code", "discount_type", "value", "is_active", "starts_at", "expires_at", "usage_limit"]
    list_filter = ["discount_type", "is_active", "starts_at", "expires_at"]
    search_fields = ["code", "description"]


@admin.register(CouponUsage)
class CouponUsageAdmin(admin.ModelAdmin):
    list_display = ["coupon", "user", "order", "discount_amount", "created_at"]
    search_fields = ["coupon__code", "user__email", "order__number"]
    autocomplete_fields = ["coupon", "user", "order"]
