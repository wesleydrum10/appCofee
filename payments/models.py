from django.db import models
from django.conf import settings
from django.utils import timezone
from uuid import uuid4


def generate_card_token():
    return f"simcard_{uuid4().hex}"


class SavedCardQuerySet(models.QuerySet):
    def usable(self):
        today = timezone.localdate()
        return self.filter(models.Q(expiry_year__gt=today.year) | models.Q(expiry_year=today.year, expiry_month__gte=today.month))


class SavedCard(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="saved_cards")
    token = models.CharField(max_length=80, unique=True, default=generate_card_token, editable=False)
    holder_name = models.CharField(max_length=100)
    brand = models.CharField(max_length=20)
    last_four = models.CharField(max_length=4)
    expiry_month = models.PositiveSmallIntegerField()
    expiry_year = models.PositiveSmallIntegerField()
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = SavedCardQuerySet.as_manager()

    class Meta:
        ordering = ["-is_default", "-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["user"], condition=models.Q(is_default=True), name="payments_one_default_card"),
            models.CheckConstraint(condition=models.Q(expiry_month__gte=1, expiry_month__lte=12), name="payments_card_month_valid"),
        ]

    @property
    def is_expired(self):
        today = timezone.localdate()
        return (self.expiry_year, self.expiry_month) < (today.year, today.month)

    @property
    def display_name(self):
        return f"{self.brand} •••• {self.last_four}"

    def __str__(self):
        return self.display_name


class PaymentSettings(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    simulation_enabled = models.BooleanField("Simulação de pagamentos", default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Configurações de pagamento"
        verbose_name_plural = "Configurações de pagamento"
        constraints = [models.CheckConstraint(condition=models.Q(id=1), name="payments_single_settings")]

    @classmethod
    def current(cls):
        return cls.objects.get_or_create(pk=1)[0]

    def __str__(self):
        return "Configurações de pagamento"


class Payment(models.Model):
    class Method(models.TextChoices):
        PIX = "PIX", "Pix"
        CARD = "CARD", "Cartão"
        CASH = "CASH", "Dinheiro"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pendente"
        APPROVED = "APPROVED", "Aprovado"
        DECLINED = "DECLINED", "Recusado"
        REFUNDED = "REFUNDED", "Estornado"

    order = models.OneToOneField("orders.Order", on_delete=models.CASCADE, related_name="payment")
    method = models.CharField(max_length=10, choices=Method.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    gateway_reference = models.CharField(max_length=120, blank=True)
    card_token = models.CharField(max_length=160, blank=True)
    card_display = models.CharField(max_length=80, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.order.number} - {self.get_method_display()}"


class PaymentAttempt(models.Model):
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name="attempts")
    idempotency_key = models.UUIDField(unique=True)
    status = models.CharField(max_length=20, choices=Payment.Status.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
