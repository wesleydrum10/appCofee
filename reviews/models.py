from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q


class StoreFeedback(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="store_feedback")
    rating = models.PositiveSmallIntegerField("Nota", validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField("Comentário", max_length=1000)
    is_public = models.BooleanField("Publicado", default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        verbose_name = "Feedback da loja"
        verbose_name_plural = "Feedbacks da loja"
        constraints = [models.CheckConstraint(condition=Q(rating__gte=1, rating__lte=5), name="store_feedback_rating_1_to_5")]

    @property
    def public_name(self):
        return self.user.first_name.strip() or "Cliente"

    def __str__(self):
        return f"{self.public_name} - {self.rating}/5"


class Review(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reviews")
    order = models.ForeignKey("orders.Order", on_delete=models.CASCADE, related_name="reviews")
    product = models.ForeignKey("catalog.Product", null=True, blank=True, on_delete=models.SET_NULL, related_name="reviews")
    rating = models.PositiveSmallIntegerField()
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(check=Q(rating__gte=1) & Q(rating__lte=5), name="reviews_rating_between_1_and_5"),
            models.UniqueConstraint(fields=["user", "order", "product"], name="reviews_unique_product_review"),
        ]

    def clean(self):
        if self.order.status != "DELIVERED":
            raise ValidationError("Avaliação permitida somente após entrega.")

    def __str__(self):
        return f"{self.rating}/5 - {self.user}"
