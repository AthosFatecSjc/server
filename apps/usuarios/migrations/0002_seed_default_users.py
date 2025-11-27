import os

from django.contrib.auth.hashers import make_password
from django.db import IntegrityError, migrations

PADRAO_LABEL = "Padrão"
DEFAULT_PASSWORD = os.getenv("DEFAULT_SEED_USER_PASSWORD", "athos123")
# Mantemos essa migração como no-op para não criar usuários padrão.
DISABLE_SEED_USERS = True


def seed_default_users(apps, schema_editor):
    if DISABLE_SEED_USERS:
        return

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

    def _buscar_usuario_existente(username: str, email: str):
        usuario = usuario_model.objects.filter(username=username).first()
        if usuario:
            return usuario
        return usuario_model.objects.filter(email__iexact=email).first()

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
        usuario_existente = _buscar_usuario_existente(dados["username"], dados["email"])
        if usuario_existente:
            for campo, valor in defaults.items():
                setattr(usuario_existente, campo, valor)
            usuario_existente.username = dados["username"]
            usuario_existente.save()
            continue

        try:
            usuario_model.objects.create(username=dados["username"], **defaults)
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
