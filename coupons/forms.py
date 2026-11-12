import re

from django import forms

from .models import Coupon


class CouponForm(forms.ModelForm):
    class Meta:
        model = Coupon
        fields = ["code", "description", "discount_type", "value", "minimum_order_value", "starts_at", "expires_at", "usage_limit", "usage_limit_per_user", "is_active"]
        labels = {"code": "Código", "description": "Descrição", "discount_type": "Tipo de desconto", "value": "Valor do desconto", "minimum_order_value": "Pedido mínimo (R$)", "starts_at": "Início da validade", "expires_at": "Fim da validade", "usage_limit": "Limite total de usos (opcional)", "usage_limit_per_user": "Limite de usos por cliente", "is_active": "Ativo"}
        widgets = {
            "starts_at": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "expires_at": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "minimum_order_value": forms.NumberInput(attrs={"min": 0, "step": "0.01"}),
            "usage_limit": forms.NumberInput(attrs={"min": 1, "step": 1}),
            "usage_limit_per_user": forms.NumberInput(attrs={"min": 1, "step": 1}),
        }

    def clean_code(self):
        code = self.cleaned_data["code"].strip().upper()
        if not re.fullmatch(r"[A-Z0-9_-]+", code):
            raise forms.ValidationError("Use letras, números, hífen ou sublinhado no código.")
        if Coupon.objects.filter(code__iexact=code).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Já existe um cupom com este código.")
        return code

    def clean(self):
        data = super().clean()
        if data.get("discount_type") == Coupon.DiscountType.PERCENT and data.get("value") is not None and data["value"] > 100:
            self.add_error("value", "O desconto percentual não pode ultrapassar 100%.")
        if data.get("minimum_order_value") is not None and data["minimum_order_value"] < 0:
            self.add_error("minimum_order_value", "O pedido mínimo não pode ser negativo.")
        if data.get("starts_at") and data.get("expires_at") and data["starts_at"] >= data["expires_at"]:
            self.add_error("expires_at", "O fim da validade deve ser posterior ao início.")
        for field in ["usage_limit", "usage_limit_per_user"]:
            if data.get(field) is not None and data[field] < 1:
                self.add_error(field, "Informe um limite maior que zero.")
        return data
