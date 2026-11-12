from uuid import uuid4

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.views.decorators.cache import never_cache
from django.http import JsonResponse
from django.template.loader import render_to_string

from accounts.models import Address
from cart.services import CartService
from inventory.services import InsufficientStock
from payments.models import Payment, PaymentSettings
from payments.services import PAYMENT_MESSAGES
from .models import Order
from .services import DeliveryProvider, OrderService
from .tracking import tracking_context


@login_required
def checkout(request):
    cart = CartService.get_or_create_cart(request)
    items = list(cart.items.select_related("product__category").prefetch_related("addons__addon"))
    addresses = list(request.user.addresses.order_by("-is_default", "id"))
    totals = CartService.totals(cart, request.user)
    delivery_options = []
    for address in addresses:
        quote = DeliveryProvider().quote(address.postal_code)
        delivery_options.append({
            "id": address.pk, "fee": str(quote.fee), "minutes": quote.estimated_minutes,
            "message": quote.message, "total": str(totals["total"] + quote.fee),
        })
    return render(request, "orders/checkout.html", {
        "cart": cart, "items": items, "item_count": sum(item.quantity for item in items),
        "addresses": addresses, "selected_address": addresses[0] if addresses else None,
        "totals": totals, "delivery_options": delivery_options,
        "delivery": delivery_options[0] if delivery_options else None,
        "saved_cards": request.user.saved_cards.usable(),
    })


@login_required
@require_POST
def create(request):
    address = get_object_or_404(Address, pk=request.POST.get("address_id"), user=request.user)
    cart = CartService.get_or_create_cart(request)
    if not cart.items.exists():
        messages.error(request, "Seu carrinho está vazio.")
        return redirect("cart:detail")
    try:
        order = OrderService.create_order(cart, request.user, address, request.POST.get("payment_method", "PIX"), saved_card_id=request.POST.get("saved_card_id"))
    except (InsufficientStock, ValueError) as exc:
        messages.error(request, str(exc))
        return redirect("orders:checkout" if request.POST.get("payment_method") == Payment.Method.CARD else "cart:detail")
    messages.success(request, f"Pedido {order.number} criado.")
    return redirect("orders:detail", number=order.number)


@login_required
def order_list(request):
    orders = request.user.orders.select_related("payment").prefetch_related("items").all()
    return render(request, "orders/list.html", {"orders": orders})


@never_cache
@login_required
def tracking(request, number):
    order = get_object_or_404(request.user.orders.select_related("payment").prefetch_related("history"), number=number)
    if not order.can_track_delivery:
        raise PermissionDenied("O rastreamento ficará disponível após a aprovação do pagamento.")
    return render(request, "orders/tracking.html", tracking_context(order))


@never_cache
@login_required
def tracking_status(request, number):
    order = get_object_or_404(request.user.orders.select_related("payment").prefetch_related("history"), number=number)
    if not order.can_track_delivery:
        return JsonResponse({"message": "O rastreamento ficará disponível após a aprovação do pagamento."}, status=403)
    context = tracking_context(order)
    return JsonResponse({
        "html": render_to_string("orders/_tracking.html", context, request=request),
        "terminal": context["terminal"],
    })


@login_required
def detail(request, number):
    order = get_object_or_404(
        request.user.orders.select_related("payment").prefetch_related("items__addons", "history"),
        number=number,
    )
    payment = getattr(order, "payment", None)
    attempted = payment.attempts.exists() if payment else False
    simulation_enabled = PaymentSettings.current().simulation_enabled
    can_simulate = simulation_enabled and payment and payment.method != Payment.Method.CASH and payment.status in [Payment.Status.PENDING, Payment.Status.DECLINED] and order.status != Order.Status.CANCELLED
    return render(request, "orders/detail.html", {
        "order": order, "can_simulate": can_simulate,
        "auto_simulate": can_simulate and not attempted and not payment.gateway_reference,
        "payment_attempted": attempted, "payment_key": uuid4(),
        "simulation_enabled": simulation_enabled,
        "payment_message": PAYMENT_MESSAGES.get(payment.status, "") if payment and (attempted or payment.status == Payment.Status.APPROVED) else "",
    })
