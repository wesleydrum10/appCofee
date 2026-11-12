from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase
from django.template.loader import render_to_string
from django.urls import reverse
from PIL import Image


class PwaTests(SimpleTestCase):
    def test_manifest_is_public_and_has_installable_icons(self):
        response = self.client.get(reverse("core:manifest"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/manifest+json")
        manifest = response.json()
        self.assertEqual(manifest["display"], "standalone")
        self.assertEqual(manifest["scope"], "/")
        self.assertEqual(manifest["start_url"], "/")
        self.assertEqual(manifest["id"], "/")
        self.assertEqual({icon["purpose"] for icon in manifest["icons"]}, {"any", "maskable"})
        for icon in manifest["icons"]:
            file = settings.BASE_DIR / icon["src"].lstrip("/")
            with Image.open(file) as image:
                self.assertEqual(f"{image.width}x{image.height}", icon["sizes"])
                if icon["purpose"] == "maskable":
                    self.assertEqual(image.convert("RGBA").getextrema()[3], (255, 255))
        self.assertEqual(len(manifest["shortcuts"]), 2)
        self.assertFalse(response.cookies)

    def test_service_worker_is_root_scoped_javascript_without_permanent_cache(self):
        response = self.client.get(reverse("core:service_worker"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/javascript")
        self.assertEqual(response["Service-Worker-Allowed"], "/")
        self.assertEqual(response["Cache-Control"], "no-cache")
        self.assertContains(response, "'/offline/'")
        self.assertContains(response, "'/static/icons/icon-192.png'")
        self.assertNotContains(response, "{%")
        self.assertFalse(response.cookies)

    def test_offline_page_has_no_network_dependencies_or_account_context(self):
        response = self.client.get(reverse("core:offline"))
        self.assertContains(response, "Uma pausa na conexão.")
        self.assertContains(response, "Tentar novamente")
        self.assertNotContains(response, "https://")
        self.assertNotContains(response, "csrfmiddlewaretoken")
        self.assertFalse(response.cookies)

    def test_base_template_exposes_icons_and_install_ui(self):
        html = render_to_string("base.html")
        self.assertIn('rel="manifest" href="/manifest.webmanifest"', html)
        self.assertIn('rel="apple-touch-icon"', html)
        self.assertIn('/static/icons/favicon.ico', html)
        self.assertIn('/static/icons/icon.svg', html)
        self.assertIn('data-pwa-install hidden', html)
        self.assertIn('Adicionar à Tela de Início', html)
        self.assertIn('css/pwa.css', html)

    def test_apple_icon_and_favicon_sizes(self):
        root = Path(settings.BASE_DIR) / "static/icons"
        with Image.open(root / "apple-touch-icon.png") as image:
            self.assertEqual(image.size, (180, 180))
        with Image.open(root / "favicon.ico") as image:
            self.assertEqual(image.ico.sizes(), {(16, 16), (32, 32), (48, 48)})
