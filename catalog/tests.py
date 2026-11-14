import json
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings

from .images import product_image_url
from .models import Addon, Category, Product


class ProductImageTests(SimpleTestCase):
    @override_settings(DEBUG=False)
    def test_bundled_images_use_static_without_media_storage(self):
        with patch("catalog.images.default_storage.url", side_effect=AssertionError("Não é upload")):
            self.assertEqual(
                product_image_url("products/cappuccino-cremoso.png"),
                "/static/catalog/products/cappuccino-cremoso.png",
            )

    def test_new_uploads_continue_using_configured_storage(self):
        with patch("catalog.images.default_storage.url", return_value="https://storage.example/custom.png") as url:
            self.assertEqual(product_image_url("products/custom.png"), "https://storage.example/custom.png")
            url.assert_called_once_with("products/custom.png")
        self.assertEqual(product_image_url(""), "")


class LoadCatalogTests(TestCase):
    def load_catalog(self):
        call_command("load_catalog", stdout=StringIO())

    def test_imports_complete_catalog_without_demo_accounts(self):
        self.load_catalog()
        data = json.loads((settings.BASE_DIR / "catalog/data/catalog.json").read_text())
        self.assertEqual(Product.objects.count(), 12)
        self.assertEqual(Category.objects.count(), 3)
        self.assertFalse(get_user_model().objects.exists())
        for row in data["products"]:
            product = Product.objects.get(slug=row["slug"])
            self.assertEqual(product.price, Decimal(row["price"]))
            self.assertEqual(product.image.name, row["image"])
            self.assertTrue((settings.BASE_DIR / "static/catalog" / row["image"]).is_file())
            self.assertEqual(product.ingredients.count(), len(row["ingredients"]))
            self.assertEqual(product.allergens.count(), len(row["allergens"]))
            self.assertEqual(product.addons.count(), len(row["addons"]))
        response = self.client.get("/produtos/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "/static/catalog/products/", count=12)

    def test_repeated_import_preserves_edits_uploads_and_relationships(self):
        self.load_catalog()
        product = Product.objects.get(slug="cupcake-red-velvet")
        product.price = Decimal("29.90")
        product.stock_quantity = 7
        product.is_active = False
        product.image = "products/custom.png"
        product.save()
        product.addons.clear()
        self.load_catalog()
        product.refresh_from_db()
        self.assertEqual(Product.objects.count(), 12)
        self.assertEqual(product.price, Decimal("29.90"))
        self.assertEqual(product.stock_quantity, 7)
        self.assertFalse(product.is_active)
        self.assertEqual(product.image.name, "products/custom.png")
        self.assertFalse(product.addons.exists())
        self.assertEqual(Addon.objects.count(), 3)

    def test_completes_seed_demo_catalog_without_resetting_passwords(self):
        call_command("seed_demo", stdout=StringIO())
        user = get_user_model().objects.get(email="gerente@demo.com")
        user.set_password("own-password-123")
        user.save()
        self.load_catalog()
        self.assertEqual(Product.objects.count(), 12)
        self.assertFalse(Product.objects.filter(image="").exists())
        user.refresh_from_db()
        self.assertTrue(user.check_password("own-password-123"))
