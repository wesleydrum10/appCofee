import json
import os
import subprocess
import sys

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.files.base import ContentFile
from django.test import SimpleTestCase, override_settings

from core.storage import ExternalMediaRequiredStorage


class DeploymentTests(SimpleTestCase):
    @override_settings(SECURE_SSL_REDIRECT=True)
    def test_health_is_public_without_database_or_https_redirect(self):
        # SimpleTestCase rejects database queries, including accidental session access.
        response = self.client.get("/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        self.assertFalse(response.cookies)
        self.assertEqual(self.client.head("/health/").status_code, 200)

    def test_production_default_rejects_ephemeral_uploads(self):
        with self.assertRaisesMessage(ImproperlyConfigured, "armazenamento externo"):
            ExternalMediaRequiredStorage().save("probe.txt", ContentFile(b"probe"))

    def load_settings(self, **overrides):
        environment = {
            **os.environ,
            "DEBUG": "False",
            "SECRET_KEY": "synthetic-deployment-test-key-with-more-than-fifty-characters",
            "ALLOWED_HOSTS": "deployment.example",
            "DATABASE_URL": "postgresql://test:test@database.example/test",
            "RENDER_EXTERNAL_HOSTNAME": "",
            "CSRF_TRUSTED_ORIGINS": "https://deployment.example",
            **overrides,
        }
        return subprocess.run(
            [sys.executable, "-c", (
                "import json; from config import settings as s; "
                "print(json.dumps({'engine': s.DATABASES['default']['ENGINE'], "
                "'hosts': s.ALLOWED_HOSTS, 'origins': s.CSRF_TRUSTED_ORIGINS, "
                "'ssl': s.DATABASES['default'].get('OPTIONS', {}).get('sslmode'), "
                "'secure_cookies': s.SESSION_COOKIE_SECURE and s.CSRF_COOKIE_SECURE, "
                "'pool_compatible': s.DATABASES['default']['DISABLE_SERVER_SIDE_CURSORS']}))"
            )],
            cwd=settings.BASE_DIR, env=environment, capture_output=True, text=True,
        )

    def test_production_requires_secret_key_and_database_url(self):
        for variable in ("SECRET_KEY", "DATABASE_URL"):
            with self.subTest(variable=variable):
                result = self.load_settings(**{variable: ""})
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(variable, result.stderr)

    def test_rejects_sqlite_in_both_environments(self):
        for debug in ("True", "False"):
            with self.subTest(debug=debug):
                result = self.load_settings(DEBUG=debug, DATABASE_URL="sqlite:///:memory:")
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("requer PostgreSQL", result.stderr)

    def test_invalid_database_urls_have_clear_errors_without_exposing_credentials(self):
        for url in (
            "psql 'postgresql://user:synthetic-secret@database.example/test'",
            "'postgresql://user:synthetic-secret@database.example/test'",
            "DATABASE_URL=postgresql://user:synthetic-secret@database.example/test",
            "database.example/test-synthetic-secret",
            "postgresql://user:synthetic-secret@database.example:wrong-port/test",
        ):
            with self.subTest(url=url):
                result = self.load_settings(DATABASE_URL=url)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Cole apenas a URL", result.stderr)
                self.assertNotIn("synthetic-secret", result.stderr)

    def test_production_requires_ssl_and_explicit_hosts(self):
        for override in (
            {"DATABASE_URL": "postgresql://test:test@database.example/test?sslmode=disable"},
            {"ALLOWED_HOSTS": "*"},
        ):
            with self.subTest(override=override):
                self.assertNotEqual(self.load_settings(**override).returncode, 0)

    def test_production_enables_ssl_cookies_and_pool_compatibility(self):
        result = self.load_settings()
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["engine"], "django.db.backends.postgresql")
        self.assertEqual(data["ssl"], "require")
        self.assertTrue(data["secure_cookies"])
        self.assertTrue(data["pool_compatible"])

    def test_preserves_stricter_ssl(self):
        result = self.load_settings(DATABASE_URL="postgresql://test:test@database.example/test?sslmode=verify-full")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["ssl"], "verify-full")

    def test_render_hostname_is_allowed_alongside_custom_domains(self):
        for hosts in ("", "localhost,127.0.0.1", "deployment.example,appcofee.onrender.com"):
            with self.subTest(hosts=hosts):
                result = self.load_settings(
                    ALLOWED_HOSTS=hosts, RENDER_EXTERNAL_HOSTNAME="appcofee.onrender.com",
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                data = json.loads(result.stdout)
                self.assertEqual(data["hosts"].count("appcofee.onrender.com"), 1)
                self.assertIn("https://appcofee.onrender.com", data["origins"])
                self.assertIn("https://deployment.example", data["origins"])

    def test_without_render_hostname_no_host_is_added(self):
        result = self.load_settings()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["hosts"], ["deployment.example"])
