from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_POST

from .forms import SavedCardForm
from .models import SavedCard


@sensitive_post_parameters("number")
@never_cache
@login_required
def cards(request):
    form = SavedCardForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        with transaction.atomic():
            get_user_model().objects.select_for_update().get(pk=request.user.pk)
            existing = request.user.saved_cards.filter(
                **data["number"], expiry_month=data["expiry_month"], expiry_year=data["expiry_year"],
            ).exists()
            if existing:
                form.add_error(None, "Este cartão já está cadastrado com essa validade.")
            else:
                default = data["is_default"] or not request.user.saved_cards.usable().filter(is_default=True).exists()
                if default:
                    request.user.saved_cards.update(is_default=False)
                card = SavedCard.objects.create(
                    user=request.user, holder_name=data["holder_name"], **data["number"],
                    expiry_month=data["expiry_month"], expiry_year=data["expiry_year"], is_default=default,
                )
                messages.success(request, "Cartão de teste cadastrado com sucesso.")
                destination = reverse("accounts:cards")
                if request.GET.get("checkout") == "1":
                    destination += "?checkout=1"
                return redirect(f"{destination}#card-{card.pk}")
    return render(request, "accounts/cards.html", {"form": form, "cards": request.user.saved_cards.all(), "from_checkout": request.GET.get("checkout") == "1"})


@never_cache
@login_required
@require_POST
def card_default(request, pk):
    with transaction.atomic():
        get_user_model().objects.select_for_update().get(pk=request.user.pk)
        card = get_object_or_404(request.user.saved_cards.usable(), pk=pk)
        request.user.saved_cards.update(is_default=False)
        card.is_default = True
        card.save(update_fields=["is_default"])
    messages.success(request, "Cartão padrão atualizado.")
    return redirect("accounts:cards")


@never_cache
@login_required
@require_POST
def card_delete(request, pk):
    with transaction.atomic():
        get_user_model().objects.select_for_update().get(pk=request.user.pk)
        card = get_object_or_404(request.user.saved_cards, pk=pk)
        was_default = card.is_default
        card.delete()
        if was_default:
            next_card = request.user.saved_cards.usable().first()
            if next_card:
                next_card.is_default = True
                next_card.save(update_fields=["is_default"])
    messages.success(request, "Cartão removido.")
    return redirect("accounts:cards")
