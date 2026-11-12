from django.urls import path

from . import views

app_name = "reviews"

urlpatterns = [
    path("loja/", views.store, name="store"),
    path("<str:number>/", views.create, name="create"),
]
