from decimal import Decimal

from django.db import transaction
from django.db.models import Sum

from catalog.models import Addon, Product
from coupons.services import CouponService
from inventory.services import InsufficientStock
from .models import Cart, CartItem, CartItemAddon


class CartLimitExceeded(Exception):
    pass


class CartService:
    MAX_ITEMS = 50

    @staticmethod
    def get_or_create_cart(request) -> Cart:
        if request.user.is_authenticated:
            cart, _ = Cart.objects.get_or_create(user=request.user)
            return cart
        if not request.session.session_key:
            request.session.create()
        cart, _ = Cart.objects.get_or_create(session_key=request.session.session_key)
        return cart

    @staticmethod
    def item_count(cart: Cart) -> int:
        return sum(cart.items.values_list("quantity", flat=True))

    @staticmethod
    def summary(cart: Cart) -> dict:
        quantities = dict(cart.items.values("product_id").annotate(total=Sum("quantity")).values_list("product_id", "total"))
        return {"count": sum(quantities.values()), "product_quantities": quantities}

    @staticmethod
    @transaction.atomic
    def add_product(cart: Cart, product: Product, quantity: int = 1, addon_ids=None) -> CartItem:
        addon_ids = addon_ids or []
        cart = Cart.objects.select_for_update().get(pk=cart.pk)
        if quantity < 1:
            raise ValueError("Informe uma quantidade maior que zero.")
        product = Product.objects.get(pk=product.pk)
        existing = cart.items.filter(product=product).aggregate(total=Sum("quantity"))["total"] or 0
        CartService.validate_stock(product, existing + quantity)
        if CartService.item_count(cart) + quantity > CartService.MAX_ITEMS:
            raise CartLimitExceeded("O pedido pode ter no máximo 50 itens.")
        item = CartItem.objects.create(cart=cart, product=product, quantity=quantity, unit_price=product.price)
        addons = Addon.objects.filter(pk__in=addon_ids, is_active=True, products=product)
        CartItemAddon.objects.bulk_create([CartItemAddon(cart_item=item, addon=addon, price=addon.price) for addon in addons])
        return item

    @staticmethod
    @transaction.atomic
    def update_quantity(item: CartItem, quantity: int = None, delta: int = None) -> None:
        Cart.objects.select_for_update().get(pk=item.cart_id)
        item = CartItem.objects.get(pk=item.pk)
        if delta is not None:
            if delta not in [-1, 1]:
                raise ValueError("Alteração de quantidade inválida.")
            quantity = item.quantity + delta
        if quantity is None or quantity < 0:
            raise ValueError("Informe uma quantidade válida.")
        if quantity < 1:
            item.delete()
            return
        product = Product.objects.get(pk=item.product_id)
        existing = item.cart.items.filter(product=product).exclude(pk=item.pk).aggregate(total=Sum("quantity"))["total"] or 0
        CartService.validate_stock(product, existing + quantity)
        if CartService.item_count(item.cart) - item.quantity + quantity > CartService.MAX_ITEMS:
            raise CartLimitExceeded("O pedido pode ter no máximo 50 itens.")
        item.quantity = quantity
        item.save(update_fields=["quantity", "updated_at"])

    @staticmethod
    def validate_stock(product, quantity):
        if not product.is_active or not product.is_available or not product.category.is_active:
            raise InsufficientStock(f"{product.name} está indisponível.")
        if product.stock_quantity is not None and quantity > product.stock_quantity:
            raise InsufficientStock(f"Estoque insuficiente para {product.name}. Disponível: {product.stock_quantity} unidades.")

    @staticmethod
    def totals(cart: Cart, user=None) -> dict:
        subtotal = cart.subtotal
        discount = Decimal("0.00")
        coupon_message = ""
        if cart.coupon:
            result = CouponService.validate(cart.coupon.code, user, subtotal)
            discount = result.discount if result.valid else Decimal("0.00")
            coupon_message = result.message
        return {
            "subtotal": subtotal,
            "discount": discount,
            "delivery": Decimal("0.00"),
            "total": max(Decimal("0.00"), subtotal - discount),
            "coupon_message": coupon_message,
        }
