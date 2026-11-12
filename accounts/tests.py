from django.conf import settings
from django.test import Client, TestCase
from django.urls import reverse

from .models import Address, User
from .forms import AddressForm


class HeaderIdentityTests(TestCase):
    def test_authenticated_header_shows_name_and_role(self):
        user = User.objects.create_user(email="header@example.com", first_name="Ana", last_name="Silva")
        self.client.force_login(user)
        response = self.client.get(reverse("catalog:product_list"))
        self.assertContains(response, 'class="header-user"', count=1)
        self.assertContains(response, 'class="header-user-name">Ana Silva</span>')
        self.assertContains(response, 'class="header-user-role">Cliente</span>')

    def test_header_falls_back_to_email_and_escapes_name(self):
        user = User.objects.create_user(email="header@example.com")
        self.client.force_login(user)
        response = self.client.get(reverse("catalog:product_list"))
        self.assertContains(response, 'class="header-user-name">header@example.com</span>')
        user.first_name = "<script>alert(1)</script>"
        user.save()
        response = self.client.get(reverse("catalog:product_list"))
        self.assertContains(response, "&lt;script&gt;alert(1)&lt;/script&gt;")
        self.assertNotContains(response, "<script>alert(1)</script>")

    def test_anonymous_header_keeps_login_without_identity(self):
        response = self.client.get(reverse("catalog:product_list"))
        self.assertNotContains(response, 'class="header-user"')
        self.assertContains(response, reverse("accounts:login"))

    def test_manager_header_shows_identity(self):
        user = User.objects.create_user(email="manager-header@example.com", first_name="Maria", role=User.Role.MANAGER)
        self.client.force_login(user)
        response = self.client.get(reverse("reports:dashboard"))
        self.assertContains(response, 'class="header-user"', count=1)
        self.assertContains(response, 'class="header-user-name">Maria</span>')
        self.assertContains(response, 'class="header-user-role">Gerente</span>')


class LoginTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User.objects.create_user(email="login@example.com", password="test-password-42")

    def test_login_page_renders_reference_layout(self):
        response = self.client.get(reverse("accounts:login"), {"next": "/produtos/"})
        self.assertContains(response, "Que bom te ver de novo")
        self.assertContains(response, 'name="next" value="/produtos/"')
        self.assertContains(response, 'name="username"')

    def test_login_respects_remember_me_and_redirect(self):
        for remember in (False, True):
            with self.subTest(remember=remember):
                self.client.logout()
                data = {"username": "login@example.com", "password": "test-password-42", "next": "/produtos/"}
                if remember:
                    data["remember_me"] = "on"
                response = self.client.post(reverse("accounts:login"), data)
                self.assertRedirects(response, "/produtos/", fetch_redirect_response=False)
                self.assertEqual(self.client.session.get_expire_at_browser_close(), not remember)

    def test_invalid_login_preserves_email_and_displays_errors(self):
        response = self.client.post(reverse("accounts:login"), {"username": "login@example.com", "password": "wrong"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'value="login@example.com"')
        self.assertContains(response, 'role="alert"')
        self.assertNotIn("_auth_user_id", self.client.session)


class SignupTests(TestCase):
    def test_signup_renders_all_fields(self):
        response = self.client.get(reverse("accounts:signup"))
        for name in ("first_name", "email", "cpf", "password1", "password2"):
            self.assertContains(response, f'name="{name}"')
        self.assertContains(response, "Criar minha conta")

    def test_invalid_signup_shows_errors_and_keeps_values(self):
        response = self.client.post(reverse("accounts:signup"), {
            "first_name": "Teste", "email": "invalid", "cpf": "invalid",
            "password1": "short", "password2": "different",
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'value="Teste"')
        self.assertContains(response, 'aria-invalid="true"')
        self.assertContains(response, 'role="alert"')
        self.assertFalse(User.objects.exists())


class SignupCsrfTests(TestCase):
    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        self.url = reverse("accounts:signup")
        self.data = {
            "first_name": "Cliente", "email": "cadastro@example.com",
            "cpf": "529.982.247-25", "password1": "coffee-test-42!",
            "password2": "coffee-test-42!",
        }

    def test_signup_with_csrf_and_unrelated_localhost_cookies(self):
        response = self.client.get(self.url)
        self.assertIn("no-store", response.headers["Cache-Control"])
        self.assertEqual(settings.CSRF_COOKIE_NAME, "appcoffee_csrftoken")
        self.assertEqual(settings.SESSION_COOKIE_NAME, "appcoffee_sessionid")
        token = self.client.cookies[settings.CSRF_COOKIE_NAME].value
        self.client.cookies["csrftoken"] = "a" * 32
        self.client.cookies["sessionid"] = "another-localhost-app"
        response = self.client.post(self.url, {**self.data, "csrfmiddlewaretoken": token}, HTTP_ORIGIN="http://testserver")
        self.assertRedirects(response, reverse("catalog:product_list"), fetch_redirect_response=False)
        user = User.objects.get(email=self.data["email"])
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)
        self.assertIn(settings.SESSION_COOKIE_NAME, self.client.cookies)

    def test_signup_without_token_is_still_rejected(self):
        self.client.get(self.url)
        self.assertEqual(self.client.post(self.url, self.data).status_code, 403)
        self.assertFalse(User.objects.exists())

    def test_signup_with_untrusted_origin_is_still_rejected(self):
        self.client.get(self.url)
        token = self.client.cookies[settings.CSRF_COOKIE_NAME].value
        response = self.client.post(self.url, {**self.data, "csrfmiddlewaretoken": token}, HTTP_ORIGIN="http://untrusted.example")
        self.assertEqual(response.status_code, 403)
        self.assertFalse(User.objects.exists())


class AddressTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="address@example.com", password="coffee-test-42!")
        self.client.force_login(self.user)
        self.url = reverse("accounts:addresses")

    def test_address_form_labels_and_invalid_values(self):
        response = self.client.get(self.url)
        for label in ("Destinatário", "CEP", "Rua / Avenida", "Bairro", "Estado (UF)"):
            self.assertContains(response, label)
        response = self.client.post(self.url, {"label": "Casa"})
        self.assertContains(response, 'value="Casa"')
        self.assertContains(response, 'role="alert"')
        self.assertFalse(Address.objects.exists())

    def test_address_is_saved_for_current_user(self):
        response = self.client.post(self.url, {
            "label": "Casa", "recipient_name": "Cliente", "postal_code": "01001-000",
            "street": "Praça da Sé", "number": "123", "complement": "Apto 2",
            "district": "Sé", "city": "São Paulo", "state": "SP", "is_default": "on",
        })
        self.assertRedirects(response, self.url)
        address = Address.objects.get()
        self.assertEqual(address.user_id, self.user.pk)
        self.assertTrue(address.is_default)

    def test_postal_code_validation_and_normalization(self):
        for value in ("14409360", "14409-360"):
            form = AddressForm({"postal_code": value})
            form.is_valid()
            self.assertEqual(form.cleaned_data["postal_code"], "14409-360")
        for value in ("1440936", "144093600", "1440A360", "14409/360"):
            form = AddressForm({"postal_code": value})
            form.is_valid()
            self.assertIn("postal_code", form.errors)


class ProfileTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="profile@example.com", first_name="Wesley", password="coffee-test-42!")
        self.client.force_login(self.user)

    def test_profile_uses_only_current_user_orders_and_addresses(self):
        from orders.models import Order

        current = Order.objects.create(user=self.user, postal_code="14409-360", status=Order.Status.PREPARING)
        Order.objects.create(user=self.user, postal_code="14409-360", status=Order.Status.DELIVERED)
        other = User.objects.create_user(email="private@example.com", password="coffee-test-42!")
        other_order = Order.objects.create(user=other, postal_code="01001-000")
        address = Address.objects.create(user=self.user, label="Casa", recipient_name="Cliente", street="Rua Principal", number="10", postal_code="14409-360", district="Centro", city="Franca", state="SP", is_default=True)
        response = self.client.get(reverse("accounts:profile"))
        self.assertEqual(response.context["active_order_count"], 1)
        self.assertEqual(response.context["current_order"], current)
        self.assertEqual(response.context["primary_address"], address)
        self.assertContains(response, "Wesley")
        self.assertContains(response, "Preparando")
        self.assertNotContains(response, other_order.number)

    def test_profile_logout_uses_protected_post(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        response = client.get(reverse("accounts:profile"))
        self.assertContains(response, 'id="logout-dialog"')
        self.assertEqual(client.get(reverse("accounts:logout")).status_code, 405)
        self.assertEqual(client.post(reverse("accounts:logout")).status_code, 403)
        token = client.cookies[settings.CSRF_COOKIE_NAME].value
        response = client.post(reverse("accounts:logout"), {"csrfmiddlewaretoken": token})
        self.assertEqual(response.status_code, 302)
        self.assertNotIn("_auth_user_id", client.session)
