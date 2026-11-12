from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from catalog.models import Addon, Category, Product, ProductAddon
from coupons.models import Coupon
from .models import Cart
from .services import CartService


class CartQuantityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("quantity@test.com", "coffee-test!42")
        self.client.force_login(self.user)
        self.cart = Cart.objects.create(user=self.user)
        category = Category.objects.create(name="Cafés")
        self.product = Product.objects.create(category=category, name="Café", price=10, stock_quantity=5)
        self.item = CartService.add_product(self.cart, self.product, 2)
        self.url = reverse("cart:update", args=[self.item.pk])

    def update(self, data):
        return self.client.post(self.url, data, HTTP_ACCEPT="application/json")

    def test_plus_minus_manual_quantity_and_removal_return_server_totals(self):
        for data, count in [({"delta": "1"}, 3), ({"delta": "-1"}, 2), ({"quantity": "4"}, 4), ({"remove": "1"}, 0)]:
            response = self.update(data)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.json()["ok"])
            self.assertEqual(response.json()["count"], count)
            self.assertEqual(Decimal(response.json()["totals"]["total"]), Decimal(10 * count))
        self.assertFalse(self.cart.items.exists())

    def test_decreasing_last_unit_removes_item_and_html_fallback_redirects(self):
        CartService.update_quantity(self.item, 1)
        response = self.client.post(self.url, {"delta": "-1"})
        self.assertRedirects(response, reverse("cart:detail"))
        self.assertFalse(self.cart.items.exists())

    def test_stock_validation_restores_authoritative_quantity(self):
        for data in [{"quantity": "6"}, {"quantity": "invalid"}, {"delta": "2"}, {"quantity": "-1"}]:
            response = self.update(data)
            self.assertEqual(response.status_code, 400)
            self.assertFalse(response.json()["ok"])
            self.assertEqual(response.json()["items"][0]["quantity"], 2)
            self.assertEqual(Decimal(response.json()["totals"]["total"]), Decimal("20"))

    def test_totals_include_addons_and_coupon_after_quantity_changes(self):
        addon = Addon.objects.create(name="Extra", kind=Addon.Kind.EXTRA, price=2)
        ProductAddon.objects.create(product=self.product, addon=addon)
        self.item.delete()
        self.item = CartService.add_product(self.cart, self.product, 1, [addon.pk])
        self.url = reverse("cart:update", args=[self.item.pk])
        self.cart.coupon = Coupon.objects.create(code="DESCONTO", discount_type=Coupon.DiscountType.PERCENT, value=10, minimum_order_value=20, starts_at=timezone.now()-timedelta(days=1), expires_at=timezone.now()+timedelta(days=1))
        self.cart.save()
        response = self.update({"delta": "1"})
        totals = response.json()["totals"]
        self.assertEqual(Decimal(totals["subtotal"]), Decimal("24"))
        self.assertEqual(Decimal(totals["discount"]), Decimal("2.40"))
        self.assertEqual(Decimal(totals["total"]), Decimal("21.60"))

    def test_other_users_cannot_update_cart_items(self):
        other = User.objects.create_user("other-quantity@test.com", "coffee-test!42")
        self.client.force_login(other)
        self.assertEqual(self.update({"delta": "1"}).status_code, 404)
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, 2)
