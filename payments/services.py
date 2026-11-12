from secrets import choice

from django.db import transaction

from orders.models import Order, OrderStatusHistory
from .models import Payment, PaymentAttempt, PaymentSettings


PAYMENT_MESSAGES = {
    Payment.Status.APPROVED: "Pagamento aprovado. Seu pedido foi confirmado!",
    Payment.Status.PENDING: "Pagamento pendente. A confirmação ainda não foi recebida. Consulte novamente em instantes.",
    Payment.Status.DECLINED: "Pagamento recusado. Nenhum valor foi recebido. Você pode tentar novamente.",
}


class PaymentService:
    @staticmethod
    @transaction.atomic
    def simulate(payment, idempotency_key, retry=False):
        configuration, _ = PaymentSettings.objects.select_for_update().get_or_create(pk=1)
        if not configuration.simulation_enabled:
            raise ValueError("A simulação de pagamentos está desativada. O pagamento aguarda confirmação da loja.")
        order = Order.objects.select_for_update().get(pk=payment.order_id)
        payment = Payment.objects.select_for_update().get(pk=payment.pk)
        if payment.method == Payment.Method.CASH:
            raise ValueError("Dinheiro é recebido na entrega.")
        if order.status == Order.Status.CANCELLED or payment.status == Payment.Status.REFUNDED:
            raise ValueError("Este pagamento não pode ser processado.")
        previous = PaymentAttempt.objects.filter(idempotency_key=idempotency_key).first()
        if previous and previous.payment_id != payment.pk:
            raise ValueError("Tentativa de pagamento inválida.")
        if previous or payment.status == Payment.Status.APPROVED or (not retry and payment.attempts.exists()):
            return payment
        payment.status = choice([Payment.Status.APPROVED, Payment.Status.PENDING, Payment.Status.DECLINED])
        attempt = PaymentAttempt.objects.create(payment=payment, idempotency_key=idempotency_key, status=payment.status)
        payment.gateway_reference = f"SIM-{attempt.pk}"
        payment.save(update_fields=["status", "gateway_reference", "updated_at"])
        if payment.status == Payment.Status.APPROVED and order.status == Order.Status.PENDING:
            order.status = Order.Status.CONFIRMED
            order.save(update_fields=["status", "updated_at"])
        OrderStatusHistory.objects.create(order=order, status=order.status, payment_status=payment.status, user=order.user, note=f"Pagamento simulado: {payment.get_status_display()}.")
        return payment
