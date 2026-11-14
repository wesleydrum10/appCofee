from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Address, User
from catalog.models import Addon, Category, Product, ProductAddon
from coupons.models import Coupon
from orders.models import Order
from orders.services import OrderService
from payments.models import Payment
from .models import Cart
from .services import CartService


class GuestCartLoginTests(TestCase):
    def setUp(self):
        self.password = "coffee-test!42"
        self.user = User.objects.create_user(f"{self._testMethodName}@cart.test", self.password)
        category = Category.objects.create(name="Cafés")
        self.product = Product.objects.create(category=category, name="Café", price=10)
        self.addon = Addon.objects.create(name="Calda", kind=Addon.Kind.EXTRA, price=2)
        ProductAddon.objects.create(product=self.product, addon=self.addon)

    def add_guest_items(self, quantity=2):
        response = self.client.post(reverse("cart:add", args=[self.product.pk]), {
            "quantity": quantity, "addons": [self.addon.pk],
        }, HTTP_ACCEPT="application/json")
        self.assertEqual(response.status_code, 200)
        return Cart.objects.get(session_key=self.client.session.session_key)

    def login(self, **data):
        return self.client.post(reverse("accounts:login"), {
            "username": self.user.email, "password": self.password,
            "next": reverse("orders:checkout"), **data,
        })

    def test_checkout_login_rotates_session_and_keeps_quantities_and_addons(self):
        guest = self.add_guest_items()
        item = guest.items.get()
        previous_session = self.client.session.session_key
        response = self.client.get(reverse("orders:checkout"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response.url)
        response = self.login()
        self.assertRedirects(response, reverse("orders:checkout"))
        self.assertNotEqual(self.client.session.session_key, previous_session)
        guest.refresh_from_db()
        self.assertEqual(guest.user, self.user)
        self.assertEqual(guest.session_key, "")
        item.refresh_from_db()
        self.assertEqual(item.quantity, 2)
        self.assertEqual(item.addons.get().addon, self.addon)
        self.assertEqual(guest.subtotal, Decimal("24.00"))
        self.assertNotIn(CartService.GUEST_CART_SESSION_KEY, self.client.session)
        self.assertEqual(self.client.get(reverse("cart:summary")).json()["count"], 2)

    def test_merges_saved_cart_without_replacing_or_duplicating_items(self):
        saved = Cart.objects.create(user=self.user)
        saved_item = CartService.add_product(saved, self.product)
        guest = self.add_guest_items()
        guest_id = guest.pk
        guest_item = guest.items.get()
        self.login()
        guest_item.refresh_from_db()
        self.assertEqual(guest_item.cart, saved)
        self.assertEqual(guest_item.addons.get().price, Decimal("2.00"))
        self.assertTrue(saved.items.filter(pk=saved_item.pk).exists())
        self.assertFalse(Cart.objects.filter(pk=guest_id).exists())
        self.assertEqual(CartService.item_count(saved), 3)
        CartService.merge_guest_cart(self.user, guest_id)
        self.assertEqual(CartService.item_count(saved), 3)

    def test_invalid_login_keeps_anonymous_cart_for_retry(self):
        guest = self.add_guest_items()
        response = self.login(password="wrong-password")
        self.assertEqual(response.status_code, 200)
        guest.refresh_from_db()
        self.assertIsNone(guest.user)
        self.assertEqual(self.client.get(reverse("cart:summary")).json()["count"], 2)
        self.login()
        guest.refresh_from_db()
        self.assertEqual(guest.user, self.user)

    def test_signup_also_keeps_the_guest_cart(self):
        guest = self.add_guest_items()
        response = self.client.post(reverse("accounts:signup"), {
            "first_name": "Cliente", "email": "signup-cart@example.com", "cpf": "529.982.247-25",
            "password1": self.password, "password2": self.password,
        })
        self.assertRedirects(response, reverse("catalog:product_list"))
        guest.refresh_from_db()
        self.assertEqual(guest.user.email, "signup-cart@example.com")
        self.assertEqual(CartService.item_count(guest), 2)

    def test_logout_and_another_account_do_not_receive_previous_account_cart(self):
        guest = self.add_guest_items()
        self.login()
        self.client.post(reverse("accounts:logout"))
        other = User.objects.create_user("other-cart@example.com", self.password)
        self.login(username=other.email)
        self.assertEqual(self.client.get(reverse("cart:summary")).json()["count"], 0)
        guest.refresh_from_db()
        self.assertEqual(guest.user, self.user)
        self.assertEqual(CartService.item_count(guest), 2)
        CartService.merge_guest_cart(other, guest.pk)
        guest.refresh_from_db()
        self.assertEqual(guest.user, self.user)

    def test_keeps_saved_coupon_when_both_carts_have_one(self):
        for existing_coupon in (False, True):
            with self.subTest(existing_coupon=existing_coupon):
                Cart.objects.all().delete()
                self.client.logout()
                coupons = [Coupon.objects.create(
                    code=f"CUPOM-{existing_coupon}-{index}", discount_type=Coupon.DiscountType.PERCENT,
                    value=10, starts_at=timezone.now()-timedelta(days=1),
                    expires_at=timezone.now()+timedelta(days=1),
                ) for index in range(2)]
                saved = Cart.objects.create(user=self.user, coupon=coupons[0] if existing_coupon else None)
                guest = self.add_guest_items()
                guest.coupon = coupons[1]
                guest.save()
                self.login()
                saved.refresh_from_db()
                self.assertEqual(saved.coupon, coupons[0] if existing_coupon else coupons[1])

    def test_merge_preserves_over_limit_items_but_checkout_requires_adjustment(self):
        saved = Cart.objects.create(user=self.user)
        CartService.add_product(saved, self.product, 30)
        guest = self.add_guest_items(30)
        item = guest.items.get()
        self.login()
        self.assertEqual(CartService.item_count(saved), 60)
        address = Address.objects.create(user=self.user, postal_code="01001-000", street="Rua", number="1", city="São Paulo", state="SP")
        with self.assertRaisesMessage(ValueError, "máximo 50 itens"):
            OrderService.create_order(saved, self.user, address, Payment.Method.CASH)
        self.assertFalse(Order.objects.exists())
        self.assertEqual(CartService.item_count(saved), 60)
        item.refresh_from_db()
        CartService.update_quantity(item, 29)
        self.assertEqual(CartService.item_count(saved), 59)
        CartService.update_quantity(item, 20)
        self.assertEqual(CartService.item_count(saved), 50)
