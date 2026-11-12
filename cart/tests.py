from datetime import timedelta
from decimal import Decimal

from django.test import Client, TestCase
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

    def test_add_json_counts_repeated_products_and_keeps_stock_validation(self):
        url = reverse("cart:add", args=[self.product.pk])
        response = self.client.post(url, {"quantity": 2}, HTTP_ACCEPT="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 4)
        self.assertEqual(response.json()["product_quantities"], {str(self.product.pk): 4})
        response = self.client.post(url, {"quantity": 2}, HTTP_ACCEPT="application/json")
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["ok"])
        self.assertEqual(CartService.item_count(self.cart), 4)

    def test_summary_groups_customized_items_and_is_private(self):
        addon = Addon.objects.create(name="Calda", kind=Addon.Kind.EXTRA, price=2)
        ProductAddon.objects.create(product=self.product, addon=addon)
        CartService.add_product(self.cart, self.product, 1, [addon.pk])
        response = self.client.get(reverse("cart:summary"))
        self.assertEqual(response.json(), {"count": 3, "product_quantities": {str(self.product.pk): 3}})
        self.assertIn("no-store", response.headers["Cache-Control"])
        guest = Client()
        self.assertEqual(guest.get(reverse("cart:summary")).json(), {"count": 0, "product_quantities": {}})
        other = User.objects.create_user("summary-other@test.com")
        self.client.force_login(other)
        self.assertEqual(self.client.get(reverse("cart:summary")).json()["count"], 0)

    def test_cards_show_saved_quantity_on_home_catalog_and_product_detail(self):
        for url in [reverse("core:home"), reverse("catalog:product_list"), self.product.get_absolute_url()]:
            response = self.client.get(url)
            self.assertContains(response, 'data-product-cart-quantity>2</strong>')
            self.assertContains(response, "data-cart-add")
            self.assertEqual(response.context["cart_product_quantities"], {self.product.pk: 2})
        CartService.update_quantity(self.item, 0)
        response = self.client.get(reverse("catalog:product_list"))
        self.assertNotContains(response, 'data-in-cart="true"')

    def test_html_add_returns_to_origin_instead_of_cart_and_rejects_external_redirect(self):
        url = reverse("cart:add", args=[self.product.pk])
        origin = reverse("catalog:product_list") + "?q=Café"
        response = self.client.post(url, {"next": origin})
        self.assertRedirects(response, origin)
        response = self.client.post(url, {"next": "https://example.com/"})
        self.assertRedirects(response, reverse("catalog:product_list"))

    def test_anonymous_addition_persists_with_session_and_updates_second_product(self):
        guest = Client()
        url = reverse("cart:add", args=[self.product.pk])
        response = guest.post(url, {}, HTTP_ACCEPT="application/json")
        self.assertEqual(response.json()["count"], 1)
        second = Product.objects.create(category=self.product.category, name="Cookie", price=9)
        response = guest.post(reverse("cart:add", args=[second.pk]), {"quantity": 2}, HTTP_ACCEPT="application/json")
        self.assertEqual(response.json()["count"], 3)
        self.assertEqual(response.json()["product_quantities"], {str(self.product.pk): 1, str(second.pk): 2})
        self.assertEqual(guest.get(reverse("cart:summary")).json()["count"], 3)
        self.assertEqual(CartService.item_count(self.cart), 2)
