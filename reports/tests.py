from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from catalog.models import Category, Product
from orders.models import Order, OrderItem
from payments.models import Payment
from .models import Expense
from .services import FinancialReportService


class ManagementTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user("manager@test.com", "Strong-test-password!", role=User.Role.MANAGER, is_staff=True)
        self.customer = User.objects.create_user("customer@test.com", "Strong-test-password!")
        self.staff = User.objects.create_user("staff@test.com", "Strong-test-password!", role=User.Role.STAFF, is_staff=True)
        self.category = Category.objects.create(name="Cafés")
        self.client.force_login(self.manager)

    def test_management_pages_render(self):
        for name in ["dashboard", "products", "product_create", "employees", "employee_create", "categories", "category_create", "expenses", "expense_create", "orders"]:
            with self.subTest(name=name):
                self.assertEqual(self.client.get(reverse(f"reports:{name}")).status_code, 200)

    def test_management_denies_customer_and_staff(self):
        for user in [self.customer, self.staff]:
            self.client.force_login(user)
            for name in ["dashboard", "products", "product_create", "employees", "employee_create", "categories", "category_create", "expenses", "expense_create", "orders"]:
                with self.subTest(user=user.email, name=name):
                    self.assertEqual(self.client.get(reverse(f"reports:{name}")).status_code, 403)
                    self.assertEqual(self.client.post(reverse(f"reports:{name}"), {}).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(reverse("reports:dashboard")).status_code, 302)

    def test_create_employee_hashes_password_and_prevents_privilege_injection(self):
        response = self.client.post(reverse("reports:employee_create"), {
            "first_name": "Ana", "email": "ana@test.com", "role": User.Role.STAFF,
            "password1": "Different-password!42", "password2": "Different-password!42", "is_superuser": "on",
        })
        self.assertRedirects(response, reverse("reports:employees"))
        employee = User.objects.get(email="ana@test.com")
        self.assertTrue(employee.check_password("Different-password!42"))
        self.assertTrue(employee.is_staff)
        self.assertFalse(employee.is_superuser)
        self.assertFalse(employee.is_manager)

    def test_cannot_disable_or_demote_self_or_edit_superuser(self):
        for data in [{"role": User.Role.MANAGER}, {"role": User.Role.STAFF, "is_active": "on"}]:
            response = self.client.post(reverse("reports:employee_edit", args=[self.manager.pk]), {"email": self.manager.email, "first_name": "Gerente", **data})
            self.assertEqual(response.status_code, 200)
            self.manager.refresh_from_db()
            self.assertTrue(self.manager.is_active)
            self.assertTrue(self.manager.is_manager)
        admin = User.objects.create_superuser("admin@test.com", "Strong-test-password!")
        self.assertEqual(self.client.post(reverse("reports:employee_edit", args=[admin.pk]), {}).status_code, 403)
        self.assertEqual(self.client.get(reverse("reports:employee_edit", args=[self.customer.pk])).status_code, 404)

    def test_employee_can_be_deactivated(self):
        response = self.client.post(reverse("reports:employee_edit", args=[self.staff.pk]), {"email": self.staff.email, "role": User.Role.STAFF})
        self.assertEqual(response.status_code, 302)
        self.staff.refresh_from_db()
        self.assertFalse(self.staff.is_active)

    def test_product_create_edit_and_slug_collision(self):
        data = {"name": "Café especial", "category": self.category.pk, "description": "Café da casa", "price": "12.50", "is_active": "on", "is_available": "on"}
        self.assertRedirects(self.client.post(reverse("reports:product_create"), data), reverse("reports:products"))
        product = Product.objects.get(name="Café especial")
        self.assertEqual(product.slug, "cafe-especial")
        response = self.client.post(reverse("reports:product_create"), data)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)
        self.assertRedirects(self.client.post(reverse("reports:product_edit", args=[product.pk]), {**data, "price": "14.50", "is_available": ""}), reverse("reports:products"))
        product.refresh_from_db()
        self.assertEqual(product.price, Decimal("14.50"))
        self.assertFalse(product.is_available)
        self.assertFalse(Product.objects.available().filter(pk=product.pk).exists())

    def test_category_and_expense_workflows(self):
        self.assertRedirects(self.client.post(reverse("reports:category_create"), {"name": "Doces", "is_active": "on"}), reverse("reports:categories"))
        category = Category.objects.get(name="Doces")
        self.assertEqual(category.slug, "doces")
        self.assertEqual(self.client.post(reverse("reports:category_create"), {"name": "doces"}).status_code, 200)
        self.assertRedirects(self.client.post(reverse("reports:expense_create"), {"description": "Insumos", "amount": "30.50", "paid_on": timezone.localdate().isoformat()}), reverse("reports:expenses"))
        expense = Expense.objects.get()
        self.assertEqual(expense.created_by, self.manager)
        self.assertEqual(self.client.get(reverse("reports:expense_delete", args=[expense.pk])).status_code, 405)
        self.assertRedirects(self.client.post(reverse("reports:expense_delete", args=[expense.pk])), reverse("reports:expenses"))
        self.assertFalse(Expense.objects.exists())

    def test_receipts_exclude_pending_refunded_cancelled_and_filter_payment_date(self):
        for payment_status, order_status in [(Payment.Status.APPROVED, Order.Status.CONFIRMED), (Payment.Status.PENDING, Order.Status.PENDING), (Payment.Status.REFUNDED, Order.Status.CONFIRMED), (Payment.Status.APPROVED, Order.Status.CANCELLED)]:
            order = Order.objects.create(user=self.customer, subtotal=100, total=100)
            order.status = order_status
            order.save()
            Order.objects.filter(pk=order.pk).update(created_at=timezone.now() - timedelta(days=10))
            Payment.objects.create(order=order, method=Payment.Method.PIX, status=payment_status, amount=100)
        Expense.objects.create(description="Insumos", amount=30)
        Expense.objects.create(description="Anterior", amount=20, paid_on=timezone.localdate() - timedelta(days=10))
        summary = FinancialReportService.summarize(timezone.localdate(), timezone.localdate())
        self.assertEqual(summary["net"], Decimal("100"))
        self.assertEqual(summary["expenses"], Decimal("30"))
        self.assertEqual(summary["balance"], Decimal("70"))
        self.assertEqual(summary["quantity"], 1)
        response = self.client.get(reverse("reports:dashboard"), {"export": "csv"})
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn("Recebimentos;100", response.content.decode())

    def test_invalid_dates_are_validation_errors(self):
        for data in [{"start": "invalid"}, {"start": "2026-10-08", "end": "2026-01-01"}]:
            response = self.client.get(reverse("reports:dashboard"), data)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context["form"].errors)
            self.assertIsNone(response.context["summary"])

    def test_pending_orders_appear_without_becoming_receipts(self):
        product = Product.objects.create(category=self.category, name="Café", description="Café", price="14.90")
        for total, quantity in [("23.80", 1), ("53.60", 3)]:
            order = Order.objects.create(user=self.customer, total=total, subtotal=Decimal("14.90") * quantity)
            Payment.objects.create(order=order, method=Payment.Method.PIX, amount=total)
            OrderItem.objects.create(order=order, product=product, product_name=product.name, quantity=quantity, unit_price="14.90", subtotal=Decimal("14.90") * quantity)
        cancelled = Order.objects.create(user=self.customer, total=99, status=Order.Status.CANCELLED)
        Payment.objects.create(order=cancelled, method=Payment.Method.PIX, amount=99)
        summary = FinancialReportService.summarize()
        self.assertEqual(summary["placed_quantity"], 2)
        self.assertEqual(summary["placed_total"], Decimal("77.40"))
        self.assertEqual(summary["pending_quantity"], 2)
        self.assertEqual(summary["pending_total"], Decimal("77.40"))
        self.assertEqual(summary["net"], 0)
        self.assertEqual(summary["quantity"], 0)
        self.assertEqual(list(summary["top_products"])[0]["quantity"], 4)
        today = FinancialReportService.cashflow()[-1]
        self.assertEqual(today["placed"], Decimal("77.40"))
        self.assertEqual(today["receipt"], 0)
        response = self.client.get(reverse("reports:dashboard"))
        self.assertContains(response, "77,40")
        self.assertContains(response, "2 pedidos aguardando pagamento")
        next_day = timezone.localdate() + timedelta(days=1)
        self.assertEqual(FinancialReportService.summarize(next_day, next_day)["placed_quantity"], 0)

    def test_quick_periods_and_cashflow_use_real_dates_and_values(self):
        today = timezone.localdate()
        order = Order.objects.create(user=self.customer, subtotal=100, total=100)
        Payment.objects.create(order=order, method=Payment.Method.PIX, status=Payment.Status.APPROVED, amount=100)
        Expense.objects.create(description="Hoje", amount=30, paid_on=today)
        Expense.objects.create(description="Anterior", amount=50, paid_on=today - timedelta(days=7))
        for period, start in [("today", today), ("week", today - timedelta(days=6)), ("month", today.replace(day=1))]:
            response = self.client.get(reverse("reports:dashboard"), {"period": period})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context["form"].cleaned_data["start"], start)
            self.assertEqual(response.context["form"].cleaned_data["end"], today)
        days = FinancialReportService.cashflow(today - timedelta(days=6), today)
        self.assertEqual(len(days), 7)
        self.assertEqual(days[-1]["receipt"], Decimal("100"))
        self.assertEqual(days[-1]["expense"], Decimal("30"))
        self.assertEqual(days[-1]["receipt_height"], 100)
        self.assertEqual(days[-1]["expense_height"], 30)
        self.assertEqual(sum(day["expense"] for day in days), Decimal("30"))
        self.assertEqual(len(FinancialReportService.cashflow(today, today)), 1)

    def test_manager_login_opens_dashboard_and_respects_next(self):
        self.client.logout()
        response = self.client.post(reverse("accounts:login"), {"username": self.manager.email, "password": "Strong-test-password!"})
        self.assertRedirects(response, reverse("reports:dashboard"))
        self.client.logout()
        response = self.client.post(reverse("accounts:login") + "?next=/conta/", {"username": self.manager.email, "password": "Strong-test-password!"})
        self.assertRedirects(response, "/conta/")
