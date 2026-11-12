from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from accounts.models import Address, User
from cart.models import Cart, CartItem
from cart.services import CartService
from catalog.models import Category, Product
from orders.models import Order
from orders.services import OrderService
from payments.models import Payment
from .services import InsufficientStock


class ProductStockTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("stock@example.com", "coffee-stock-test!42")
        self.cart = Cart.objects.create(user=self.user)
        self.category = Category.objects.create(name="Cafés")
        self.product = Product.objects.create(category=self.category, name="Café", price=10, stock_quantity=5, minimum_stock=2)
        self.address = Address.objects.create(user=self.user, recipient_name="Cliente", postal_code="01001-000", street="Rua", number="1", district="Centro", city="São Paulo", state="SP")

    def order(self):
        return OrderService.create_order(self.cart, self.user, self.address, "PIX")

    def test_cart_validates_combined_quantities_of_same_product(self):
        item = CartService.add_product(self.cart, self.product, 3)
        CartService.add_product(self.cart, self.product, 2)
        with self.assertRaises(InsufficientStock):
            CartService.add_product(self.cart, self.product, 1)
        with self.assertRaises(InsufficientStock):
            CartService.update_quantity(item, 4)
        self.assertEqual(CartService.item_count(self.cart), 5)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 5)

    def test_order_deducts_stock_and_cancellation_restores_once(self):
        CartService.add_product(self.cart, self.product, 3)
        CartService.add_product(self.cart, self.product, 2)
        order = self.order()
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 0)
        self.assertFalse(Product.objects.available().filter(pk=self.product.pk).exists())
        self.assertFalse(self.cart.items.exists())
        self.assertTrue(order.stock_deducted)
        self.assertEqual(sum(order.items.values_list("reserved_stock_quantity", flat=True)), 5)
        OrderService.change_status(order, Order.Status.CANCELLED)
        OrderService.change_status(order, Order.Status.CANCELLED)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 5)
        with self.assertRaises(ValueError):
            OrderService.change_status(order, Order.Status.CONFIRMED)

    def test_checkout_revalidates_and_rolls_back_when_stock_changes(self):
        CartService.add_product(self.cart, self.product, 5)
        Product.objects.filter(pk=self.product.pk).update(stock_quantity=1)
        with self.assertRaises(InsufficientStock):
            self.order()
        self.assertFalse(Order.objects.exists())
        self.assertFalse(Payment.objects.exists())
        self.assertEqual(CartService.item_count(self.cart), 5)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 1)
        self.client.force_login(self.user)
        self.assertRedirects(self.client.post(reverse("orders:create"), {"address_id": self.address.pk}), reverse("cart:detail"))

    def test_multiple_products_rollback_all_deductions(self):
        other = Product.objects.create(category=self.category, name="Outro café", price=12, stock_quantity=2)
        CartService.add_product(self.cart, self.product, 3)
        CartService.add_product(self.cart, other, 2)
        Product.objects.filter(pk=other.pk).update(stock_quantity=0)
        with self.assertRaises(InsufficientStock):
            self.order()
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 5)
        self.assertFalse(Order.objects.exists())

    def test_last_unit_cannot_be_sold_twice(self):
        Product.objects.filter(pk=self.product.pk).update(stock_quantity=1)
        other_user = User.objects.create_user("other-stock@example.com", "coffee-stock-test!42")
        other_cart = Cart.objects.create(user=other_user)
        CartService.add_product(self.cart, self.product)
        CartService.add_product(other_cart, self.product)
        self.order()
        with self.assertRaises(InsufficientStock):
            OrderService.create_order(other_cart, other_user, self.address, "PIX")
        self.assertEqual(Order.objects.count(), 1)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 0)

    def test_untracked_and_legacy_orders_do_not_restore_unreserved_stock(self):
        untracked = Product.objects.create(category=self.category, name="Sem controle", price=10)
        CartService.add_product(self.cart, self.product, 2)
        CartService.add_product(self.cart, untracked, 3)
        order = self.order()
        Product.objects.filter(pk=untracked.pk).update(stock_quantity=10)
        OrderService.change_status(order, Order.Status.CANCELLED)
        untracked.refresh_from_db()
        self.assertEqual(untracked.stock_quantity, 10)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 5)
        legacy = Order.objects.create(user=self.user, total=10)
        OrderService.change_status(legacy, Order.Status.CANCELLED)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 5)

    def test_invalid_quantity_and_out_of_stock_requests_are_handled(self):
        self.client.force_login(self.user)
        for quantity in ["6", "invalid", "0", "-1"]:
            response = self.client.post(reverse("cart:add", args=[self.product.pk]), {"quantity": quantity}, HTTP_ACCEPT="application/json")
            self.assertEqual(response.status_code, 400)
            self.assertFalse(response.json()["ok"])
        self.assertFalse(CartItem.objects.exists())

    def test_manager_can_set_stock_and_dashboard_shows_alert(self):
        self.user.role = User.Role.MANAGER
        self.user.save()
        self.client.force_login(self.user)
        data = {"name": self.product.name, "category": self.category.pk, "description": "Café", "price": "10", "stock_quantity": "2", "minimum_stock": "3", "is_active": "on", "is_available": "on"}
        self.assertRedirects(self.client.post(reverse("reports:product_edit", args=[self.product.pk]), data), reverse("reports:products"))
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 2)
        self.assertEqual(self.product.minimum_stock, 3)
        response = self.client.get(reverse("reports:dashboard"))
        self.assertEqual(response.context["low_products"][0], self.product)
        self.assertContains(response, "2 unidades restantes")
        for invalid in ["-1", "1.5"]:
            response = self.client.post(reverse("reports:product_edit", args=[self.product.pk]), {**data, "stock_quantity": invalid})
            self.assertEqual(response.status_code, 200)
            self.assertIn("stock_quantity", response.context["form"].errors)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 2)
