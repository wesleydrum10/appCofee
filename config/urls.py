from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("core.urls")),
    path("conta/", include("accounts.urls")),
    path("produtos/", include("catalog.urls")),
    path("carrinho/", include("cart.urls")),
    path("checkout/", include("orders.urls")),
    path("pagamentos/", include("payments.urls")),
    path("avaliacoes/", include("reviews.urls")),
    path("dashboard/", include("reports.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
