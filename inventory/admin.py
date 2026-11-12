from django.contrib import admin

from .models import InventoryItem, InventoryMovement


@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    list_display = ["ingredient", "sku", "quantity_on_hand", "unit", "minimum_quantity"]
    search_fields = ["ingredient__name", "sku"]
    autocomplete_fields = ["ingredient"]


@admin.register(InventoryMovement)
class InventoryMovementAdmin(admin.ModelAdmin):
    list_display = ["item", "movement_type", "quantity", "user", "created_at"]
    list_filter = ["movement_type", "created_at"]
    search_fields = ["item__ingredient__name", "note"]
    autocomplete_fields = ["item", "user"]
