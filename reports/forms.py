from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.utils.text import slugify

from accounts.models import User
from catalog.models import Category, Product
from .models import Expense
from payments.models import PaymentSettings
from orders.models import Order
from orders.tracking import tracking_context


class DeliveryUpdateForm(forms.Form):
    expected_status = forms.ChoiceField(choices=Order.Status.choices, widget=forms.HiddenInput)
    status = forms.ChoiceField(label="Próxima etapa")
    note = forms.CharField(
        label="Mensagem para o cliente", max_length=180, required=False,
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Ex.: Seu pedido saiu para entrega."}),
    )

    def __init__(self, *args, order, **kwargs):
        super().__init__(*args, **kwargs)
        context = tracking_context(order)
        choices = []
        if context["next_status"]:
            choices.append((context["next_status"], context["next_label"]))
        if not context["terminal"]:
            choices.append((Order.Status.CANCELLED, "Cancelar pedido"))
        self.fields["status"].choices = choices
        self.fields["expected_status"].initial = order.status


class PaymentSettingsForm(forms.ModelForm):
    class Meta:
        model = PaymentSettings
        fields = ["simulation_enabled"]
        widgets = {"simulation_enabled": forms.CheckboxInput(attrs={"role": "switch"})}


class PeriodForm(forms.Form):
    start = forms.DateField(label="De", required=False, widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"))
    end = forms.DateField(label="Até", required=False, widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"))

    def clean(self):
        data = super().clean()
        if data.get("start") and data.get("end") and data["start"] > data["end"]:
            raise forms.ValidationError("A data inicial deve ser anterior à data final.")
        return data


class EmployeeForm(UserCreationForm):
    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "role", "password1", "password2"]
        labels = {"role": "Cargo"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["first_name"].required = True
        self.fields["role"].choices = [(User.Role.STAFF, "Atendimento"), (User.Role.MANAGER, "Gerente")]

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = user.email
        user.is_staff = True
        if commit:
            user.save()
        return user


class EmployeeEditForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "role", "is_active"]
        labels = {"role": "Cargo", "is_active": "Acesso ativo"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["role"].choices = [(User.Role.STAFF, "Atendimento"), (User.Role.MANAGER, "Gerente")]


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ["name", "slug", "category", "description", "image", "price", "stock_quantity", "minimum_stock", "nutritional_info", "is_active", "is_available"]
        labels = {"name": "Nome", "slug": "Identificador", "category": "Categoria", "description": "Descrição", "image": "Imagem", "price": "Preço (R$)", "nutritional_info": "Informações nutricionais", "is_active": "Ativo", "is_available": "Disponível"}
        widgets = {"description": forms.Textarea(attrs={"rows": 3}), "nutritional_info": forms.Textarea(attrs={"rows": 2}), "stock_quantity": forms.NumberInput(attrs={"min": 0, "step": 1}), "minimum_stock": forms.NumberInput(attrs={"min": 0, "step": 1})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["minimum_stock"].required = False

    def clean_minimum_stock(self):
        return self.cleaned_data.get("minimum_stock") or 0

    def clean(self):
        data = super().clean()
        slug = data.get("slug") or slugify(data.get("name", ""))
        if not slug:
            self.add_error("slug", "Informe um identificador válido.")
        elif Product.objects.filter(slug=slug).exclude(pk=self.instance.pk).exists():
            self.add_error("slug", "Este identificador já está em uso.")
        else:
            data["slug"] = slug
        return data


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name", "slug", "description", "is_active"]
        labels = {"name": "Nome", "slug": "Identificador", "description": "Descrição", "is_active": "Ativa"}

    def clean(self):
        data = super().clean()
        slug = data.get("slug") or slugify(data.get("name", ""))
        if not slug or Category.objects.filter(slug=slug).exclude(pk=self.instance.pk).exists():
            self.add_error("slug", "Informe um identificador válido e único.")
        else:
            data["slug"] = slug
        return data


class ExpenseForm(forms.ModelForm):
    class Meta:
        model = Expense
        fields = ["description", "amount", "paid_on"]
        widgets = {"paid_on": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")}
