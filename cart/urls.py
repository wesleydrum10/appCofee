from django.urls import path

from . import views

app_name = "cart"

urlpatterns = [
    path("", views.detail, name="detail"),
    path("resumo/", views.summary, name="summary"),
    path("adicionar/<int:product_id>/", views.add, name="add"),
    path("item/<int:item_id>/", views.update, name="update"),
    path("cupom/", views.apply_coupon, name="apply_coupon"),
    path("limpar/", views.clear, name="clear"),
]
