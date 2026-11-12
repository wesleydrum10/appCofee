from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from .models import Coupon
from .services import CouponService


class CouponManagementTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user("coupons-manager@test.com", "coffee-test!42", role=User.Role.MANAGER)
        self.customer = User.objects.create_user("coupons-customer@test.com", "coffee-test!42")
        self.client.force_login(self.manager)
        self.data = {
            "code": "cafe10", "description": "Oferta", "discount_type": Coupon.DiscountType.PERCENT,
            "value": "10", "minimum_order_value": "20", "usage_limit": "100", "usage_limit_per_user": "1", "is_active": "on",
            "starts_at": timezone.localtime(timezone.now()-timedelta(days=1)).strftime("%Y-%m-%dT%H:%M"),
            "expires_at": timezone.localtime(timezone.now()+timedelta(days=1)).strftime("%Y-%m-%dT%H:%M"),
        }

    def test_create_coupon_and_apply_it_to_customer_order(self):
        self.assertEqual(self.client.get(reverse("reports:coupon_create")).status_code, 200)
        response = self.client.post(reverse("reports:coupon_create"), self.data)
        self.assertRedirects(response, reverse("reports:coupons"))
        coupon = Coupon.objects.get()
        self.assertEqual(coupon.code, "CAFE10")
        result = CouponService.validate("cafe10", self.customer, Decimal("50"))
        self.assertTrue(result.valid)
        self.assertEqual(result.discount, Decimal("5.00"))
        self.assertContains(self.client.get(reverse("reports:coupons")), "CAFE10")

    def test_edit_fixed_discount_and_deactivate_preserves_coupon(self):
        self.client.post(reverse("reports:coupon_create"), self.data)
        coupon = Coupon.objects.get()
        response = self.client.post(reverse("reports:coupon_edit", args=[coupon.pk]), {**self.data, "discount_type": Coupon.DiscountType.FIXED, "value": "8", "is_active": ""})
        self.assertRedirects(response, reverse("reports:coupons"))
        coupon.refresh_from_db()
        self.assertFalse(coupon.is_active)
        self.assertEqual(coupon.value, Decimal("8"))
        self.assertEqual(Coupon.objects.count(), 1)
        self.assertFalse(CouponService.validate(coupon.code, self.customer, Decimal("50")).valid)

    def test_invalid_values_dates_and_duplicate_code_are_rejected(self):
        for change, field in [({"value": "101"}, "value"), ({"minimum_order_value": "-1"}, "minimum_order_value"), ({"expires_at": self.data["starts_at"]}, "expires_at"), ({"usage_limit": "0"}, "usage_limit"), ({"usage_limit_per_user": "0"}, "usage_limit_per_user"), ({"code": "invalid code"}, "code")]:
            response = self.client.post(reverse("reports:coupon_create"), {**self.data, **change})
            self.assertEqual(response.status_code, 200)
            self.assertIn(field, response.context["form"].errors)
        self.assertFalse(Coupon.objects.exists())
        self.client.post(reverse("reports:coupon_create"), self.data)
        response = self.client.post(reverse("reports:coupon_create"), {**self.data, "code": "CaFe10"})
        self.assertIn("code", response.context["form"].errors)
        self.assertEqual(Coupon.objects.count(), 1)

    def test_client_and_staff_cannot_access_coupon_management(self):
        for role in [User.Role.CLIENT, User.Role.STAFF]:
            self.customer.role = role
            self.customer.save()
            self.client.force_login(self.customer)
            for name in ["coupons", "coupon_create"]:
                self.assertEqual(self.client.get(reverse(f"reports:{name}")).status_code, 403)
                self.assertEqual(self.client.post(reverse(f"reports:{name}"), self.data).status_code, 403)
        self.assertFalse(Coupon.objects.exists())
