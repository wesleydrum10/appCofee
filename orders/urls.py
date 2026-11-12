from django.urls import path

from . import views

app_name = "orders"

urlpatterns = [
    path("", views.checkout, name="checkout"),
    path("criar/", views.create, name="create"),
    path("pedidos/", views.order_list, name="list"),
    path("pedidos/<str:number>/", views.detail, name="detail"),
]
