from django.http import HttpResponse, JsonResponse
from django.template.loader import render_to_string
from django.templatetags.static import static
from django.urls import reverse
from django.views.decorators.http import require_GET


@require_GET
def manifest(request):
    response = JsonResponse({
        "id": "/", "name": "Veludo & Grão — Café artesanal", "short_name": "Veludo & Grão",
        "description": "Cafés especiais, cupcakes e acompanhamento dos seus pedidos.",
        "lang": "pt-BR", "dir": "ltr", "start_url": "/", "scope": "/",
        "display": "standalone", "background_color": "#fcf9f4", "theme_color": "#2b1e1a",
        "categories": ["food", "shopping"],
        "icons": [
            {"src": static(f"icons/icon-{size}.png"), "sizes": f"{size}x{size}", "type": "image/png", "purpose": "any"}
            for size in (192, 512)
        ] + [
            {"src": static(f"icons/icon-maskable-{size}.png"), "sizes": f"{size}x{size}", "type": "image/png", "purpose": "maskable"}
            for size in (192, 512)
        ],
        "shortcuts": [
            {"name": "Cardápio", "url": reverse("catalog:product_list")},
            {"name": "Meus pedidos", "url": reverse("orders:list")},
        ],
    }, content_type="application/manifest+json")
    response["Cache-Control"] = "public, max-age=3600"
    return response


@require_GET
def service_worker(request):
    response = HttpResponse(render_to_string("core/service-worker.js"), content_type="application/javascript")
    response["Cache-Control"] = "no-cache"
    response["Service-Worker-Allowed"] = "/"
    return response


@require_GET
def offline(request):
    # No request context: this cached page must never include account or cart data.
    return HttpResponse(render_to_string("core/offline.html"))
