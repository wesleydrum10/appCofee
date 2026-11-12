from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Address, User
from cart.models import Cart
from cart.services import CartService
from catalog.models import Category, Product
from orders.models import Order
from orders.services import OrderService
from .models import SavedCard


class SavedCardTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(email="cards@example.com")
        cls.other = User.objects.create_user(email="other-cards@example.com")
        cls.year = timezone.localdate().year + 1

    def setUp(self):
        self.client.force_login(self.user)
        self.url = reverse("accounts:cards")
        self.data = {"holder_name": "Cliente Teste", "number": "4242 4242 4242 4242", "expiry_month": 12, "expiry_year": self.year}

    def make_card(self, **kwargs):
        return SavedCard.objects.create(**{
            "user": self.user, "holder_name": "Cliente Teste", "brand": "Visa", "last_four": "4242",
            "expiry_month": 12, "expiry_year": self.year, **kwargs,
        })

    def checkout_fixture(self):
        address = Address.objects.create(user=self.user, label="Casa", postal_code="01001-000", street="Rua teste", number="10", city="São Paulo", state="SP")
        category = Category.objects.create(name="Cafés")
        product = Product.objects.create(category=category, name="Café", price=10, stock_quantity=5)
        cart = Cart.objects.create(user=self.user)
        CartService.add_product(cart, product)
        return cart, address, product

    def test_create_masks_card_and_defaults_first_without_saving_number(self):
        response = self.client.post(self.url, self.data)
        card = SavedCard.objects.get()
        self.assertRedirects(response, f"{self.url}#card-{card.pk}")
        self.assertTrue(card.is_default)
        self.assertEqual(card.display_name, "Visa •••• 4242")
        self.assertTrue(card.token.startswith("simcard_"))
        self.assertNotIn("4242424242424242", str(card.__dict__))
        self.assertFalse(any(field.name in {"number", "cvv", "cvc"} for field in SavedCard._meta.fields))
        response = self.client.get(self.url)
        self.assertContains(response, "•••• •••• •••• 4242")
        self.assertIn("no-store", response.headers["Cache-Control"])
        self.assertNotContains(response, card.token)

    def test_rejects_non_demo_numbers_invalid_expiration_and_duplicates(self):
        for fields in [
            {"number": "4111111111111111"}, {"number": "123"}, {"number": "4242x424242424242"},
            {"expiry_month": 13}, {"expiry_year": self.year-2}, {"expiry_year": self.year+100},
        ]:
            with self.subTest(fields=fields):
                response = self.client.post(self.url, {**self.data, **fields})
                self.assertEqual(response.status_code, 200)
                self.assertFalse(SavedCard.objects.exists())
                self.assertTrue(response.context["form"].errors)
        self.client.post(self.url, self.data)
        response = self.client.post(self.url, self.data)
        self.assertContains(response, "já está cadastrado")
        self.assertEqual(SavedCard.objects.count(), 1)

    def test_default_and_delete_are_private_post_only_and_preserve_one_default(self):
        first = self.make_card(is_default=True)
        second = self.make_card(brand="Mastercard", last_four="4444")
        default = reverse("accounts:card_default", args=[second.pk])
        delete = reverse("accounts:card_delete", args=[second.pk])
        self.assertEqual(self.client.get(default).status_code, 405)
        self.assertEqual(self.client.get(delete).status_code, 405)
        self.assertRedirects(self.client.post(default), self.url)
        self.assertEqual(list(self.user.saved_cards.filter(is_default=True)), [second])
        self.assertRedirects(self.client.post(delete), self.url)
        first.refresh_from_db()
        self.assertTrue(first.is_default)
        self.client.force_login(self.other)
        self.assertNotContains(self.client.get(self.url), "•••• •••• •••• 4242")
        for action in ["card_default", "card_delete"]:
            self.assertEqual(self.client.post(reverse(f"accounts:{action}", args=[first.pk])).status_code, 404)
        self.assertTrue(SavedCard.objects.filter(pk=first.pk).exists())

    def test_login_and_csrf_required(self):
        card = self.make_card()
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 302)
        self.assertEqual(self.client.post(self.url, self.data).status_code, 302)
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        for url in [self.url, reverse("accounts:card_delete", args=[card.pk]), reverse("accounts:card_default", args=[card.pk])]:
            self.assertEqual(client.post(url, self.data).status_code, 403)

    def test_expired_cards_not_selectable_and_cannot_be_default(self):
        expired = self.make_card(expiry_year=self.year-2)
        active = self.make_card(last_four="4444", brand="Mastercard")
        self.checkout_fixture()
        response = self.client.get(reverse("orders:checkout"))
        self.assertEqual(list(response.context["saved_cards"]), [active])
        self.assertNotContains(response, f'<option value="{expired.pk}"')
        self.assertEqual(self.client.post(reverse("accounts:card_default", args=[expired.pk])).status_code, 404)

    def test_checkout_requires_own_valid_card_without_changing_cart_or_stock(self):
        cart, address, product = self.checkout_fixture()
        foreign = self.make_card(user=self.other)
        expired = self.make_card(expiry_year=self.year-2)
        for card_id in [None, "bad-id", str(10**30), foreign.pk, expired.pk]:
            with self.subTest(card_id=card_id):
                with self.assertRaisesMessage(ValueError, "selecione um cartão válido"):
                    OrderService.create_order(cart, self.user, address, "CARD", saved_card_id=card_id)
                self.assertFalse(Order.objects.exists())
                product.refresh_from_db()
                self.assertEqual(product.stock_quantity, 5)
                self.assertEqual(cart.items.count(), 1)
        response = self.client.post(reverse("orders:create"), {"address_id": address.pk, "payment_method": "CARD"})
        self.assertRedirects(response, reverse("orders:checkout"))

    def test_selected_card_is_used_and_deletion_preserves_order_payment(self):
        cart, address, product = self.checkout_fixture()
        card = self.make_card(is_default=True)
        other = self.make_card(brand="Mastercard", last_four="4444")
        self.assertContains(self.client.get(reverse("orders:checkout")), f'<option value="{card.pk}" selected>')
        response = self.client.post(reverse("orders:create"), {"address_id": address.pk, "payment_method": "CARD", "saved_card_id": other.pk})
        order = Order.objects.get()
        self.assertRedirects(response, reverse("orders:detail", args=[order.number]))
        self.assertEqual(order.payment.card_token, other.token)
        self.assertEqual(order.payment.card_display, other.display_name)
        self.assertEqual(order.payment.status, "PENDING")
        self.client.post(reverse("accounts:card_delete", args=[other.pk]))
        order.payment.refresh_from_db()
        self.assertEqual(order.payment.card_display, "Mastercard •••• 4444")
        self.assertContains(self.client.get(response.url), "Mastercard •••• 4444")
        self.assertFalse(order.can_track_delivery)

    def test_pix_and_cash_do_not_require_card_and_ignore_submitted_card_id(self):
        cart, address, product = self.checkout_fixture()
        order = OrderService.create_order(cart, self.user, address, "PIX", saved_card_id="invalid")
        self.assertEqual(order.payment.card_token, "")
        CartService.add_product(cart, product)
        order = OrderService.create_order(cart, self.user, address, "CASH")
        self.assertEqual(order.payment.card_display, "")

    def test_checkout_registration_reloads_card_list_and_name_is_escaped(self):
        response = self.client.post(self.url + "?checkout=1", {**self.data, "holder_name": '<script>alert(1)</script>'})
        card = SavedCard.objects.get()
        self.assertRedirects(response, f"{self.url}?checkout=1#card-{card.pk}", fetch_redirect_response=False)
        response = self.client.get(response.url)
        self.assertNotContains(response, '<script>alert(1)</script>')
        self.assertContains(response, '&lt;script&gt;alert(1)&lt;/script&gt;')
        self.assertContains(response, f'id="card-{card.pk}"')
        self.assertContains(response, 'Cartão de teste cadastrado com sucesso.')
        self.assertContains(response, 'Voltar ao checkout')
        self.assertFalse(response.context["form"].is_bound)
        self.assertEqual(SavedCard.objects.count(), 1)
        self.client.get(response.request["PATH_INFO"])
        self.assertEqual(SavedCard.objects.count(), 1)
