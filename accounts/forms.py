from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from .models import Address, User


class SignUpForm(UserCreationForm):
    first_name = forms.CharField(label="Nome", max_length=120)
    email = forms.EmailField(label="E-mail")
    cpf = forms.CharField(label="CPF", max_length=14)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        attributes = {
            "first_name": {"placeholder": "Como podemos te chamar?", "autocomplete": "given-name"},
            "email": {"placeholder": "seu.email@exemplo.com", "autocomplete": "email"},
            "cpf": {"placeholder": "000.000.000-00", "inputmode": "numeric"},
            "password1": {"placeholder": "Crie sua senha", "autocomplete": "new-password"},
            "password2": {"placeholder": "Repita sua senha", "autocomplete": "new-password"},
        }
        for name, attrs in attributes.items():
            self.fields[name].widget.attrs.update(attrs)
        self.fields["password2"].label = "Confirmar senha"

    class Meta:
        model = User
        fields = ["first_name", "email", "cpf", "password1", "password2"]


class EmailAuthenticationForm(AuthenticationForm):
    username = forms.EmailField(label="E-mail", widget=forms.EmailInput(attrs={"autocomplete": "email"}))


class AddressForm(forms.ModelForm):
    postal_code = forms.RegexField(
        label="CEP", regex=r"^[0-9]{5}-?[0-9]{3}$", max_length=9,
        error_messages={"invalid": "Informe um CEP válido com 8 dígitos."},
    )

    def clean_postal_code(self):
        digits = self.cleaned_data["postal_code"].replace("-", "")
        return f"{digits[:5]}-{digits[5:]}"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        attributes = {
            "label": {"placeholder": "Ex.: Casa, Trabalho"},
            "recipient_name": {"placeholder": "Nome de quem recebe", "autocomplete": "name"},
            "postal_code": {"placeholder": "00000-000", "autocomplete": "postal-code", "inputmode": "numeric", "pattern": "[0-9]{5}-?[0-9]{3}", "aria-describedby": "postal-code-status"},
            "street": {"placeholder": "Rua ou avenida", "autocomplete": "address-line1"},
            "number": {"placeholder": "Ex.: 123 ou S/N"},
            "complement": {"placeholder": "Apartamento, bloco, referência", "autocomplete": "address-line2"},
            "district": {"placeholder": "Seu bairro"},
            "city": {"placeholder": "Sua cidade", "autocomplete": "address-level2"},
            "state": {"placeholder": "Ex.: SP", "autocomplete": "address-level1"},
        }
        for name, attrs in attributes.items():
            self.fields[name].widget.attrs.update({"class": "address-input", **attrs})
        self.fields["is_default"].widget.attrs["class"] = "address-checkbox"

    class Meta:
        model = Address
        exclude = ["user"]
        labels = {
            "label": "Nome do endereço", "recipient_name": "Destinatário",
            "postal_code": "CEP", "street": "Rua / Avenida", "number": "Número",
            "complement": "Complemento", "district": "Bairro", "city": "Cidade",
            "state": "Estado (UF)", "is_default": "Usar como endereço padrão",
        }
