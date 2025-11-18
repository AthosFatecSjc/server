from django.apps import AppConfig


class UsuariosConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.usuarios"

    def ready(self):  # noqa: D401
        """Registra sinais do app."""
        from apps.usuarios import signals  # noqa: F401
