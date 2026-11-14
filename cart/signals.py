from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver

from .services import CartService


@receiver(user_logged_in, dispatch_uid="cart.merge_guest_cart_on_login")
def merge_guest_cart_on_login(sender, request, user, **kwargs):
    if request is None:
        return
    guest_cart_id = request.session.get(CartService.GUEST_CART_SESSION_KEY)
    if guest_cart_id is not None:
        CartService.merge_guest_cart(user, guest_cart_id)
        request.session.pop(CartService.GUEST_CART_SESSION_KEY, None)
