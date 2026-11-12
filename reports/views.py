import csv
from datetime import timedelta
from functools import wraps

from django.contrib import messages
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count, F, Q
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.utils import timezone

from accounts.models import User
from catalog.models import Category, Product
from inventory.models import InventoryItem
from orders.models import Order
from orders.services import OrderService
from orders.tracking import tracking_context
from .forms import DeliveryUpdateForm
from .forms import CategoryForm, EmployeeEditForm, EmployeeForm, ExpenseForm, PaymentSettingsForm, PeriodForm, ProductForm
from payments.models import PaymentSettings
from coupons.models import Coupon
from coupons.forms import CouponForm
from reviews.models import StoreFeedback
from .models import Expense
from .services import FinancialReportService


def manager_required(view):
    @login_required
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_active or not request.user.is_manager:
            raise PermissionDenied
        return view(request, *args, **kwargs)
    return wrapped


@manager_required
def feedback_list(request):
    feedbacks = StoreFeedback.objects.select_related("user")
    return render(request, "reports/feedbacks.html", {
        "section": "feedbacks", "page": Paginator(feedbacks, 20).get_page(request.GET.get("page")),
    })


@manager_required
@require_POST
def feedback_visibility(request, pk):
    feedback = get_object_or_404(StoreFeedback, pk=pk)
    if request.POST.get("is_public") not in {"0", "1"}:
        messages.error(request, "Situação inválida.")
    else:
        feedback.is_public = request.POST["is_public"] == "1"
        feedback.save(update_fields=["is_public"])
        messages.success(request, "Feedback publicado." if feedback.is_public else "Feedback ocultado.")
    return redirect("reports:feedbacks")


@manager_required
def dashboard(request):
    today = timezone.localdate()
    period = request.GET.get("period", "custom")
    data = request.GET.copy()
    if period in {"today", "week", "month"}:
        data["start"] = {"today": today, "week": today - timedelta(days=6), "month": today.replace(day=1)}[period].isoformat()
        data["end"] = today.isoformat()
    form = PeriodForm(data)
    summary = FinancialReportService.summarize(
        form.cleaned_data.get("start"), form.cleaned_data.get("end"),
    ) if form.is_valid() else None
    if request.GET.get("export") == "csv" and summary is not None:
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="financeiro.csv"'
        response.write("\ufeff")
        writer = csv.writer(response, delimiter=";")
        writer.writerow(["Indicador", "Valor"])
        for label, key in [("Pedidos realizados", "placed_quantity"), ("Valor dos pedidos", "placed_total"), ("Pedidos aguardando pagamento", "pending_quantity"), ("A receber", "pending_total"), ("Recebimentos", "net"), ("Despesas", "expenses"), ("Saldo", "balance"), ("Pedidos pagos", "quantity"), ("Ticket médio", "average_ticket"), ("Descontos", "discounts")]:
            writer.writerow([label, summary[key]])
        return response
    low_stock = list(InventoryItem.objects.filter(quantity_on_hand__lte=F("minimum_quantity")).select_related("ingredient")[:10])
    for item in low_stock:
        item.stock_percent = float(min(item.quantity_on_hand / item.minimum_quantity * 100, 100)) if item.minimum_quantity else 0
    low_products = list(Product.objects.filter(is_active=True, stock_quantity__isnull=False, stock_quantity__lte=F("minimum_stock")))
    for product in low_products:
        product.stock_percent = float(min(product.stock_quantity / product.minimum_stock * 100, 100)) if product.minimum_stock else 0
    return render(request, "reports/dashboard.html", {
        "summary": summary, "form": form, "section": "finance",
        "low_stock": low_stock, "period": period, "media_url": settings.MEDIA_URL,
        "low_products": low_products, "stock_alert_count": len(low_stock) + len(low_products),
        "cashflow": FinancialReportService.cashflow(form.cleaned_data.get("start"), form.cleaned_data.get("end")) if summary is not None else [],
    })


@manager_required
def product_list(request):
    products = Product.objects.select_related("category")
    query = request.GET.get("q", "").strip()
    if query:
        products = products.filter(Q(name__icontains=query) | Q(category__name__icontains=query))
    return render(request, "reports/products.html", {"section": "products", "page": Paginator(products, 20).get_page(request.GET.get("page")), "query": query})


@manager_required
def product_edit(request, pk=None):
    product = get_object_or_404(Product, pk=pk) if pk else None
    form = ProductForm(request.POST if request.method == "POST" else None, request.FILES or None, instance=product)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Produto salvo.")
        return redirect("reports:products")
    return render(request, "reports/form.html", {"form": form, "title": "Editar produto" if pk else "Novo produto", "section": "products", "back": "reports:products"})


@manager_required
def employee_list(request):
    employees = User.objects.filter(role__in=[User.Role.STAFF, User.Role.MANAGER]).order_by("first_name", "email")
    return render(request, "reports/employees.html", {"section": "employees", "page": Paginator(employees, 20).get_page(request.GET.get("page"))})


@manager_required
def employee_edit(request, pk=None):
    employee = get_object_or_404(User, pk=pk, role__in=[User.Role.STAFF, User.Role.MANAGER]) if pk else None
    if employee and employee.is_superuser and not request.user.is_superuser:
        raise PermissionDenied
    original_role = employee.role if employee else None
    form_class = EmployeeEditForm if employee else EmployeeForm
    form = form_class(request.POST if request.method == "POST" else None, instance=employee)
    if request.method == "POST" and form.is_valid():
        if employee and employee.pk == request.user.pk and (not form.cleaned_data["is_active"] or form.cleaned_data["role"] != original_role):
            form.add_error(None, "Você não pode desativar ou alterar seu próprio cargo.")
        else:
            form.save()
            messages.success(request, "Funcionário salvo.")
            return redirect("reports:employees")
    return render(request, "reports/form.html", {"form": form, "title": "Editar funcionário" if pk else "Novo funcionário", "section": "employees", "back": "reports:employees"})


@manager_required
def category_list(request):
    return render(request, "reports/categories.html", {"section": "categories", "page": Paginator(Category.objects.all(), 20).get_page(request.GET.get("page"))})


@manager_required
def category_edit(request, pk=None):
    category = get_object_or_404(Category, pk=pk) if pk else None
    form = CategoryForm(request.POST if request.method == "POST" else None, instance=category)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Categoria salva.")
        return redirect("reports:categories")
    return render(request, "reports/form.html", {"form": form, "title": "Editar categoria" if pk else "Nova categoria", "section": "categories", "back": "reports:categories"})


@manager_required
def expense_list(request):
    return render(request, "reports/expenses.html", {"section": "expenses", "page": Paginator(Expense.objects.all(), 20).get_page(request.GET.get("page"))})


@manager_required
def expense_edit(request, pk=None):
    expense = get_object_or_404(Expense, pk=pk) if pk else None
    form = ExpenseForm(request.POST if request.method == "POST" else None, instance=expense)
    if request.method == "POST" and form.is_valid():
        expense = form.save(commit=False)
        if not expense.pk:
            expense.created_by = request.user
        expense.save()
        messages.success(request, "Despesa salva.")
        return redirect("reports:expenses")
    return render(request, "reports/form.html", {"form": form, "title": "Editar despesa" if pk else "Nova despesa", "section": "expenses", "back": "reports:expenses"})


@manager_required
@require_POST
def expense_delete(request, pk):
    get_object_or_404(Expense, pk=pk).delete()
    messages.success(request, "Despesa excluída.")
    return redirect("reports:expenses")


@manager_required
def order_list(request):
    orders = Order.objects.select_related("user", "payment")
    status = request.GET.get("status", "")
    if status in Order.Status.values:
        orders = orders.filter(status=status)
    return render(request, "reports/orders.html", {"section": "orders", "page": Paginator(orders, 20).get_page(request.GET.get("page")), "statuses": Order.Status.choices, "status": status})


@manager_required
def order_delivery(request, number):
    order = get_object_or_404(Order.objects.select_related("user").prefetch_related("history"), number=number)
    form = DeliveryUpdateForm(request.POST if request.method == "POST" else None, order=order)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            locked = Order.objects.select_for_update().get(pk=order.pk)
            if locked.status != form.cleaned_data["expected_status"]:
                form.add_error(None, "O pedido foi atualizado por outra pessoa. Recarregue a página antes de continuar.")
            else:
                try:
                    OrderService.change_status(locked, form.cleaned_data["status"], user=request.user, note=form.cleaned_data["note"])
                except ValueError as exc:
                    form.add_error(None, str(exc))
                else:
                    messages.success(request, "Etapa da entrega atualizada. O cliente já pode acompanhar a mudança.")
                    return redirect("reports:order_delivery", number=number)
    return render(request, "reports/order_delivery.html", {
        **tracking_context(order), "section": "orders", "form": form,
    })


@manager_required
def payment_settings(request):
    configuration = PaymentSettings.current()
    form = PaymentSettingsForm(request.POST if request.method == "POST" else None, instance=configuration)
    if request.method == "POST" and form.is_valid():
        configuration = form.save()
        messages.success(request, "Simulação de pagamentos ativada." if configuration.simulation_enabled else "Simulação de pagamentos desativada.")
        return redirect("reports:payment_settings")
    return render(request, "reports/payment_settings.html", {"form": form, "configuration": configuration, "section": "settings"})


@manager_required
def coupon_list(request):
    coupons = Coupon.objects.annotate(total_usages=Count("usages")).order_by("code", "pk")
    query = request.GET.get("q", "").strip()
    if query:
        coupons = coupons.filter(Q(code__icontains=query) | Q(description__icontains=query))
    page = Paginator(coupons, 20).get_page(request.GET.get("page"))
    now = timezone.now()
    for coupon in page:
        if not coupon.is_active:
            coupon.state, coupon.state_label = "INACTIVE", "Inativo"
        elif coupon.expires_at < now:
            coupon.state, coupon.state_label = "EXPIRED", "Expirado"
        elif coupon.starts_at > now:
            coupon.state, coupon.state_label = "SCHEDULED", "Agendado"
        elif coupon.usage_limit is not None and coupon.total_usages >= coupon.usage_limit:
            coupon.state, coupon.state_label = "LIMIT_REACHED", "Limite atingido"
        else:
            coupon.state, coupon.state_label = "ACTIVE", "Ativo"
    return render(request, "reports/coupons.html", {"section": "coupons", "page": page, "query": query})


@manager_required
def coupon_edit(request, pk=None):
    coupon = get_object_or_404(Coupon, pk=pk) if pk else None
    form = CouponForm(request.POST if request.method == "POST" else None, instance=coupon)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Cupom salvo.")
        return redirect("reports:coupons")
    return render(request, "reports/form.html", {"form": form, "title": "Editar cupom" if pk else "Novo cupom", "section": "coupons", "back": "reports:coupons"})
