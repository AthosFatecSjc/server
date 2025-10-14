"""Configuração da aplicação de dashboards."""
from django.apps import AppConfig


class DashboardsConfig(AppConfig):
    """Configuração da aplicação de dashboards."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.dashboards'
