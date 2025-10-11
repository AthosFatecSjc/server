"""Configuração da aplicação de comparação de relatórios."""
from django.apps import AppConfig


class ComparacaoConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.relatorios.comparacao"
