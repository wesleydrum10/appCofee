from django.urls import path

from . import views
from payments import card_views

app_name = "accounts"

urlpatterns = [
    path("cadastro/", views.signup, name="signup"),
    path("login/", views.EmailLoginView.as_view(), name="login"),
    path("logout/", views.AccountLogoutView.as_view(), name="logout"),
    path("recuperar-senha/", views.AccountPasswordResetView.as_view(), name="password_reset"),
    path("", views.profile, name="profile"),
    path("enderecos/", views.address_list, name="addresses"),
    path("cartoes/", card_views.cards, name="cards"),
    path("cartoes/<int:pk>/padrao/", card_views.card_default, name="card_default"),
    path("cartoes/<int:pk>/remover/", card_views.card_delete, name="card_delete"),
]
