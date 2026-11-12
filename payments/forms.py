import re

from django import forms
from django.utils import timezone


TEST_CARDS = {"4242424242424242": "Visa", "5555555555554444": "Mastercard"}


class SavedCardForm(forms.Form):
    holder_name = forms.CharField(label="Nome no cartão", max_length=100, widget=forms.TextInput(attrs={"autocomplete": "cc-name"}))
    number = forms.CharField(
        label="Número do cartão de teste", max_length=19,
        widget=forms.TextInput(attrs={"inputmode": "numeric", "autocomplete": "off", "placeholder": "4242 4242 4242 4242", "data-card-number": ""}),
        help_text="Use 4242 4242 4242 4242 (Visa) ou 5555 5555 5555 4444 (Mastercard).",
    )
    expiry_month = forms.IntegerField(label="Mês de validade", min_value=1, max_value=12, widget=forms.NumberInput(attrs={"autocomplete": "cc-exp-month", "placeholder": "MM"}))
    expiry_year = forms.IntegerField(label="Ano de validade", widget=forms.NumberInput(attrs={"autocomplete": "cc-exp-year", "placeholder": "AAAA"}))
    is_default = forms.BooleanField(label="Usar como cartão padrão", required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        today = timezone.localdate()
        self.fields["expiry_year"].min_value = today.year
        self.fields["expiry_year"].max_value = today.year + 20
        self.fields["expiry_year"].widget.attrs.update({"min": today.year, "max": today.year + 20})

    def clean_number(self):
        number = re.sub(r"[ -]", "", self.cleaned_data["number"])
        if number not in TEST_CARDS:
            raise forms.ValidationError("Use um dos cartões de teste indicados. Não cadastre um cartão real.")
        # Only masked metadata leaves validation; never pass a full number to storage.
        return {"brand": TEST_CARDS[number], "last_four": number[-4:]}

    def clean(self):
        data = super().clean()
        month, year = data.get("expiry_month"), data.get("expiry_year")
        today = timezone.localdate()
        if year and (year < today.year or year > today.year + 20):
            self.add_error("expiry_year", "Informe um ano válido dentro dos próximos 20 anos.")
        elif month and year and (year, month) < (today.year, today.month):
            self.add_error("expiry_month", "Este cartão está vencido.")
        return data
