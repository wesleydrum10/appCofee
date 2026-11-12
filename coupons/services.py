from dataclasses import dataclass
from decimal import Decimal

from django.db.models import Count

from .models import Coupon


@dataclass(frozen=True)
class CouponResult:
    valid: bool
    message: str
    discount: Decimal = Decimal("0.00")
    coupon: Coupon | None = None


class CouponService:
    @staticmethod
    def validate(code: str, user, subtotal: Decimal) -> CouponResult:
        normalized = code.strip().upper()
        if not normalized:
            return CouponResult(False, "Informe um cupom.")
        try:
            coupon = Coupon.objects.annotate(total_usages=Count("usages")).get(code__iexact=normalized)
        except Coupon.DoesNotExist:
            return CouponResult(False, "Cupom não encontrado.")
        if not coupon.is_valid_now():
            return CouponResult(False, "Cupom expirado ou inativo.", coupon=coupon)
        if subtotal < coupon.minimum_order_value:
            return CouponResult(False, f"Pedido mínimo de R$ {coupon.minimum_order_value}.", coupon=coupon)
        if coupon.usage_limit and coupon.total_usages >= coupon.usage_limit:
            return CouponResult(False, "Cupom atingiu o limite de uso.", coupon=coupon)
        if user.is_authenticated:
            user_count = coupon.usages.filter(user=user).count()
            if user_count >= coupon.usage_limit_per_user:
                return CouponResult(False, "Você já utilizou este cupom.", coupon=coupon)
        discount = CouponService.calculate_discount(coupon, subtotal)
        return CouponResult(True, "Cupom aplicado.", discount=discount, coupon=coupon)

    @staticmethod
    def calculate_discount(coupon: Coupon, subtotal: Decimal) -> Decimal:
        if coupon.discount_type == Coupon.DiscountType.PERCENT:
            return min(subtotal, (subtotal * coupon.value / Decimal("100")).quantize(Decimal("0.01")))
        return min(subtotal, coupon.value)
