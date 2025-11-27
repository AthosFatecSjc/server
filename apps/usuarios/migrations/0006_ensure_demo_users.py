import os

from django.contrib.auth.hashers import make_password
from django.db import migrations

DEFAULT_PASSWORD = os.getenv("DEFAULT_DEMO_USER_PASSWORD", "athos123")


def ensure_demo_users(apps, schema_editor):
    usuario_model = apps.get_model("usuarios", "Usuario")
    demos = [
        {
            "username": "gerente_demo",
            "email": "gerente@demo.local",
            "nome_completo": "Gerente Demo",
            "perfil_acesso": "GERENTE",
            "cargo": "Gerente de Projetos",
            "is_staff": True,
            "is_superuser": True,
        },
        {
            "username": "lider_demo",
            "email": "lider@demo.local",
            "nome_completo": "Lider Demo",
            "perfil_acesso": "LIDER",
            "cargo": "Lider de Equipe",
            "is_staff": True,
            "is_superuser": True,
        },
        {
            "username": "membro_demo",
            "email": "membro@demo.local",
            "nome_completo": "Membro Demo",
            "perfil_acesso": "MEMBRO",
            "cargo": "Analista",
            "is_staff": False,
            "is_superuser": False,
        },
    ]
    hashed_password = make_password(DEFAULT_PASSWORD)
    for dados in demos:
        usuario, _ = usuario_model.objects.update_or_create(
            username=dados["username"],
            defaults={
                **dados,
                "ativo": True,
                "password": hashed_password,
            },
        )
        if not usuario.is_active:
            usuario.is_active = True
            usuario.save(update_fields=["is_active"])


class Migration(migrations.Migration):
    dependencies = [
        ("usuarios", "0005_remove_seed_users_again"),
    ]

    operations = [
        migrations.RunPython(
            ensure_demo_users,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
