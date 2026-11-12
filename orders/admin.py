from django.contrib import admin
from django import forms

from .models import Order, OrderItem, OrderItemAddon, OrderStatusHistory
from .services import OrderService


class OrderAdminForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = "__all__"

    def clean_status(self):
        status = self.cleaned_data["status"]
        if self.instance.pk and Order.objects.filter(pk=self.instance.pk, status=Order.Status.CANCELLED).exists() and status != Order.Status.CANCELLED:
            raise forms.ValidationError("Um pedido cancelado não pode ser reaberto.")
        return status


class OrderItemAddonInline(admin.TabularInline):
    model = OrderItemAddon
    extra = 0


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ["product_name", "quantity", "unit_price", "subtotal"]


class OrderStatusHistoryInline(admin.TabularInline):
    model = OrderStatusHistory
    extra = 0
    readonly_fields = ["status", "note", "user", "created_at"]


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    form = OrderAdminForm
    list_display = ["number", "user", "status", "total", "created_at"]
    list_filter = ["status", "created_at"]
    search_fields = ["number", "user__email"]
    autocomplete_fields = ["user", "address", "coupon"]
    inlines = [OrderItemInline, OrderStatusHistoryInline]

    def save_model(self, request, obj, form, change):
        new_status = obj.status
        if change:
            obj.status = Order.objects.get(pk=obj.pk).status
        super().save_model(request, obj, form, change)
        if change and obj.status != new_status:
            updated = OrderService.change_status(obj, new_status, user=request.user)
            obj.status = updated.status
            obj.stock_deducted = updated.stock_deducted


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ["order", "product_name", "quantity", "subtotal"]
    autocomplete_fields = ["order", "product"]
    inlines = [OrderItemAddonInline]
