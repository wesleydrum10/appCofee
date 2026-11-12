from .services import CartService


def cart_summary(request):
    try:
        cart = CartService.get_or_create_cart(request)
        return {"cart_item_count": CartService.item_count(cart)}
    except Exception:
        return {"cart_item_count": 0}
