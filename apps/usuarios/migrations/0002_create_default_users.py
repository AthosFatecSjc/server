from django.contrib.auth.hashers import make_password
from django.db import migrations


def create_default_users(apps, schema_editor):
    Usuario = apps.get_model("usuarios", "Usuario")
    default_users = [
        {
            "username": "gerente_demo",
            "email": "gerente@demo.local",
            "nome_completo": "Gerente Demo",
            "perfil_acesso": "GERENTE",
            "cargo": "Gerente de Projetos",
            "password": "senha123",
        },
        {
            "username": "lider_demo",
            "email": "lider@demo.local",
            "nome_completo": "Lider Demo",
            "perfil_acesso": "LIDER",
            "cargo": "Lider de Equipe",
            "password": "senha123",
        },
        {
            "username": "membro_demo",
            "email": "membro@demo.local",
            "nome_completo": "Membro Demo",
            "perfil_acesso": "MEMBRO",
            "cargo": "Analista",
            "password": "senha123",
        },
    ]

    db_alias = schema_editor.connection.alias
    for user_data in default_users:
        if (
            Usuario.objects.using(db_alias)
            .filter(username=user_data["username"])
            .exists()
        ):
            continue
        usuario = Usuario(
            username=user_data["username"],
            email=user_data["email"],
            nome_completo=user_data["nome_completo"],
            perfil_acesso=user_data["perfil_acesso"],
            cargo=user_data["cargo"],
            ativo=True,
        )
        usuario.password = make_password(user_data["password"])
        usuario.save(using=db_alias)


def remove_default_users(apps, schema_editor):
    Usuario = apps.get_model("usuarios", "Usuario")
    usernames = ["gerente_demo", "lider_demo", "membro_demo"]
    db_alias = schema_editor.connection.alias
    Usuario.objects.using(db_alias).filter(username__in=usernames).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("usuarios", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(create_default_users, remove_default_users),
    ]
