from django.db import migrations


def remove_seed_users(apps, schema_editor):
    usuario_model = apps.get_model("usuarios", "Usuario")
    usernames = [
        "gerente",
        "lider",
        "membro",
    ]
    usuario_model.objects.filter(username__in=usernames).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("usuarios", "0003_merge_20251110_2200"),
    ]

    operations = [
        migrations.RunPython(remove_seed_users, reverse_code=migrations.RunPython.noop),
    ]
