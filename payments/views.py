from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.utils import timezone

from .models import Payment, PaymentSettings
from .services import PAYMENT_MESSAGES, PaymentService


class SimulationForm(forms.Form):
    idempotency_key = forms.UUIDField()
    retry = forms.BooleanField(required=False)


def health(request):
    return JsonResponse({"ok": True})


@login_required
@require_POST
def simulate(request, number):
    payment = get_object_or_404(Payment.objects.select_related("order"), order__number=number, order__user=request.user)
    form = SimulationForm(request.POST)
    wants_json = request.headers.get("accept") == "application/json"
    try:
        if not form.is_valid():
            raise ValueError("Tentativa de pagamento inválida. Atualize a página e tente novamente.")
        payment = PaymentService.simulate(payment, form.cleaned_data["idempotency_key"], form.cleaned_data["retry"])
    except ValueError as exc:
        if wants_json:
            return JsonResponse({"ok": False, "message": str(exc), "simulation_enabled": PaymentSettings.current().simulation_enabled}, status=400)
        messages.error(request, str(exc))
        return redirect("orders:detail", number=number)
    message = PAYMENT_MESSAGES[payment.status]
    if wants_json:
        payment.order.refresh_from_db()
        entry = payment.order.history.exclude(payment_status="").order_by("created_at", "id").last()
        timeline_entry = {"id": entry.pk, "status": entry.payment_status, "label": entry.event_label, "note": entry.note, "date": timezone.localtime(entry.created_at).strftime("%d/%m/%Y %H:%M")} if entry else None
        return JsonResponse({"ok": True, "status": payment.status, "status_label": payment.get_status_display(), "message": message, "order_status": payment.order.get_status_display(), "timeline_entry": timeline_entry, "detail_url": reverse("orders:detail", kwargs={"number": number})})
    if payment.status == Payment.Status.APPROVED:
        messages.success(request, message)
    elif payment.status == Payment.Status.DECLINED:
        messages.error(request, message)
    else:
        messages.info(request, message)
    return redirect("orders:detail", number=number)
