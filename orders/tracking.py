from datetime import timedelta

from django.utils import timezone

from .models import Order


DELIVERY_STEPS = [
    (Order.Status.PENDING, "Pedido recebido", "receipt_long"),
    (Order.Status.CONFIRMED, "Confirmado", "task_alt"),
    (Order.Status.PREPARING, "Em preparo", "skillet"),
    (Order.Status.READY, "Pronto para sair", "shopping_bag"),
    (Order.Status.DISPATCHED, "Saiu para entrega", "moped"),
    (Order.Status.DELIVERED, "Entregue", "home"),
]
STATUS_MESSAGES = {
    Order.Status.PENDING: "Recebemos seu pedido. Aguarde a confirmação da loja.",
    Order.Status.CONFIRMED: "Pedido confirmado! Logo começaremos o preparo.",
    Order.Status.PREPARING: "Estamos preparando seu pedido com carinho.",
    Order.Status.READY: "Tudo pronto! Seu pedido aguarda a saída para entrega.",
    Order.Status.DISPATCHED: "Seu pedido está a caminho do endereço informado.",
    Order.Status.DELIVERED: "Entrega concluída. Bom apetite!",
    Order.Status.CANCELLED: "Este pedido foi cancelado. A entrega não será realizada.",
}


def tracking_context(order):
    history = list(order.history.all())
    codes = [code for code, _, _ in DELIVERY_STEPS]
    cancelled = order.status == Order.Status.CANCELLED
    terminal = cancelled or order.status == Order.Status.DELIVERED
    current = codes.index(order.status) if not cancelled else -1
    steps = []
    for index, (code, label, icon) in enumerate(DELIVERY_STEPS):
        occurred = next((entry.created_at for entry in history if entry.status == code), None)
        if code == Order.Status.PENDING:
            occurred = occurred or order.created_at
        steps.append({
            "label": label, "icon": icon, "time": occurred,
            "state": "current" if index == current else "complete" if index < current else "upcoming",
        })
    estimate = order.created_at + timedelta(minutes=order.estimated_delivery_minutes)
    next_status = codes[current + 1] if not terminal else None
    return {
        "order": order, "steps": steps, "terminal": terminal,
        "tracking_message": STATUS_MESSAGES[order.status],
        "estimated_at": estimate, "delayed": not terminal and timezone.now() > estimate,
        "delivery_history": [entry for entry in history if not entry.payment_status],
        "next_status": next_status,
        "next_label": dict(Order.Status.choices).get(next_status),
    }
