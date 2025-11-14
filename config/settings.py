import datetime
import os
from pathlib import Path

import environ
import sentry_sdk
from django.core.exceptions import ImproperlyConfigured
from sentry_sdk.integrations.django import DjangoIntegration

BASE_DIR = Path(__file__).resolve().parent.parent
SQLITE_ENGINE = "django.db.backends.sqlite3"

env = environ.Env()
env_path = BASE_DIR / ".env"
if not env_path.exists():
    env_path = BASE_DIR.parent / ".env"
if env_path.exists():
    environ.Env.read_env(str(env_path))


def get_env(name: str, default=None):
    return os.getenv(name, default)


def get_bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "t", "yes", "on"}


def get_list_env(name: str, default=None, separator: str = ",") -> list:
    value = os.getenv(name)
    if value is None:
        return list(default) if isinstance(default, (list, tuple)) else default or []
    return [item.strip() for item in value.split(separator) if item.strip()]


def optional(value):
    return value if value not in (None, "") else None


DEBUG = get_bool_env("DEBUG", True)
secret_fallback = get_env(
    "DEFAULT_SECRET_KEY",
    "django-insecure-default-key-for-tests",
)
SECRET_KEY = get_env("SECRET_KEY", secret_fallback)
if not SECRET_KEY:
    SECRET_KEY = secret_fallback
if SECRET_KEY == secret_fallback and not DEBUG:
    raise ImproperlyConfigured(
        "SECRET_KEY não configurado. Defina SECRET_KEY no ambiente."
    )

ALLOWED_HOSTS_DEFAULT = ["*"] if DEBUG else []
ALLOWED_HOSTS = get_list_env("ALLOWED_HOSTS", ALLOWED_HOSTS_DEFAULT)

# Application definition
INSTALLED_APPS = [
    "apps.relatorios",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_htmx",
    "django_crontab",
    "apps.usuarios",
    "apps.relatorios.produtividade",
    "apps.relatorios.comparacao.apps.ComparacaoConfig",
    "apps.relatorios.atividade",
    "apps.dashboards",
    "apps.dashboards.desenvolvedores",
    "apps.dashboards.projetos",
    "apps.dashboards.equipes",
    "apps.utils",
    "config",
    "olap_models",
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
    "django_htmx.middleware.HtmxMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [
            BASE_DIR / "templates",
        ],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases

DATABASE_ROUTERS = ["config.routers.OlapRouter"]

default_db_engine = get_env("DB_ENGINE") or get_env("DB_OLTP_ENGINE") or SQLITE_ENGINE
default_db_name = (
    get_env("DB_NAME") or get_env("DB_OLTP_NAME") or str(BASE_DIR / "db.sqlite3")
)

DATABASES = {
    "default": {
        "ENGINE": default_db_engine,
        "NAME": default_db_name,
        "USER": optional(get_env("DB_USER") or get_env("DB_OLTP_USER")),
        "PASSWORD": optional(get_env("DB_PASSWORD") or get_env("DB_OLTP_PASSWORD")),
        "HOST": optional(get_env("DB_HOST") or get_env("DB_OLTP_HOST")),
        "PORT": optional(get_env("DB_PORT") or get_env("DB_OLTP_PORT")),
    },
    "olap": {
        "ENGINE": (
            get_env("DB_ENGINE_OLAP") or get_env("DB_OLAP_ENGINE") or default_db_engine
        ),
        "NAME": (
            get_env("DB_NAME_OLAP")
            or get_env("DB_OLAP_NAME")
            or str(BASE_DIR / "db_olap.sqlite3")
        ),
        "USER": optional(get_env("DB_USER_OLAP") or get_env("DB_OLAP_USER")),
        "PASSWORD": optional(
            get_env("DB_PASSWORD_OLAP") or get_env("DB_OLAP_PASSWORD")
        ),
        "HOST": optional(get_env("DB_HOST_OLAP") or get_env("DB_OLAP_HOST")),
        "PORT": optional(get_env("DB_PORT_OLAP") or get_env("DB_OLAP_PORT")),
    },
}

DATABASE_ROUTERS = ["config.routers.OlapRouter"]

AUTH_USER_MODEL = "usuarios.Usuario"

if not DATABASES["default"]["NAME"]:
    DATABASES["default"] = {
        "ENGINE": SQLITE_ENGINE,
        "NAME": str(BASE_DIR / "db.sqlite3"),
    }
if not DATABASES["olap"]["NAME"]:
    DATABASES["olap"] = {
        "ENGINE": SQLITE_ENGINE,
        "NAME": str(BASE_DIR / "db_olap.sqlite3"),
    }

if get_env("TEST_DB_ENGINE"):
    DATABASES["default"] = {
        "ENGINE": get_env("TEST_DB_ENGINE"),
        "NAME": get_env("TEST_DB_NAME", ":memory:"),
    }

JIRA_BASE_URL = get_env("JIRA_BASE_URL") or get_env(
    "JIRA_URL",
    "https://dummy.atlassian.net",
)
JIRA_USER = get_env("JIRA_USER", "dummy@ci")
JIRA_TOKEN = get_env("JIRA_TOKEN", "token123")

# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = "pt-br"

TIME_ZONE = "America/Sao_Paulo"

USE_I18N = True

USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = "static/"

# Onde o Django procura arquivos estáticos adicionais (a pasta /static do seu projeto)
STATICFILES_DIRS = [
    BASE_DIR / "static",
]

# Para onde o 'collectstatic' vai copiar todos os arquivos para produção
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Cron Jobs
# Cron Jobs
CRONJOBS = [
    # Executa a cada minuto - sincronização rápida
    (
        get_env("CRON_BUSCAR_DADOS", "0 19 * * *"),
        "apps.utils.cron.buscar_dados_api",
    ),
    # Executa a cada minuto - ETL mais pesado
    (
        get_env("CRON_ETL", "*/1 * * * *"),
        "apps.utils.cron.buscar_dados_com_etl",
    ),
    # Executa a cada hora - processo completo (Jira sync + ETL)
    # (
    #     get_env("CRON_COMPLETO", "0 */1 * * *"),  # A cada hora
    #     "apps.utils.cron.buscar_dados_com_etl",
    # ),
]

# Configuração de cache personalizado para dados do JIRA
CACHE_JIRA = {
    "data": {},
    "timestamp": None,
    "validade": datetime.timedelta(minutes=10),
}

# Session management
SESSION_COOKIE_AGE = env.int("SESSION_COOKIE_AGE", default=2 * 60 * 60)  # 2 hours
SESSION_SAVE_EVERY_REQUEST = True  # refresh expiry on activity
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

# Sentry Configuration
SENTRY_DSN = get_env("SENTRY_DSN", "")

if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[
            DjangoIntegration(),
        ],
        traces_sample_rate=1.0,
        send_default_pii=True,
    )
