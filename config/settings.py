import datetime
import os
from pathlib import Path

import environ
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(DEBUG=(bool, False))

env_path = os.path.join(BASE_DIR, ".env")
if not os.path.exists(env_path):
    env_path = os.path.join(BASE_DIR, "../.env")

environ.Env.read_env(env_path)

DEBUG = env("DEBUG", default=True)
SECRET_KEY = env("SECRET_KEY")
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=[])

# Application definition
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_htmx",
    "django_crontab",
    "apps.usuarios",
    "apps.relatorios",
    "apps.relatorios.produtividade",
    "apps.relatorios.comparacao.apps.ComparacaoConfig",
    "apps.relatorios.atividade",
    "apps.dashboards",
    "apps.dashboards.desenvolvedores",
    "apps.dashboards.projetos",
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

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("DB_OLTP_NAME", default=None),
        "USER": env("DB_OLTP_USER", default=None),
        "PASSWORD": env("DB_OLTP_PASSWORD", default=None),
        "HOST": env("DB_OLTP_HOST", default=None),
        "PORT": env("DB_OLTP_PORT", default=None),
    },
    "olap": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("DB_OLAP_NAME", default=None),
        "USER": env("DB_OLAP_USER", default=None),
        "PASSWORD": env("DB_OLAP_PASSWORD", default=None),
        "HOST": env("DB_OLAP_HOST", default=None),
        "PORT": env("DB_OLAP_PORT", default=None),
    },
}

DATABASE_ROUTERS = ["config.routers.OlapRouter"]

if not DATABASES["default"]["NAME"]:
    DATABASES["default"] = {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": str(BASE_DIR / "db.sqlite3"),
    }
if not DATABASES["olap"]["NAME"]:
    DATABASES["olap"] = {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": str(BASE_DIR / "db_olap.sqlite3"),
    }

if os.environ.get("TEST_DB_ENGINE"):
    DATABASES["default"] = {
        "ENGINE": os.environ["TEST_DB_ENGINE"],
        "NAME": os.environ.get("TEST_DB_NAME", ":memory:"),
    }

JIRA_BASE_URL = env("JIRA_BASE_URL", default="http://localhost")
JIRA_USER = env("JIRA_USER", default="user")
JIRA_TOKEN = env("JIRA_TOKEN", default="token")

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
        env("CRON_BUSCAR_DADOS", default="0 19 * * *"),
        "apps.utils.cron.buscar_dados_api",
    ),
    # Executa a cada minuto - ETL mais pesado
    (
        env("CRON_ETL", default="*/1 * * * *"),
        "apps.utils.cron.buscar_dados_com_etl",
    ),
    # Executa a cada hora - processo completo (Jira sync + ETL)
    # (
    #     env("CRON_COMPLETO", default="0 */1 * * *"),  # A cada hora
    #     "apps.utils.cron.buscar_dados_com_etl",
    # ),
]

# Configuração de cache personalizado para dados do JIRA
CACHE_JIRA = {
    "data": {},
    "timestamp": None,
    "validade": datetime.timedelta(minutes=10),
}

# Sentry Configuration
SENTRY_DSN = env("SENTRY_DSN", default="")

if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[
            DjangoIntegration(),
        ],
        traces_sample_rate=1.0,
        send_default_pii=True,
    )
