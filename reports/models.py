from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class Expense(models.Model):
    description = models.CharField("Descrição", max_length=180)
    amount = models.DecimalField("Valor", max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    paid_on = models.DateField("Data do pagamento", default=timezone.localdate)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-paid_on", "-id"]
        constraints = [models.CheckConstraint(condition=models.Q(amount__gt=0), name="reports_expense_positive")]

    def __str__(self):
        return self.description
