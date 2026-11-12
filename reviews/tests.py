from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import User
from .models import StoreFeedback


class StoreFeedbackTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(email="feedback@example.com", first_name="Ana")
        cls.other = User.objects.create_user(email="other-feedback@example.com")
        cls.manager = User.objects.create_user(email="feedback-manager@example.com", role=User.Role.MANAGER)
        cls.staff = User.objects.create_user(email="feedback-staff@example.com", role=User.Role.STAFF)

    def setUp(self):
        self.url = reverse("reviews:store")

    def test_client_can_publish_and_edit_only_own_feedback(self):
        self.client.force_login(self.user)
        response = self.client.post(self.url, {"rating": 5, "comment": "Ótimo atendimento!", "user": self.other.pk, "is_public": "0"})
        self.assertRedirects(response, self.url)
        feedback = StoreFeedback.objects.get()
        self.assertEqual(feedback.user, self.user)
        self.assertTrue(feedback.is_public)
        response = self.client.post(self.url, {"rating": 4, "comment": "Café delicioso."})
        self.assertRedirects(response, self.url)
        feedback.refresh_from_db()
        self.assertEqual(StoreFeedback.objects.count(), 1)
        self.assertEqual(feedback.rating, 4)
        self.assertEqual(feedback.comment, "Café delicioso.")

    def test_public_pages_show_feedback_without_private_email(self):
        StoreFeedback.objects.create(user=self.user, rating=5, comment="Ótimo atendimento!")
        hidden = StoreFeedback.objects.create(user=self.other, rating=1, comment="Comentário oculto", is_public=False)
        for url in (self.url, reverse("core:home")):
            response = self.client.get(url)
            self.assertContains(response, "Ótimo atendimento!")
            self.assertContains(response, "Ana")
            self.assertNotContains(response, self.user.email)
            self.assertNotContains(response, hidden.comment)
        response = self.client.get(self.url)
        self.assertEqual(response.context["summary"], {"average": 5.0, "total": 1})

    def test_missing_name_uses_generic_name_and_html_is_escaped(self):
        StoreFeedback.objects.create(user=self.other, rating=3, comment="<script>alert(1)</script>")
        response = self.client.get(self.url)
        self.assertContains(response, "Cliente")
        self.assertNotContains(response, self.other.email)
        self.assertContains(response, "&lt;script&gt;alert(1)&lt;/script&gt;")
        self.assertNotContains(response, "<script>alert(1)</script>")

    def test_invalid_feedback_does_not_save_and_keeps_comment(self):
        self.client.force_login(self.user)
        for data in ({"rating": 0, "comment": "Teste"}, {"rating": 6, "comment": "Teste"},
                     {"rating": "invalid", "comment": "Teste"}, {"rating": 5, "comment": " "},
                     {"comment": "Teste"}, {"rating": 4, "comment": "x" * 1001}):
            with self.subTest(data=data):
                response = self.client.post(self.url, data)
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context["form"].errors)
                self.assertContains(response, 'role="alert"')
                self.assertFalse(StoreFeedback.objects.exists())

    def test_anonymous_staff_and_manager_cannot_publish(self):
        response = self.client.post(self.url, {"rating": 5, "comment": "Teste"})
        self.assertEqual(response.status_code, 302)
        for user in (self.staff, self.manager):
            self.client.force_login(user)
            self.assertEqual(self.client.post(self.url, {"rating": 5, "comment": "Teste"}).status_code, 403)
        self.assertFalse(StoreFeedback.objects.exists())

    def test_moderation_is_manager_only_and_post_only(self):
        feedback = StoreFeedback.objects.create(user=self.user, rating=2, comment="Avaliação real")
        url = reverse("reports:feedback_visibility", args=[feedback.pk])
        for user in (self.user, self.staff):
            self.client.force_login(user)
            self.assertEqual(self.client.get(reverse("reports:feedbacks")).status_code, 403)
            self.assertEqual(self.client.post(url, {"is_public": "0"}).status_code, 403)
        self.client.force_login(self.manager)
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertRedirects(self.client.post(url, {"is_public": "0"}), reverse("reports:feedbacks"))
        feedback.refresh_from_db()
        self.assertFalse(feedback.is_public)
        self.assertNotContains(self.client.get(reverse("core:home")), feedback.comment)
        self.assertRedirects(self.client.post(url, {"is_public": "1"}), reverse("reports:feedbacks"))
        feedback.refresh_from_db()
        self.assertTrue(feedback.is_public)

    def test_edit_cannot_republish_hidden_feedback(self):
        feedback = StoreFeedback.objects.create(user=self.user, rating=1, comment="Oculto", is_public=False)
        self.client.force_login(self.user)
        self.client.post(self.url, {"rating": 5, "comment": "Editado", "is_public": "1"})
        feedback.refresh_from_db()
        self.assertEqual(feedback.comment, "Editado")
        self.assertFalse(feedback.is_public)
        self.assertContains(self.client.get(self.url), "oculta pelo administrador")

    def test_feedback_publication_requires_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(client.post(self.url, {"rating": 5, "comment": "Teste"}).status_code, 403)

    def test_public_feedbacks_are_paginated(self):
        for index in range(13):
            user = User.objects.create_user(email=f"page{index}@example.com")
            StoreFeedback.objects.create(user=user, rating=4, comment=f"Feedback {index}")
        response = self.client.get(self.url)
        self.assertEqual(len(response.context["page"]), 12)
        self.assertTrue(response.context["page"].has_next())
