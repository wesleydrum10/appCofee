from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView, PasswordResetView
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django_ratelimit.decorators import ratelimit

from .forms import AddressForm, EmailAuthenticationForm, SignUpForm
from orders.models import Order


@never_cache
def signup(request):
    form = SignUpForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        return redirect("catalog:product_list")
    return render(request, "accounts/signup.html", {"form": form})


@method_decorator(ratelimit(key="post:username", rate="5/m", method="POST", block=True), name="dispatch")
class EmailLoginView(LoginView):
    authentication_form = EmailAuthenticationForm
    template_name = "accounts/login.html"

    def get_success_url(self):
        if not self.get_redirect_url() and self.request.user.is_manager:
            return reverse_lazy("reports:dashboard")
        return super().get_success_url()

    def form_valid(self, form):
        response = super().form_valid(form)
        self.request.session.set_expiry(None if self.request.POST.get("remember_me") else 0)
        return response


class AccountLogoutView(LogoutView):
    pass


class AccountPasswordResetView(PasswordResetView):
    template_name = "accounts/password_reset.html"
    email_template_name = "accounts/password_reset_email.html"
    success_url = reverse_lazy("accounts:login")


@login_required
def profile(request):
    active_orders = request.user.orders.exclude(status__in=[Order.Status.DELIVERED, Order.Status.CANCELLED])
    current_order = active_orders.prefetch_related("items").first()
    return render(request, "accounts/profile.html", {
        "active_order_count": active_orders.count(),
        "current_order": current_order,
        "current_order_item": current_order.items.first() if current_order else None,
        "primary_address": request.user.addresses.order_by("-is_default", "id").first(),
    })


@login_required
def address_list(request):
    form = AddressForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        address = form.save(commit=False)
        address.user = request.user
        address.save()
        messages.success(request, "Endereço salvo com sucesso.")
        return redirect("accounts:addresses")
    return render(request, "accounts/addresses.html", {"form": form, "addresses": request.user.addresses.all()})
