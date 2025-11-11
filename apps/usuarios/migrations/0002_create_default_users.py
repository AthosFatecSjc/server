import os

from django.contrib.auth.hashers import make_password
from django.db import migrations

HASHED_PREFIXES = ("pbkdf2_sha256$",)
DEFAULT_DEMO_PASSWORD = os.getenv(
    "DEFAULT_DEMO_USER_PASSWORD_HASH",
    "pbkdf2_sha256$1000000$cb09NZgFtDrrCzFTHCid4H$n9a6Ej8lQ/E2LiyBBtSJNxHZC0hD4+SnWJG3+tbLRIU=",
)


def _resolve_password(value: str) -> str:
    if not value:
        return ""
    return value if value.startswith(HASHED_PREFIXES) else make_password(value)


def create_default_users(apps, schema_editor):
    usuario_model = apps.get_model("usuarios", "Usuario")
    default_users = [
        {
            "username": "gerente_demo",
            "email": "gerente@demo.local",
            "nome_completo": "Gerente Demo",
            "perfil_acesso": "GERENTE",
            "cargo": "Gerente de Projetos",
            "password": DEFAULT_DEMO_PASSWORD,
        },
        {
            "username": "lider_demo",
            "email": "lider@demo.local",
            "nome_completo": "Lider Demo",
            "perfil_acesso": "LIDER",
            "cargo": "Lider de Equipe",
            "password": DEFAULT_DEMO_PASSWORD,
        },
        {
            "username": "membro_demo",
            "email": "membro@demo.local",
            "nome_completo": "Membro Demo",
            "perfil_acesso": "MEMBRO",
            "cargo": "Analista",
            "password": DEFAULT_DEMO_PASSWORD,
        },
    ]

    db_alias = schema_editor.connection.alias
    for user_data in default_users:
        if (
            usuario_model.objects.using(db_alias)
            .filter(username=user_data["username"])
            .exists()
        ):
            continue
        usuario = usuario_model(
            username=user_data["username"],
            email=user_data["email"],
            nome_completo=user_data["nome_completo"],
            perfil_acesso=user_data["perfil_acesso"],
            cargo=user_data["cargo"],
            ativo=True,
        )
        usuario.password = _resolve_password(user_data["password"])
        usuario.save(using=db_alias)


def remove_default_users(apps, schema_editor):
    usuario_model = apps.get_model("usuarios", "Usuario")
    usernames = ["gerente_demo", "lider_demo", "membro_demo"]
    db_alias = schema_editor.connection.alias
    usuario_model.objects.using(db_alias).filter(username__in=usernames).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("usuarios", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(create_default_users, remove_default_users),
    ]
