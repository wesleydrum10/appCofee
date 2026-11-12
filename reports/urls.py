from django.urls import path

from . import views

app_name = "reports"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("produtos/", views.product_list, name="products"),
    path("produtos/novo/", views.product_edit, name="product_create"),
    path("produtos/<int:pk>/", views.product_edit, name="product_edit"),
    path("funcionarios/", views.employee_list, name="employees"),
    path("funcionarios/novo/", views.employee_edit, name="employee_create"),
    path("funcionarios/<int:pk>/", views.employee_edit, name="employee_edit"),
    path("categorias/", views.category_list, name="categories"),
    path("categorias/nova/", views.category_edit, name="category_create"),
    path("categorias/<int:pk>/", views.category_edit, name="category_edit"),
    path("despesas/", views.expense_list, name="expenses"),
    path("despesas/nova/", views.expense_edit, name="expense_create"),
    path("despesas/<int:pk>/", views.expense_edit, name="expense_edit"),
    path("despesas/<int:pk>/excluir/", views.expense_delete, name="expense_delete"),
    path("pedidos/", views.order_list, name="orders"),
    path("configuracoes/pagamentos/", views.payment_settings, name="payment_settings"),
    path("cupons/", views.coupon_list, name="coupons"),
    path("cupons/novo/", views.coupon_edit, name="coupon_create"),
    path("cupons/<int:pk>/", views.coupon_edit, name="coupon_edit"),
    path("feedbacks/", views.feedback_list, name="feedbacks"),
    path("feedbacks/<int:pk>/visibilidade/", views.feedback_visibility, name="feedback_visibility"),
]
