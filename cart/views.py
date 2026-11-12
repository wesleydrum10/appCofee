from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.cache import never_cache
from django.utils.http import url_has_allowed_host_and_scheme

from catalog.models import Product
from coupons.services import CouponService
from inventory.services import InsufficientStock
from .models import CartItem
from .services import CartLimitExceeded, CartService


def detail(request):
    cart = CartService.get_or_create_cart(request)
    totals = CartService.totals(cart, request.user)
    return render(request, "cart/detail.html", {"cart": cart, "totals": totals})


@never_cache
@require_GET
def summary(request):
    return JsonResponse(CartService.summary(CartService.get_or_create_cart(request)))


@require_POST
def add(request, product_id):
    cart = CartService.get_or_create_cart(request)
    product = get_object_or_404(Product, pk=product_id)
    addon_ids = request.POST.getlist("addons")
    try:
        quantity = int(request.POST.get("quantity", 1))
        CartService.add_product(cart, product, quantity, addon_ids)
        message = "Produto adicionado ao carrinho."
        if request.headers.get("accept") == "application/json":
            return JsonResponse({"ok": True, "message": message, **CartService.summary(cart)})
        messages.success(request, message)
    except (CartLimitExceeded, InsufficientStock, ValueError) as exc:
        if request.headers.get("accept") == "application/json":
            return JsonResponse({"ok": False, "message": str(exc)}, status=400)
        messages.error(request, str(exc))
    next_url = request.POST.get("next", "")
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return redirect(next_url)
    return redirect("catalog:product_list")


@require_POST
def update(request, item_id):
    cart = CartService.get_or_create_cart(request)
    item = get_object_or_404(CartItem, pk=item_id, cart=cart)
    error = None
    try:
        if request.POST.get("remove") == "1":
            CartService.update_quantity(item, 0)
        elif "delta" in request.POST:
            CartService.update_quantity(item, delta=int(request.POST["delta"]))
        else:
            CartService.update_quantity(item, int(request.POST.get("quantity", 1)))
    except (CartLimitExceeded, InsufficientStock, ValueError) as exc:
        error = str(exc)
    if request.headers.get("accept") == "application/json":
        items = list(cart.items.select_related("product").prefetch_related("addons"))
        totals = CartService.totals(cart, request.user)
        return JsonResponse({
            "ok": error is None, "message": error or "Sacola atualizada.",
            "count": sum(item.quantity for item in items),
            "items": [{"id": item.pk, "quantity": item.quantity, "subtotal": str(item.subtotal)} for item in items],
            "totals": {key: str(value) for key, value in totals.items()},
        }, status=400 if error else 200)
    if error:
        messages.error(request, error)
    return redirect("cart:detail")


@require_POST
def apply_coupon(request):
    cart = CartService.get_or_create_cart(request)
    result = CouponService.validate(request.POST.get("code", ""), request.user, cart.subtotal)
    if result.valid:
        cart.coupon = result.coupon
        cart.save(update_fields=["coupon", "updated_at"])
        messages.success(request, result.message)
    else:
        messages.error(request, result.message)
    return redirect("cart:detail")


@require_POST
def clear(request):
    CartService.get_or_create_cart(request).items.all().delete()
    messages.success(request, "Carrinho esvaziado.")
    return redirect("cart:detail")
