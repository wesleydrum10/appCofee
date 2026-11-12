from decimal import Decimal

from django.db import transaction

from catalog.models import Product
from .models import InventoryItem, InventoryMovement


class InsufficientStock(Exception):
    pass


class InventoryService:
    @staticmethod
    def product_is_available(product: Product) -> bool:
        if not product.is_active or not product.is_available or (product.stock_quantity is not None and product.stock_quantity < 1):
            return False
        essential = product.ingredients.filter(is_essential=True).select_related("inventory_item")
        return all(
            hasattr(ingredient, "inventory_item") and ingredient.inventory_item.quantity_on_hand > 0
            for ingredient in essential
        )

    @staticmethod
    @transaction.atomic
    def register_movement(item: InventoryItem, movement_type: str, quantity: Decimal, user=None, note: str = ""):
        locked = InventoryItem.objects.select_for_update().get(pk=item.pk)
        if movement_type == InventoryMovement.Type.IN:
            locked.quantity_on_hand += quantity
        elif movement_type == InventoryMovement.Type.OUT:
            if locked.quantity_on_hand < quantity:
                raise InsufficientStock("Estoque insuficiente para saída.")
            locked.quantity_on_hand -= quantity
        else:
            locked.quantity_on_hand = quantity
        locked.save(update_fields=["quantity_on_hand", "updated_at"])
        return InventoryMovement.objects.create(
            item=locked,
            movement_type=movement_type,
            quantity=quantity,
            user=user,
            note=note,
        )
