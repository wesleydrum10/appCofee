from django.contrib import admin

from .models import Payment, PaymentSettings


@admin.register(PaymentSettings)
class PaymentSettingsAdmin(admin.ModelAdmin):
    fields = ["simulation_enabled", "updated_at"]
    readonly_fields = ["updated_at"]

    def has_add_permission(self, request):
        return not PaymentSettings.objects.exists() and super().has_add_permission(request)

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ["order", "method", "status", "amount", "created_at"]
    list_filter = ["method", "status", "created_at"]
    search_fields = ["order__number", "gateway_reference"]
    readonly_fields = ["card_token"]
