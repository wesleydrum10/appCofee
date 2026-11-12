from .services import CartService


def cart_summary(request):
    try:
        cart = CartService.get_or_create_cart(request)
        summary = CartService.summary(cart)
        return {"cart_item_count": summary["count"], "cart_product_quantities": summary["product_quantities"]}
    except Exception:
        return {"cart_item_count": 0, "cart_product_quantities": {}}
