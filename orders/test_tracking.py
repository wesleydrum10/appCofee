from datetime import timedelta

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from catalog.models import Category, Product
from payments.models import Payment
from .models import Order, OrderItem, OrderStatusHistory
from .tracking import tracking_context


class DeliveryTrackingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.customer = User.objects.create_user(email="delivery@example.com")
        cls.other = User.objects.create_user(email="other-delivery@example.com")
        cls.manager = User.objects.create_user(email="manager-delivery@example.com", role=User.Role.MANAGER)
        cls.staff = User.objects.create_user(email="staff-delivery@example.com", role=User.Role.STAFF, is_staff=True)

    def setUp(self):
        self.order = Order.objects.create(user=self.customer, postal_code="01001-000", address_snapshot={
            "street": "Rua Privada", "number": "123", "district": "Centro", "city": "São Paulo", "state": "SP",
        })
        OrderStatusHistory.objects.create(order=self.order, status=self.order.status, note="Pedido criado.")
        self.url = reverse("orders:tracking", args=[self.order.number])
        self.api = reverse("orders:tracking_status", args=[self.order.number])
        self.manage = reverse("reports:order_delivery", args=[self.order.number])

    def test_tracking_requires_login_and_only_owner_can_read(self):
        for url in [self.url, self.api]:
            self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.other)
        for url in [self.url, self.api]:
            self.assertEqual(self.client.get(url).status_code, 404)
        self.client.force_login(self.customer)
        response = self.client.get(self.url)
        self.assertContains(response, "Rua Privada")
        self.assertContains(response, "Rastrear entrega")
        self.assertIn("no-store", response.headers["Cache-Control"])
        response = self.client.get(self.api)
        self.assertFalse(response.json()["terminal"])
        self.assertIn("Pedido recebido", response.json()["html"])
        self.assertIn("no-store", response.headers["Cache-Control"])

    def test_customer_and_staff_cannot_manage_even_with_post(self):
        for user in [self.customer, self.staff]:
            self.client.force_login(user)
            self.assertEqual(self.client.get(self.manage).status_code, 403)
            self.assertEqual(self.client.post(self.manage, {"status": "DISPATCHED", "expected_status": "PENDING"}).status_code, 403)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PENDING)

    def test_manager_advances_all_stages_and_customer_sees_updates(self):
        self.client.force_login(self.manager)
        self.assertContains(self.client.get(reverse("reports:orders")), self.manage)
        previous = Order.Status.PENDING
        for status in ["CONFIRMED", "PREPARING", "READY", "DISPATCHED", "DELIVERED"]:
            response = self.client.post(self.manage, {
                "expected_status": previous, "status": status, "note": f"Atualização {status}",
            })
            self.assertRedirects(response, self.manage)
            self.order.refresh_from_db()
            self.assertEqual(self.order.status, status)
            entry = self.order.history.last()
            self.assertEqual(entry.user, self.manager)
            self.assertEqual(entry.note, f"Atualização {status}")
            previous = status
        self.client.force_login(self.customer)
        response = self.client.get(self.api)
        self.assertTrue(response.json()["terminal"])
        self.assertIn("Entrega concluída", response.json()["html"])
        self.assertIn("Atualização DISPATCHED", response.json()["html"])

    def test_invalid_skipped_stale_and_oversized_updates_do_not_write(self):
        self.client.force_login(self.manager)
        for data in [
            {"expected_status": "PENDING", "status": "INVALID"},
            {"expected_status": "PENDING", "status": "DISPATCHED"},
            {"expected_status": "CONFIRMED", "status": "CONFIRMED"},
            {"expected_status": "PENDING", "status": "CONFIRMED", "note": "x" * 181},
        ]:
            self.assertEqual(self.client.post(self.manage, data).status_code, 200)
            self.order.refresh_from_db()
            self.assertEqual(self.order.status, "PENDING")
            self.assertEqual(self.order.history.count(), 1)
        self.client.get(self.manage)
        self.order.refresh_from_db()
        self.assertEqual(self.order.history.count(), 1)

    def test_delivered_and_cancelled_orders_cannot_be_changed_in_management(self):
        self.client.force_login(self.manager)
        for terminal in ["DELIVERED", "CANCELLED"]:
            Order.objects.filter(pk=self.order.pk).update(status=terminal)
            response = self.client.post(self.manage, {"expected_status": terminal, "status": "CONFIRMED"})
            self.assertEqual(response.status_code, 200)
            self.order.refresh_from_db()
            self.assertEqual(self.order.status, terminal)
            self.assertNotContains(response, 'name="status"')

    def test_cancellation_returns_reserved_stock_once(self):
        category = Category.objects.create(name="Teste entrega")
        product = Product.objects.create(category=category, name="Cookie", price=10, stock_quantity=3)
        OrderItem.objects.create(order=self.order, product=product, product_name=product.name, quantity=2, unit_price=10, subtotal=20, reserved_stock_quantity=2)
        Order.objects.filter(pk=self.order.pk).update(stock_deducted=True)
        self.client.force_login(self.manager)
        data = {"expected_status": "PENDING", "status": "CANCELLED", "note": "Cancelado pela loja."}
        self.assertRedirects(self.client.post(self.manage, data), self.manage)
        self.client.post(self.manage, data)
        product.refresh_from_db()
        self.assertEqual(product.stock_quantity, 5)
        self.client.force_login(self.customer)
        response = self.client.get(self.api).json()
        self.assertTrue(response["terminal"])
        self.assertIn("Cancelado pela loja.", response["html"])
        self.assertNotIn('aria-label="Etapas da entrega"', response["html"])

    def test_estimate_delay_and_automatic_payment_confirmation(self):
        Order.objects.filter(pk=self.order.pk).update(created_at=timezone.now() - timedelta(hours=2), status="CONFIRMED")
        OrderStatusHistory.objects.create(order=self.order, status="CONFIRMED", payment_status=Payment.Status.APPROVED, note="Pagamento simulado: Aprovado.")
        self.order.refresh_from_db()
        context = tracking_context(self.order)
        self.assertTrue(context["delayed"])
        self.assertIsNotNone(context["steps"][1]["time"])
        self.client.force_login(self.customer)
        response = self.client.get(self.url)
        self.assertContains(response, "A entrega está levando mais tempo")
        self.assertNotContains(response, "Pagamento simulado")

    def test_public_notes_are_escaped_and_csrf_is_required(self):
        self.client.force_login(self.manager)
        self.client.post(self.manage, {"expected_status": "PENDING", "status": "CONFIRMED", "note": '<script>alert("test")</script>'})
        self.client.force_login(self.customer)
        html = self.client.get(self.api).json()["html"]
        self.assertNotIn('<script>alert(', html)
        self.assertIn('&lt;script&gt;', html)
        protected = Client(enforce_csrf_checks=True)
        protected.force_login(self.manager)
        self.assertEqual(protected.post(self.manage, {"expected_status": "CONFIRMED", "status": "PREPARING"}).status_code, 403)
