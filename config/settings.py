"""Settings for the SPARK ranking system."""
import os
from datetime import timedelta
from pathlib import Path

# Load .env file in development
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Helper for boolean env vars
def env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}

from django.core.exceptions import ImproperlyConfigured
from django.core.management.utils import get_random_secret_key

# Optional: dj_database_url can be used for Neon URL parsing.
# It is not required because we parse the URL manually using urllib.parse.



def env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


BASE_DIR = Path(__file__).resolve().parent.parent

DEBUG = env_bool("SPARK_DEBUG", False)
SECRET_KEY = os.environ.get("SPARK_SECRET_KEY")
if not SECRET_KEY:
    if DEBUG:
        # An ephemeral key keeps local development usable without shipping a
        # known signing key into production.
        SECRET_KEY = get_random_secret_key()
    else:
        raise ImproperlyConfigured("Set SPARK_SECRET_KEY before starting outside debug mode.")

if not DEBUG and not os.environ.get("SPARK_ALLOWED_HOSTS", "").strip():
    raise ImproperlyConfigured("Set SPARK_ALLOWED_HOSTS to the deployed host names outside debug mode.")

ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get("SPARK_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if host.strip()
]

# Production defaults assume TLS terminates at Django or a correctly
# configured reverse proxy. HSTS is enabled for one year in production.
SECURE_SSL_REDIRECT = env_bool("SPARK_SSL_REDIRECT", not DEBUG)
SECURE_HSTS_SECONDS = int(os.environ.get("SPARK_HSTS_SECONDS", "0" if DEBUG else "31536000"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("SPARK_HSTS_INCLUDE_SUBDOMAINS", False)
SECURE_HSTS_PRELOAD = env_bool("SPARK_HSTS_PRELOAD", False)
SESSION_COOKIE_SECURE = env_bool("SPARK_SESSION_COOKIE_SECURE", not DEBUG)
CSRF_COOKIE_SECURE = env_bool("SPARK_CSRF_COOKIE_SECURE", not DEBUG)
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

if env_bool("SPARK_TRUST_X_FORWARDED_PROTO", False):
    # Enable only when the trusted proxy removes any client supplied value.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "leaderboard.apps.LeaderboardConfig",
    "axes",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "axes.middleware.AxesMiddleware",
]

AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]

# Track failed Admin logins by IP, with a rolling cooldown that avoids a
# permanent account lockout after a small number of mistyped passwords.
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = timedelta(minutes=15)
AXES_USE_ATTEMPT_EXPIRATION = True
AXES_LOCKOUT_PARAMETERS = ["ip_address"]
AXES_ONLY_ADMIN_SITE = True
AXES_RESET_ON_SUCCESS = True
AXES_HTTP_RESPONSE_CODE = 429
AXES_ENABLE_RETRY_AFTER_HEADER = True

if env_bool("SPARK_AXES_TRUST_X_FORWARDED_FOR", False):
    try:
        AXES_IPWARE_PROXY_COUNT = int(os.environ["SPARK_AXES_PROXY_COUNT"])
    except (KeyError, ValueError) as exc:
        raise ImproperlyConfigured(
            "Set SPARK_AXES_PROXY_COUNT to the trusted proxy count when trusting X-Forwarded-For."
        ) from exc
    if AXES_IPWARE_PROXY_COUNT < 1:
        raise ImproperlyConfigured("SPARK_AXES_PROXY_COUNT must be at least 1.")
    AXES_IPWARE_META_PRECEDENCE_ORDER = ("HTTP_X_FORWARDED_FOR", "REMOTE_ADDR")

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# Database configuration – use Neon if NEON_DATABASE_URL is set, otherwise fallback to Postgres env vars
from urllib.parse import urlparse
NEON_URL = os.getenv("NEON_DATABASE_URL")
if NEON_URL:
    parsed = urlparse(NEON_URL)
    # parsed.path includes leading '/', strip it for DB name
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": parsed.path.lstrip("/"),
            "USER": parsed.username,
            "PASSWORD": parsed.password,
            "HOST": parsed.hostname,
            "PORT": str(parsed.port) if parsed.port else "",
            "OPTIONS": {"sslmode": "require"},
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("POSTGRES_DB", "postgres"),
            "USER": os.getenv("POSTGRES_USER", "postgres"),
            "PASSWORD": os.getenv("POSTGRES_PASSWORD", ""),
            "HOST": os.getenv("POSTGRES_HOST", "localhost"),
            "PORT": os.getenv("POSTGRES_PORT", "5432"),
        }
    }


AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# USNs stay private until club leadership approves public display.
PUBLIC_SHOW_USN = os.environ.get("SPARK_PUBLIC_SHOW_USN", "false").lower() in {"1", "true", "yes"}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
