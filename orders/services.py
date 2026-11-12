from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction
from django.db.models import F, Sum

from coupons.models import CouponUsage
from coupons.services import CouponService
from payments.models import Payment
from catalog.models import Product
from cart.models import Cart
from cart.services import CartService
from inventory.services import InsufficientStock
from .models import Order, OrderItem, OrderItemAddon, OrderStatusHistory


@dataclass(frozen=True)
class DeliveryQuote:
    fee: Decimal
    estimated_minutes: int
    message: str


class DeliveryProvider:
    def quote(self, postal_code: str) -> DeliveryQuote:
        clean = postal_code.replace("-", "").strip()
        if len(clean) != 8:
            return DeliveryQuote(Decimal("0.00"), 0, "CEP inválido.")
        prefix = int(clean[:2])
        if prefix > 99:
            return DeliveryQuote(Decimal("0.00"), 0, "Endereço fora da área de entrega.")
        return DeliveryQuote(Decimal("8.90"), 45, "Entrega disponível em até 15 km.")


class OrderService:
    @staticmethod
    @transaction.atomic
    def create_order(cart, user, address, payment_method: str, saved_card_id=None) -> Order:
        if not user.is_authenticated:
            raise PermissionError("Faça login para finalizar o pedido.")
        if payment_method not in Payment.Method.values:
            raise ValueError("Escolha uma forma de pagamento válida.")
        card = None
        if payment_method == Payment.Method.CARD:
            try:
                card_id = int(saved_card_id)
                if 0 < card_id <= 9223372036854775807:
                    card = user.saved_cards.select_for_update().usable().filter(pk=card_id).first()
            except (TypeError, ValueError, OverflowError):
                card = None
            if card is None:
                raise ValueError("Cadastre e selecione um cartão válido para continuar.")
        cart = Cart.objects.select_for_update().get(pk=cart.pk)
        cart_items = list(cart.items.select_related("product").prefetch_related("addons__addon"))
        if not cart_items:
            raise ValueError("Seu carrinho está vazio.")
        quantities = {}
        for item in cart_items:
            quantities[item.product_id] = quantities.get(item.product_id, 0) + item.quantity
        stock_deducted = False
        tracked_products = set()
        for product in Product.objects.select_for_update().filter(pk__in=quantities).order_by("pk"):
            quantity = quantities[product.pk]
            CartService.validate_stock(product, quantity)
            if product.stock_quantity is not None:
                if not Product.objects.filter(pk=product.pk, stock_quantity__gte=quantity).update(stock_quantity=F("stock_quantity") - quantity):
                    raise InsufficientStock(f"Estoque insuficiente para {product.name}.")
                stock_deducted = True
                tracked_products.add(product.pk)
        totals = cart.subtotal
        quote = DeliveryProvider().quote(address.postal_code)
        coupon_result = CouponService.validate(cart.coupon.code, user, totals) if cart.coupon else None
        discount = coupon_result.discount if coupon_result and coupon_result.valid else Decimal("0.00")
        order = Order.objects.create(
            user=user,
            address=address,
            postal_code=address.postal_code,
            address_snapshot={
                "street": address.street,
                "number": address.number,
                "district": address.district,
                "city": address.city,
                "state": address.state,
            },
            coupon=cart.coupon if coupon_result and coupon_result.valid else None,
            subtotal=totals,
            discount=discount,
            delivery_fee=quote.fee,
            total=totals - discount + quote.fee,
            estimated_delivery_minutes=quote.estimated_minutes,
            stock_deducted=stock_deducted,
        )
        for cart_item in cart_items:
            order_item = OrderItem.objects.create(
                order=order,
                product=cart_item.product,
                product_name=cart_item.product.name,
                quantity=cart_item.quantity,
                unit_price=cart_item.unit_total,
                subtotal=cart_item.subtotal,
                reserved_stock_quantity=cart_item.quantity if cart_item.product_id in tracked_products else 0,
            )
            OrderItemAddon.objects.bulk_create(
                [
                    OrderItemAddon(
                        order_item=order_item,
                        addon=cart_addon.addon,
                        addon_name=cart_addon.addon.name,
                        price=cart_addon.price,
                    )
                    for cart_addon in cart_item.addons.select_related("addon")
                ]
            )
        OrderStatusHistory.objects.create(order=order, status=order.status, user=user, note="Pedido criado.")
        if order.coupon:
            CouponUsage.objects.create(coupon=order.coupon, user=user, order=order, discount_amount=discount)
        Payment.objects.create(
            order=order, method=payment_method, amount=order.total,
            card_token=card.token if card else "", card_display=card.display_name if card else "",
        )
        cart.items.all().delete()
        cart.coupon = None
        cart.save(update_fields=["coupon", "updated_at"])
        return order

    @staticmethod
    @transaction.atomic
    def change_status(order: Order, status: str, user=None, note: str = "") -> Order:
        order = Order.objects.select_for_update().get(pk=order.pk)
        if status not in Order.Status.values:
            raise ValueError("Situação do pedido inválida.")
        if order.status == status:
            return order
        if order.status == Order.Status.CANCELLED:
            raise ValueError("Um pedido cancelado não pode ser reaberto.")
        if status == Order.Status.CANCELLED and order.stock_deducted:
            for item in order.items.values("product_id").annotate(quantity=Sum("reserved_stock_quantity")).order_by("product_id"):
                Product.objects.filter(pk=item["product_id"], stock_quantity__isnull=False).update(stock_quantity=F("stock_quantity") + item["quantity"])
            order.items.update(reserved_stock_quantity=0)
            order.stock_deducted = False
        order.status = status
        order.save(update_fields=["status", "stock_deducted", "updated_at"])
        OrderStatusHistory.objects.create(order=order, status=status, user=user, note=note)
        return order
