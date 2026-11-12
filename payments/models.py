from django.db import models


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
