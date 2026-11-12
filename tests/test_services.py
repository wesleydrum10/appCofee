from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from cart.models import Cart
from cart.services import CartLimitExceeded, CartService
from catalog.models import Addon, Category, Product, ProductAddon
from coupons.models import Coupon, CouponUsage
from coupons.services import CouponService


class ServiceRulesTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(email="cliente@test.com", password="123456", cpf="12345678900")
        self.category = Category.objects.create(name="Cupcakes")
        self.product = Product.objects.create(
            category=self.category,
            name="Cupcake Teste",
            description="Produto de teste",
            price=Decimal("10.00"),
        )
        self.addon = Addon.objects.create(name="Ganache", kind=Addon.Kind.TOPPING, price=Decimal("2.50"))
        ProductAddon.objects.create(product=self.product, addon=self.addon)
        self.cart = Cart.objects.create(user=self.user)

    def test_price_with_addons(self):
        item = CartService.add_product(self.cart, self.product, quantity=2, addon_ids=[self.addon.id])
        self.assertEqual(item.subtotal, Decimal("25.00"))

    def test_cart_limit_50_items(self):
        CartService.add_product(self.cart, self.product, quantity=50)
        with self.assertRaises(CartLimitExceeded):
            CartService.add_product(self.cart, self.product, quantity=1)

    def test_valid_coupon(self):
        coupon = Coupon.objects.create(
            code="CUPOM10",
            discount_type=Coupon.DiscountType.PERCENT,
            value=Decimal("10.00"),
            minimum_order_value=Decimal("20.00"),
            starts_at=timezone.now() - timedelta(days=1),
            expires_at=timezone.now() + timedelta(days=1),
            is_active=True,
        )
        result = CouponService.validate(coupon.code, self.user, Decimal("50.00"))
        self.assertTrue(result.valid)
        self.assertEqual(result.discount, Decimal("5.00"))

    def test_invalid_coupon_minimum(self):
        coupon = Coupon.objects.create(
            code="ALTO",
            discount_type=Coupon.DiscountType.FIXED,
            value=Decimal("5.00"),
            minimum_order_value=Decimal("100.00"),
            starts_at=timezone.now() - timedelta(days=1),
            expires_at=timezone.now() + timedelta(days=1),
            is_active=True,
        )
        result = CouponService.validate(coupon.code, self.user, Decimal("50.00"))
        self.assertFalse(result.valid)

    def test_duplicate_coupon_for_user(self):
        coupon = Coupon.objects.create(
            code="UNICO",
            discount_type=Coupon.DiscountType.FIXED,
            value=Decimal("5.00"),
            minimum_order_value=Decimal("0.00"),
            starts_at=timezone.now() - timedelta(days=1),
            expires_at=timezone.now() + timedelta(days=1),
            is_active=True,
        )
        CouponUsage.objects.create(coupon=coupon, user=self.user, discount_amount=Decimal("5.00"))
        result = CouponService.validate(coupon.code, self.user, Decimal("50.00"))
        self.assertFalse(result.valid)
