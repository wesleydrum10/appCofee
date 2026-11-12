from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from orders.models import Order, OrderItem
from payments.models import Payment
from .models import Expense


class FinancialReportService:
    @staticmethod
    def summarize(start_date=None, end_date=None):
        orders = Order.objects.filter(payment__status=Payment.Status.APPROVED).exclude(status=Order.Status.CANCELLED)
        placed_orders = Order.objects.exclude(status=Order.Status.CANCELLED)
        expenses = Expense.objects.all()
        if start_date:
            orders = orders.filter(payment__updated_at__date__gte=start_date)
            placed_orders = placed_orders.filter(created_at__date__gte=start_date)
            expenses = expenses.filter(paid_on__gte=start_date)
        if end_date:
            orders = orders.filter(payment__updated_at__date__lte=end_date)
            placed_orders = placed_orders.filter(created_at__date__lte=end_date)
            expenses = expenses.filter(paid_on__lte=end_date)
        totals = orders.aggregate(
            gross=Sum("subtotal"),
            discounts=Sum("discount"),
            delivery=Sum("delivery_fee"),
            net=Sum("payment__amount"),
            quantity=Count("id"),
        )
        quantity = totals["quantity"] or 0
        net = totals["net"] or Decimal("0.00")
        expense_total = expenses.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
        placed_totals = placed_orders.aggregate(quantity=Count("id"), total=Sum("total"))
        pending_totals = placed_orders.filter(Q(payment__status=Payment.Status.PENDING) | Q(payment__isnull=True)).aggregate(quantity=Count("id"), total=Sum("total"))
        top_products = (
            OrderItem.objects.filter(order__in=placed_orders)
            .values("product_name", "product__image")
            .annotate(quantity=Sum("quantity"), revenue=Sum("subtotal"))
            .order_by("-quantity")[:10]
        )
        return {
            "gross": totals["gross"] or Decimal("0.00"),
            "discounts": totals["discounts"] or Decimal("0.00"),
            "delivery": totals["delivery"] or Decimal("0.00"),
            "net": net,
            "expenses": expense_total,
            "balance": net - expense_total,
            "quantity": quantity,
            "placed_quantity": placed_totals["quantity"],
            "placed_total": placed_totals["total"] or Decimal("0.00"),
            "pending_quantity": pending_totals["quantity"],
            "pending_total": pending_totals["total"] or Decimal("0.00"),
            "average_ticket": net / quantity if quantity else Decimal("0.00"),
            "top_products": top_products,
        }

    @staticmethod
    def cashflow(start_date=None, end_date=None):
        end = end_date or timezone.localdate()
        start = max(start_date or end - timedelta(days=6), end - timedelta(days=6))
        receipts = dict(
            Payment.objects.filter(status=Payment.Status.APPROVED, updated_at__date__range=(start, end))
            .exclude(order__status=Order.Status.CANCELLED)
            .annotate(day=TruncDate("updated_at")).values("day")
            .annotate(total=Sum("amount")).values_list("day", "total")
        )
        expenses = dict(Expense.objects.filter(paid_on__range=(start, end)).values("paid_on").annotate(total=Sum("amount")).values_list("paid_on", "total"))
        placed = dict(Order.objects.filter(created_at__date__range=(start, end)).exclude(status=Order.Status.CANCELLED).annotate(day=TruncDate("created_at")).values("day").annotate(total=Sum("total")).values_list("day", "total"))
        days = []
        for offset in range((end - start).days + 1):
            day = start + timedelta(days=offset)
            days.append({"date": day, "receipt": receipts.get(day, Decimal("0")), "expense": expenses.get(day, Decimal("0")), "placed": placed.get(day, Decimal("0"))})
        maximum = max((max(day["receipt"], day["expense"], day["placed"]) for day in days), default=0) or 1
        for day in days:
            day["receipt_height"] = float(day["receipt"] / maximum * 100)
            day["expense_height"] = float(day["expense"] / maximum * 100)
            day["placed_height"] = float(day["placed"] / maximum * 100)
        return days
