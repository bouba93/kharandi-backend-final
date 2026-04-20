"""
╔══════════════════════════════════════════════════════════════════════════╗
║             KHARANDI — Django Settings                                  ║
║             Optimisé pour Render.com (plan gratuit)                     ║
║             Sans Celery / Sans Redis                                    ║
╚══════════════════════════════════════════════════════════════════════════╝
"""

import os
from pathlib import Path
from datetime import timedelta
import environ
import dj_database_url

# ── Chemins ────────────────────────────────────────────────────────────────
# config/settings.py → config/ → kharandi_v2/
BASE_DIR = Path(__file__).resolve().parent.parent

# ── Environnement ──────────────────────────────────────────────────────────
env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY    = env("SECRET_KEY")
DEBUG         = env.bool("DEBUG", default=False)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1", ".onrender.com"])

# ══════════════════════════════════════════════════════════════════════════
#  APPLICATIONS
# ══════════════════════════════════════════════════════════════════════════
DJANGO_APPS = [
    "unfold",
    "unfold.contrib.filters",
    "unfold.contrib.forms",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "django_filters",
    "auditlog",
    "axes",
    "phonenumber_field",
    "cloudinary",
    "cloudinary_storage",
]

LOCAL_APPS = [
    "kharandi.apps.accounts",
    "kharandi.apps.marketplace",
    "kharandi.apps.payments",
    "kharandi.apps.courses",
    "kharandi.apps.notifications",
    "kharandi.apps.search",
    "kharandi.apps.reports",
    "kharandi.apps.support",
    "kharandi.apps.ai_assistant",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# ══════════════════════════════════════════════════════════════════════════
#  MIDDLEWARE
# ══════════════════════════════════════════════════════════════════════════
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",      # Statiques avant CORS
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "auditlog.middleware.AuditlogMiddleware",
    "axes.middleware.AxesMiddleware",
]

ROOT_URLCONF      = "config.urls"
WSGI_APPLICATION  = "config.wsgi.application"

# ══════════════════════════════════════════════════════════════════════════
#  TEMPLATES
# ══════════════════════════════════════════════════════════════════════════
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

# ══════════════════════════════════════════════════════════════════════════
#  BASE DE DONNÉES — PostgreSQL Render
# ══════════════════════════════════════════════════════════════════════════
DATABASE_URL = env("DATABASE_URL", default="sqlite:///kharandi_dev.db")

DATABASES = {
    "default": dj_database_url.parse(
        DATABASE_URL,
        conn_max_age=600,
        conn_health_checks=True,
    )
}
DATABASES["default"]["ATOMIC_REQUESTS"] = True

# ══════════════════════════════════════════════════════════════════════════
#  CACHE — Base de données (sans Redis sur Render gratuit)
# ══════════════════════════════════════════════════════════════════════════
CACHES = {
    "default": {
        "BACKEND":  "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "kharandi_cache_table",
        "TIMEOUT":  300,
        "OPTIONS":  {"MAX_ENTRIES": 5000},
    }
}
# Note : après migrate, lancer : python manage.py createcachetable

# ══════════════════════════════════════════════════════════════════════════
#  AUTH
# ══════════════════════════════════════════════════════════════════════════
AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
     "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]

# ══════════════════════════════════════════════════════════════════════════
#  INTERNATIONALISATION
# ══════════════════════════════════════════════════════════════════════════
LANGUAGE_CODE = "fr"           # "fr-gn" invalide → "fr"
TIME_ZONE     = "Africa/Conakry"
USE_I18N      = True
USE_TZ        = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ══════════════════════════════════════════════════════════════════════════
#  FICHIERS STATIQUES (Whitenoise — Render)
# ══════════════════════════════════════════════════════════════════════════
STATIC_URL   = "/static/"
STATIC_ROOT  = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# ══════════════════════════════════════════════════════════════════════════
#  MÉDIAS — Cloudinary (gratuit, persistant)
# ══════════════════════════════════════════════════════════════════════════
CLOUDINARY_STORAGE = {
    "CLOUD_NAME": env("CLOUDINARY_CLOUD_NAME", default=""),
    "API_KEY":    env("CLOUDINARY_API_KEY",    default=""),
    "API_SECRET": env("CLOUDINARY_API_SECRET", default=""),
}

# Si Cloudinary configuré, l'utiliser; sinon stockage local (dev)
if env("CLOUDINARY_CLOUD_NAME", default=""):
    DEFAULT_FILE_STORAGE = "cloudinary_storage.storage.MediaCloudinaryStorage"
    MEDIA_URL = f"https://res.cloudinary.com/{env('CLOUDINARY_CLOUD_NAME', default='')}/"
else:
    MEDIA_URL  = "/media/"
    MEDIA_ROOT = BASE_DIR / "media"

# ══════════════════════════════════════════════════════════════════════════
#  DJANGO REST FRAMEWORK
# ══════════════════════════════════════════════════════════════════════════
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_PAGINATION_CLASS": "kharandi.apps.accounts.pagination.KharandiPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "100/hour",
        "user": "1000/hour",
        "otp":  "5/minute",
        "ai":   "20/hour",
    },
    "EXCEPTION_HANDLER": "kharandi.apps.accounts.exceptions.kharandi_exception_handler",
}

# ══════════════════════════════════════════════════════════════════════════
#  JWT
# ══════════════════════════════════════════════════════════════════════════
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME":    timedelta(hours=2),
    "REFRESH_TOKEN_LIFETIME":   timedelta(days=30),
    "ROTATE_REFRESH_TOKENS":    True,
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_HEADER_TYPES":        ("Bearer",),
    "USER_ID_FIELD":            "id",
    "USER_ID_CLAIM":            "user_id",
}

# ══════════════════════════════════════════════════════════════════════════
#  CORS
# ══════════════════════════════════════════════════════════════════════════
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[
    "http://localhost:3000",
    "http://localhost:5173",
])
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_ALL_ORIGINS = env.bool("CORS_ALLOW_ALL", default=False)

# ══════════════════════════════════════════════════════════════════════════
#  NIMBASMS (appel direct, sans Celery)
# ══════════════════════════════════════════════════════════════════════════
NIMBA_SID         = env("NIMBA_SID",    default="")
NIMBA_TOKEN       = env("NIMBA_TOKEN",  default="")
NIMBA_SENDER_NAME = env("NIMBA_SENDER", default="Kharandi")

# ══════════════════════════════════════════════════════════════════════════
#  LENGOPAY
# ══════════════════════════════════════════════════════════════════════════
LENGOPAY_WEBSITE_ID      = env("LENGOPAY_SITE_ID",  default="")
LENGOPAY_LICENSE_KEY     = env("LENGOPAY_LICENSE",  default="")
LENGOPAY_API_URL         = "https://portal.lengopay.com/api/v1/payments"
PLATFORM_COMMISSION_RATE = env.float("COMMISSION_RATE", default=0.05)

# ══════════════════════════════════════════════════════════════════════════
#  IA — Karamö
# ══════════════════════════════════════════════════════════════════════════
AI_PROVIDER            = env("AI_PROVIDER",    default="gemini")
GEMINI_API_KEY         = env("GEMINI_API_KEY", default="")
DEEPSEEK_API_KEY       = env("DEEPSEEK_API_KEY", default="")
ANTHROPIC_API_KEY      = env("ANTHROPIC_API_KEY", default="")
AI_DAILY_LIMIT_FREE    = env.int("AI_DAILY_LIMIT_FREE",    default=10)
AI_DAILY_LIMIT_PREMIUM = env.int("AI_DAILY_LIMIT_PREMIUM", default=50)
# Cache IA en base (sans Redis)
AI_CACHE_TIMEOUT = env.int("AI_CACHE_TIMEOUT", default=86400)

# ══════════════════════════════════════════════════════════════════════════
#  TÉLÉPHONES
# ══════════════════════════════════════════════════════════════════════════
PHONENUMBER_DEFAULT_REGION = "GN"
PHONENUMBER_DB_FORMAT      = "INTERNATIONAL"

# ══════════════════════════════════════════════════════════════════════════
#  DJANGO-AXES (anti brute-force)
# ══════════════════════════════════════════════════════════════════════════
AXES_FAILURE_LIMIT                       = 5
AXES_COOLOFF_TIME                        = timedelta(minutes=30)
AXES_LOCK_OUT_BY_COMBINATION_USER_AND_IP = True
AXES_RESET_ON_SUCCESS                    = True
AXES_HANDLER                             = "axes.handlers.database.AxesDatabaseHandler"

# ══════════════════════════════════════════════════════════════════════════
#  AUDIT LOG
# ══════════════════════════════════════════════════════════════════════════
AUDITLOG_INCLUDE_ALL_MODELS = False

# ══════════════════════════════════════════════════════════════════════════
#  LOGGING — Console uniquement (Render filesystem éphémère)
# ══════════════════════════════════════════════════════════════════════════
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{asctime} [{levelname}] {name} — {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class":     "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "loggers": {
        "kharandi": {"handlers": ["console"], "level": "INFO",    "propagate": False},
        "django":   {"handlers": ["console"], "level": "WARNING", "propagate": False},
    },
    "root": {"handlers": ["console"], "level": "WARNING"},
}

# ══════════════════════════════════════════════════════════════════════════
#  SÉCURITÉ PRODUCTION
# ══════════════════════════════════════════════════════════════════════════
if not DEBUG:
    SECURE_PROXY_SSL_HEADER      = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT          = True
    SESSION_COOKIE_SECURE        = True
    CSRF_COOKIE_SECURE           = True
    SECURE_HSTS_SECONDS          = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD          = True
    SECURE_CONTENT_TYPE_NOSNIFF  = True

# ══════════════════════════════════════════════════════════════════════════
#  UNFOLD ADMIN
# ══════════════════════════════════════════════════════════════════════════
UNFOLD = {
    "SITE_TITLE":        "Kharandi Admin",
    "SITE_HEADER":       "Kharandi",
    "SITE_URL":          "/",
    "SITE_SYMBOL":       "school",
    "SHOW_HISTORY":      True,
    "SHOW_VIEW_ON_SITE": True,
    "COLORS": {
        "primary": {
            "50": "240 249 255", "100": "224 242 254",
            "500": "26 115 232", "700": "21 100 191", "900": "12 74 110",
        }
    },
    "SIDEBAR": {
        "show_search": True,
        "show_all_applications": False,
        "navigation": [
            {
                "title": "Utilisateurs",
                "icon":  "people",
                "items": [
                    {"title": "Tous",        "link": "/admin/accounts/user/"},
                    {"title": "Répétiteurs", "link": "/admin/accounts/user/?role=tutor"},
                    {"title": "Vendeurs",    "link": "/admin/accounts/user/?role=vendor"},
                ],
            },
            {
                "title": "Marketplace",
                "icon":  "store",
                "items": [
                    {"title": "Produits",   "link": "/admin/marketplace/product/"},
                    {"title": "Commandes",  "link": "/admin/marketplace/order/"},
                    {"title": "Catégories", "link": "/admin/marketplace/category/"},
                ],
            },
            {
                "title": "Cours",
                "icon":  "book",
                "items": [
                    {"title": "Cours",       "link": "/admin/courses/course/"},
                    {"title": "Inscriptions","link": "/admin/courses/enrollment/"},
                    {"title": "Notes",       "link": "/admin/courses/grade/"},
                ],
            },
            {
                "title": "Paiements",
                "icon":  "payments",
                "items": [
                    {"title": "Transactions", "link": "/admin/payments/transaction/"},
                    {"title": "Commissions",  "link": "/admin/payments/commission/"},
                    {"title": "Factures",     "link": "/admin/payments/invoice/"},
                ],
            },
            {
                "title": "Support",
                "icon":  "support_agent",
                "items": [
                    {"title": "Tickets", "link": "/admin/support/ticket/"},
                ],
            },
            {
                "title": "IA Karamö",
                "icon":  "smart_toy",
                "items": [
                    {"title": "Conversations", "link": "/admin/ai_assistant/aiconversation/"},
                    {"title": "Consommation",  "link": "/admin/ai_assistant/aiusagelog/"},
                ],
            },
            {
                "title": "Système",
                "icon":  "settings",
                "items": [
                    {"title": "Audit Logs",  "link": "/admin/auditlog/logentry/"},
                    {"title": "OTP Codes",   "link": "/admin/accounts/otpcode/"},
                    {"title": "Axes / Accès","link": "/admin/axes/accessattempt/"},
                ],
            },
        ],
    },
}

# ── Crons HTTP (cron-job.org) ─────────────────────────────────────────────
import os as _os
CRON_SECRET = _os.environ.get('CRON_SECRET', '')
