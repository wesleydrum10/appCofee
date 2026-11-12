from unittest.mock import patch
from uuid import uuid4

from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from orders.models import Order, OrderStatusHistory
from reports.services import FinancialReportService
from .models import Payment, PaymentAttempt, PaymentSettings
from .services import PaymentService


class PaymentSimulationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("payment@test.com", "coffee-test-42!")
        self.order = Order.objects.create(user=self.user, total=25, subtotal=25)
        self.payment = Payment.objects.create(order=self.order, method=Payment.Method.PIX, amount=25)
        self.client.force_login(self.user)
        self.url = reverse("payments:simulate", args=[self.order.number])

    def request(self, key=None, retry=False):
        return self.client.post(self.url, {"idempotency_key": key or str(uuid4()), "retry": "1" if retry else ""}, HTTP_ACCEPT="application/json")

    def test_all_random_results_for_pix_and_card_are_saved_and_reported(self):
        for method in [Payment.Method.PIX, Payment.Method.CARD]:
            for status in [Payment.Status.APPROVED, Payment.Status.PENDING, Payment.Status.DECLINED]:
                with self.subTest(method=method, status=status):
                    self.payment.attempts.all().delete()
                    self.payment.method = method
                    self.payment.status = Payment.Status.PENDING
                    self.payment.save()
                    self.order.status = Order.Status.PENDING
                    self.order.save()
                    with patch("payments.services.choice", return_value=status) as chooser:
                        response = self.request()
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.json()["status"], status)
                    self.assertTrue(response.json()["message"])
                    chooser.assert_called_once()
                    self.payment.refresh_from_db()
                    self.order.refresh_from_db()
                    self.assertEqual(self.payment.status, status)
                    self.assertTrue(self.payment.gateway_reference.startswith("SIM-"))
                    self.assertEqual(self.order.status, Order.Status.CONFIRMED if status == Payment.Status.APPROVED else Order.Status.PENDING)
                    self.assertEqual(FinancialReportService.summarize()["net"], 25 if status == Payment.Status.APPROVED else 0)
                    self.assertEqual(PaymentAttempt.objects.get().status, status)

    def test_repeated_request_does_not_randomize_or_duplicate_receipts(self):
        key = str(uuid4())
        with patch("payments.services.choice", return_value=Payment.Status.APPROVED) as chooser:
            self.request(key)
            self.request(key)
            self.request(retry=True)
        chooser.assert_called_once()
        self.assertEqual(PaymentAttempt.objects.count(), 1)
        self.assertEqual(FinancialReportService.summarize()["net"], 25)
        self.assertEqual(self.order.history.count(), 1)

    def test_pending_requires_explicit_new_retry_and_refresh_never_rerolls(self):
        key = str(uuid4())
        with patch("payments.services.choice", return_value=Payment.Status.PENDING) as chooser:
            self.request(key)
            self.request()
            self.request(key, retry=True)
        chooser.assert_called_once()
        response = self.client.get(reverse("orders:detail", args=[self.order.number]))
        self.assertNotContains(response, "data-auto-simulate")
        self.assertContains(response, "Consultar pagamento")
        with patch("payments.services.choice", return_value=Payment.Status.APPROVED):
            response = self.request(retry=True)
        self.assertEqual(response.json()["status"], Payment.Status.APPROVED)
        self.assertEqual(PaymentAttempt.objects.count(), 2)

    def test_declined_can_be_retried(self):
        with patch("payments.services.choice", return_value=Payment.Status.DECLINED):
            self.request()
        self.assertContains(self.client.get(reverse("orders:detail", args=[self.order.number])), "Tentar novamente")
        with patch("payments.services.choice", return_value=Payment.Status.PENDING):
            self.assertEqual(self.request(retry=True).json()["status"], Payment.Status.PENDING)

    def test_cash_cancelled_refunded_and_invalid_keys_are_rejected(self):
        with patch("payments.services.choice") as chooser:
            self.payment.method = Payment.Method.CASH
            self.payment.save()
            self.assertEqual(self.request().status_code, 400)
            self.payment.method = Payment.Method.PIX
            self.payment.status = Payment.Status.REFUNDED
            self.payment.save()
            self.assertEqual(self.request().status_code, 400)
            self.payment.status = Payment.Status.PENDING
            self.payment.save()
            self.order.status = Order.Status.CANCELLED
            self.order.save()
            self.assertEqual(self.request().status_code, 400)
            self.assertEqual(self.request("invalid").status_code, 400)
            chooser.assert_not_called()
        self.assertFalse(PaymentAttempt.objects.exists())

    def test_ownership_post_only_and_csrf_are_enforced(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)
        from django.test import Client
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.user)
        self.assertEqual(csrf_client.post(self.url, {"idempotency_key": str(uuid4())}).status_code, 403)
        other = User.objects.create_user("other-payment@test.com", "coffee-test-42!")
        self.client.force_login(other)
        self.assertEqual(self.request().status_code, 404)
        self.client.logout()
        self.assertEqual(self.request().status_code, 302)

    def test_key_cannot_be_reused_for_another_payment(self):
        key = uuid4()
        with patch("payments.services.choice", return_value=Payment.Status.PENDING):
            PaymentService.simulate(self.payment, key)
        other_order = Order.objects.create(user=self.user, total=10)
        other_payment = Payment.objects.create(order=other_order, amount=10, method=Payment.Method.CARD)
        with self.assertRaises(ValueError):
            PaymentService.simulate(other_payment, key)

    def test_no_javascript_post_has_feedback_and_unattempted_detail_auto_starts(self):
        self.assertContains(self.client.get(reverse("orders:detail", args=[self.order.number])), "data-auto-simulate")
        with patch("payments.services.choice", return_value=Payment.Status.APPROVED):
            response = self.client.post(self.url, {"idempotency_key": str(uuid4())}, follow=True)
        self.assertContains(response, "Pagamento aprovado")
        self.assertNotContains(response, "data-payment-form")

    def test_disabled_simulator_blocks_initial_and_retry_requests(self):
        configuration = PaymentSettings.current()
        configuration.simulation_enabled = False
        configuration.save()
        with patch("payments.services.choice") as chooser:
            for retry in [False, True]:
                response = self.request(retry=retry)
                self.assertEqual(response.status_code, 400)
                self.assertFalse(response.json()["simulation_enabled"])
            chooser.assert_not_called()
        self.assertFalse(PaymentAttempt.objects.exists())
        self.payment.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.Status.PENDING)
        self.assertEqual(self.order.status, Order.Status.PENDING)
        response = self.client.get(reverse("orders:detail", args=[self.order.number]))
        self.assertNotContains(response, "data-auto-simulate")
        self.assertNotContains(response, "data-payment-form")
        self.assertContains(response, "Aguardando confirmação do recebimento")

    def test_reenabling_restores_simulation_without_resetting_past_results(self):
        with patch("payments.services.choice", return_value=Payment.Status.APPROVED):
            self.request()
        configuration = PaymentSettings.current()
        configuration.simulation_enabled = False
        configuration.save()
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.Status.APPROVED)
        self.assertEqual(FinancialReportService.summarize()["net"], 25)
        configuration.simulation_enabled = True
        configuration.save()
        with patch("payments.services.choice") as chooser:
            self.assertEqual(self.request(retry=True).json()["status"], Payment.Status.APPROVED)
            chooser.assert_not_called()
        self.assertEqual(PaymentAttempt.objects.count(), 1)

    def test_manager_setting_is_persistent_and_reenables_pending_order(self):
        self.user.role = User.Role.MANAGER
        self.user.save()
        url = reverse("reports:payment_settings")
        self.assertRedirects(self.client.post(url, {}), url)
        self.assertFalse(PaymentSettings.current().simulation_enabled)
        self.assertContains(self.client.get(url), "Desativada")
        self.assertRedirects(self.client.post(url, {"simulation_enabled": "on"}), url)
        self.assertTrue(PaymentSettings.current().simulation_enabled)
        self.assertEqual(PaymentSettings.objects.count(), 1)
        self.assertContains(self.client.get(reverse("orders:detail", args=[self.order.number])), "data-auto-simulate")

    def test_customer_and_staff_cannot_change_settings(self):
        url = reverse("reports:payment_settings")
        for role in [User.Role.CLIENT, User.Role.STAFF]:
            self.user.role = role
            self.user.save()
            self.assertEqual(self.client.get(url).status_code, 403)
            self.assertEqual(self.client.post(url, {}).status_code, 403)
        self.assertTrue(PaymentSettings.current().simulation_enabled)

    def test_declined_flag_survives_a_later_approval(self):
        with patch("payments.services.choice", return_value=Payment.Status.DECLINED):
            response = self.request()
        self.assertEqual(response.json()["timeline_entry"]["status"], Payment.Status.DECLINED)
        self.assertEqual(response.json()["timeline_entry"]["label"], "Recusado")
        entry = self.order.history.get()
        self.assertEqual(entry.status, Order.Status.PENDING)
        self.assertEqual(entry.payment_status, Payment.Status.DECLINED)
        self.assertEqual(entry.event_label, "Recusado")
        with patch("payments.services.choice", return_value=Payment.Status.APPROVED):
            self.request(retry=True)
        response = self.client.get(reverse("orders:detail", args=[self.order.number]))
        self.assertContains(response, 'class="status-badge" data-status="DECLINED">Recusado')
        self.assertContains(response, 'class="status-badge" data-status="APPROVED">Aprovado')
        entry.refresh_from_db()
        self.assertEqual(entry.event_status, Payment.Status.DECLINED)

    def test_existing_simulation_notes_are_backfilled_without_changing_order_status(self):
        from importlib import import_module
        from django.apps import apps
        legacy = OrderStatusHistory.objects.create(order=self.order, status=Order.Status.PENDING, note="Pagamento simulado: Recusado.")
        created = OrderStatusHistory.objects.create(order=self.order, status=Order.Status.PENDING, note="Pedido criado.")
        migration = import_module("orders.migrations.0003_orderstatushistory_payment_status")
        migration.backfill_payment_status(apps, None)
        legacy.refresh_from_db()
        created.refresh_from_db()
        self.assertEqual(legacy.payment_status, Payment.Status.DECLINED)
        self.assertEqual(legacy.status, Order.Status.PENDING)
        self.assertEqual(created.payment_status, "")
        self.assertEqual(created.event_label, "Pendente")
