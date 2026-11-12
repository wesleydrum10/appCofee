from catalog.models import Category, Product
from django.shortcuts import render
from django.db.models import Avg, Count
from reviews.models import StoreFeedback


def home(request):
    products = (
        Product.objects.available()
        .select_related("category")
        .prefetch_related("allergens")
        .order_by("-created_at")[:8]
    )
    categories = Category.objects.filter(is_active=True)
    feedbacks = StoreFeedback.objects.filter(is_public=True).select_related("user")
    return render(request, "core/home.html", {
        "products": products, "categories": categories, "feedbacks": feedbacks[:6],
        "feedback_summary": feedbacks.aggregate(average=Avg("rating"), total=Count("pk")),
    })
