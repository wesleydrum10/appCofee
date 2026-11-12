from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Avg, Count
from django.shortcuts import get_object_or_404, redirect
from django.shortcuts import render
from django.contrib.auth.views import redirect_to_login
from django.views.decorators.http import require_POST, require_http_methods

from orders.models import Order
from .models import Review, StoreFeedback
from .forms import StoreFeedbackForm


@require_http_methods(["GET", "POST"])
def store(request):
    can_publish = request.user.is_authenticated and request.user.role == "CLIENT" and not request.user.is_manager
    own_feedback = StoreFeedback.objects.filter(user=request.user).first() if can_publish else None
    if request.method == "POST":
        if not request.user.is_authenticated:
            return redirect_to_login(request.path, settings.LOGIN_URL)
        if not can_publish:
            raise PermissionDenied
    form = StoreFeedbackForm(request.POST if request.method == "POST" else None, instance=own_feedback)
    if request.method == "POST" and form.is_valid():
        StoreFeedback.objects.update_or_create(user=request.user, defaults=form.cleaned_data)
        messages.success(request, "Feedback atualizado." if own_feedback else "Feedback publicado. Obrigado pela avaliação!")
        return redirect("reviews:store")
    feedbacks = StoreFeedback.objects.filter(is_public=True).select_related("user")
    return render(request, "reviews/store.html", {
        "page": Paginator(feedbacks, 12).get_page(request.GET.get("page")),
        "summary": feedbacks.aggregate(average=Avg("rating"), total=Count("pk")),
        "form": form, "can_publish": can_publish, "own_feedback": own_feedback,
    })


@login_required
@require_POST
def create(request, number):
    order = get_object_or_404(Order, number=number, user=request.user)
    review = Review(user=request.user, order=order, rating=request.POST.get("rating", 5), comment=request.POST.get("comment", ""))
    review.full_clean()
    review.save()
    messages.success(request, "Avaliação registrada. Obrigado pelo retorno.")
    return redirect("orders:detail", number=order.number)
