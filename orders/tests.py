from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from accounts.models import Address, User
from cart.models import Cart
from cart.services import CartService
from catalog.models import Category, Product
from payments.models import Payment

from .models import Order


class CheckoutTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="checkout@example.com", password="coffee-test-42!")
        self.client.force_login(self.user)
        self.cart = Cart.objects.create(user=self.user)
        category = Category.objects.create(name="Cupcakes")
        self.product = Product.objects.create(category=category, name="Red Velvet", price=Decimal("12.50"))
        self.address = Address.objects.create(user=self.user, label="Casa", recipient_name="Cliente", postal_code="14409-360", street="Rua de teste", number="123", district="Centro", city="Franca", state="SP")

    def test_summary_total_matches_created_order(self):
        CartService.add_product(self.cart, self.product, quantity=2)
        response = self.client.get(reverse("orders:checkout"))
        self.assertContains(response, "Resumo da Confeitaria")
        self.assertContains(response, "Red Velvet")
        self.assertEqual(response.context["item_count"], 2)
        displayed_total = Decimal(response.context["delivery"]["total"])
        self.assertEqual(displayed_total, Decimal("33.90"))
        response = self.client.post(reverse("orders:create"), {"address_id": self.address.pk, "payment_method": "PIX"})
        order = Order.objects.get()
        self.assertRedirects(response, reverse("orders:detail", kwargs={"number": order.number}))
        self.assertEqual(order.total, displayed_total)

    def test_default_address_is_selected_and_quotes_only_belong_to_user(self):
        default = Address.objects.create(user=self.user, label="Trabalho", recipient_name="Cliente", postal_code="01001-000", street="Praça da Sé", number="10", district="Sé", city="São Paulo", state="SP", is_default=True)
        other = User.objects.create_user(email="other@example.com", password="coffee-test-42!")
        Address.objects.create(user=other, label="Privado", recipient_name="Outro", postal_code="01001-000", street="Outro endereço", number="1", district="Centro", city="São Paulo", state="SP")
        response = self.client.get(reverse("orders:checkout"))
        self.assertEqual(response.context["selected_address"], default)
        self.assertEqual({option["id"] for option in response.context["delivery_options"]}, {self.address.pk, default.pk})

    def test_cash_payment_is_offered_and_saved_as_pending(self):
        CartService.add_product(self.cart, self.product)
        response = self.client.get(reverse("orders:checkout"))
        self.assertContains(response, 'value="CASH"')
        self.assertContains(response, "Pagamento na entrega")
        response = self.client.post(reverse("orders:create"), {"address_id": self.address.pk, "payment_method": "CASH"})
        order = Order.objects.get()
        self.assertRedirects(response, reverse("orders:detail", kwargs={"number": order.number}))
        self.assertEqual(order.payment.method, Payment.Method.CASH)
        self.assertEqual(order.payment.status, Payment.Status.PENDING)
        self.assertEqual(order.payment.amount, order.total)
        self.assertContains(self.client.get(response.url), "Dinheiro")

    def test_invalid_payment_method_preserves_cart(self):
        CartService.add_product(self.cart, self.product)
        response = self.client.post(reverse("orders:create"), {"address_id": self.address.pk, "payment_method": "INVALID"})
        self.assertRedirects(response, reverse("cart:detail"))
        self.assertFalse(Order.objects.exists())
        self.assertFalse(Payment.objects.exists())
        self.assertTrue(self.cart.items.exists())

    def test_empty_cart_and_missing_address_have_recovery_actions(self):
        response = self.client.get(reverse("orders:checkout"))
        self.assertContains(response, "Sua sacola está vazia")
        CartService.add_product(self.cart, self.product)
        self.address.delete()
        response = self.client.get(reverse("orders:checkout"))
        self.assertContains(response, "Adicionar endereço")
        self.assertNotContains(response, 'action="/checkout/criar/"')
