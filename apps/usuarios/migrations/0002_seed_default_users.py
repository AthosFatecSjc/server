import os

from django.contrib.auth.hashers import make_password
from django.db import IntegrityError, migrations

PADRAO_LABEL = "Padrão"
DEFAULT_PASSWORD = os.getenv("DEFAULT_SEED_USER_PASSWORD", "athos123")


def seed_default_users(apps, schema_editor):
    usuario_model = apps.get_model("usuarios", "Usuario")
    usuarios = [
        {
            "username": "lider",
            "nome_completo": f"Líder {PADRAO_LABEL}",
            "first_name": "Líder",
            "last_name": PADRAO_LABEL,
            "email": "lider@athos.com",
            "cargo": "Líder de Projeto",
            "perfil_acesso": "LIDER",
            "is_staff": True,
            "is_superuser": True,
            "password": DEFAULT_PASSWORD,
        },
        {
            "username": "gerente",
            "nome_completo": f"Gerente {PADRAO_LABEL}",
            "first_name": "Gerente",
            "last_name": PADRAO_LABEL,
            "email": "gerente@athos.com",
            "cargo": "Gerente Operacional",
            "perfil_acesso": "GERENTE",
            "is_staff": True,
            "is_superuser": True,
            "password": DEFAULT_PASSWORD,
        },
        {
            "username": "membro",
            "nome_completo": f"Membro {PADRAO_LABEL}",
            "first_name": "Membro",
            "last_name": PADRAO_LABEL,
            "email": "membro@athos.com",
            "cargo": "Desenvolvedor",
            "perfil_acesso": "MEMBRO",
            "is_staff": False,
            "is_superuser": False,
            "password": DEFAULT_PASSWORD,
        },
    ]

    for dados in usuarios:
        defaults = {
            "nome_completo": dados["nome_completo"],
            "first_name": dados["first_name"],
            "last_name": dados["last_name"],
            "email": dados["email"],
            "cargo": dados["cargo"],
            "perfil_acesso": dados["perfil_acesso"],
            "contrato": "CLT",
            "ativo": True,
            "is_staff": dados["is_staff"],
            "is_superuser": dados["is_superuser"],
            "password": make_password(dados["password"]),
        }
        try:
            usuario_model.objects.update_or_create(
                username=dados["username"],
                defaults=defaults,
            )
        except IntegrityError:
            usuario_model.objects.filter(username=dados["username"]).update(**defaults)


def remove_default_users(apps, schema_editor):
    usuario_model = apps.get_model("usuarios", "Usuario")
    usuario_model.objects.filter(username__in=["lider", "gerente", "membro"]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("usuarios", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_default_users, remove_default_users),
    ]
