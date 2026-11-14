import json
from pathlib import Path

import dj_database_url
from decouple import Csv, config
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(value, default=False):
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on", "debug"}:
        return True
    if normalized in {"0", "false", "no", "off", "release", "production"}:
        return False
    return default


DEBUG = config("DEBUG", default=False, cast=env_bool)
SECRET_KEY = config("SECRET_KEY", default="dev-only-change-me" if DEBUG else "")
if not SECRET_KEY or (not DEBUG and SECRET_KEY in {"dev-only-change-me", "change-me"}):
    raise ImproperlyConfigured("Defina SECRET_KEY com um segredo próprio para produção.")
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="localhost,127.0.0.1", cast=Csv())
CSRF_TRUSTED_ORIGINS = config("CSRF_TRUSTED_ORIGINS", default="", cast=Csv())
# O Render informa o domínio atribuído ao serviço, inclusive em previews.
# Nunca derive esta permissão do cabeçalho Host enviado pelo cliente.
render_hostname = config("RENDER_EXTERNAL_HOSTNAME", default="").strip()
if render_hostname:
    if render_hostname not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(render_hostname)
    render_origin = f"https://{render_hostname}"
    if render_origin not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(render_origin)
if not DEBUG and (not ALLOWED_HOSTS or "*" in ALLOWED_HOSTS):
    raise ImproperlyConfigured("Defina ALLOWED_HOSTS com os domínios de produção, sem '*'.")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "core",
    "accounts",
    "catalog",
    "inventory",
    "cart",
    "orders",
    "payments",
    "coupons",
    "reviews",
    "reports",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates", BASE_DIR / "core" / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "cart.context_processors.cart_summary",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

database_url = config("DATABASE_URL", default="").strip()
if database_url:
    if not database_url.lower().startswith(("postgres://", "postgresql://")):
        raise ImproperlyConfigured(
            "Este projeto requer PostgreSQL. DATABASE_URL deve começar com postgresql:// ou postgres://. "
            "Cole apenas a URL, sem psql, aspas ou o prefixo DATABASE_URL=."
        )
    try:
        database = dj_database_url.parse(database_url, conn_max_age=60, conn_health_checks=True)
    except ValueError:
        raise ImproperlyConfigured(
            "DATABASE_URL PostgreSQL inválida. Confira a connection string do Neon e a porta. "
            "Cole apenas a URL, sem psql, aspas ou o prefixo DATABASE_URL=."
        ) from None
elif DEBUG:
    database = {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": config("POSTGRES_DB", default="appcoffee"),
        "USER": config("POSTGRES_USER", default="appcoffee"),
        "PASSWORD": config("POSTGRES_PASSWORD", default=""),
        "HOST": config("POSTGRES_HOST", default="localhost"),
        "PORT": config("POSTGRES_PORT", default="5432"),
    }
else:
    raise ImproperlyConfigured("Defina DATABASE_URL PostgreSQL para produção (Neon com SSL).")
if database["ENGINE"] != "django.db.backends.postgresql":
    raise ImproperlyConfigured("Este projeto requer PostgreSQL; DATABASE_URL deve usar postgres ou postgresql.")
if not DEBUG:
    options = database.setdefault("OPTIONS", {})
    if options.get("sslmode", "require") not in {"require", "verify-ca", "verify-full"}:
        raise ImproperlyConfigured("DATABASE_URL de produção deve exigir SSL (sslmode=require ou verify-*).")
    options.setdefault("sslmode", "require")
# Compatível com o pool transacional do Neon/PgBouncer.
database["DISABLE_SERVER_SIDE_CURSORS"] = True
DATABASES = {"default": database}

AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = ["accounts.backends.EmailBackend"]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

MEDIA_URL = config("MEDIA_URL", default="/media/")
MEDIA_ROOT = BASE_DIR / "media"
STORAGES = {
    "default": {
        "BACKEND": config("MEDIA_STORAGE_BACKEND", default=(
            "django.core.files.storage.FileSystemStorage" if DEBUG else "core.storage.ExternalMediaRequiredStorage"
        )),
        "OPTIONS": config("MEDIA_STORAGE_OPTIONS", default="{}", cast=json.loads),
    },
    # URLs estáveis preservam os imports relativos dos ES Modules e o cache do PWA.
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "catalog:product_list"
LOGOUT_REDIRECT_URL = "core:home"

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
SESSION_COOKIE_NAME = "appcoffee_sessionid"
CSRF_COOKIE_NAME = "appcoffee_csrftoken"
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https") if not DEBUG else None
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_SSL_REDIRECT = config("SECURE_SSL_REDIRECT", default=not DEBUG, cast=env_bool)
SECURE_REDIRECT_EXEMPT = [r"^health/$"]

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}

PASSWORD_RESET_TIMEOUT = 60 * 60 * 24
