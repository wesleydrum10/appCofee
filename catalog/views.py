from django.db.models import Prefetch, Q
from django.shortcuts import get_object_or_404, render

from .models import Addon, Category, Product


def product_list(request):
    query = request.GET.get("q", "").strip()
    category_slug = request.GET.get("categoria", "").strip()
    products = Product.objects.available().select_related("category").prefetch_related("allergens")
    categories = Category.objects.filter(is_active=True)
    selected_category = None
    if query:
        products = products.filter(Q(name__icontains=query) | Q(description__icontains=query))
    if category_slug:
        selected_category = get_object_or_404(Category, slug=category_slug, is_active=True)
        products = products.filter(category=selected_category)
    return render(
        request,
        "catalog/product_list.html",
        {"products": products, "categories": categories, "query": query, "selected_category": selected_category},
    )


def product_detail(request, slug):
    product = get_object_or_404(
        Product.objects.available()
        .select_related("category")
        .prefetch_related(
            "ingredients",
            "allergens",
            Prefetch("addons", queryset=Addon.objects.filter(is_active=True)),
        ),
        slug=slug,
    )
    return render(request, "catalog/product_detail.html", {"product": product})
