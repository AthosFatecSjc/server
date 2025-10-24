from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        (
            "relatorios",
            "0002_rename_objetivo_estagirario_metatempocontrole_objetivo_estagiario",
        ),
    ]

    operations = [
        migrations.AddField(
            model_name="funcionario",
            name="valor_hora",
            field=models.DecimalField(
                decimal_places=2,
                default=40.0,
                help_text="Valor/hora do desenvolvedor (R$)",
                max_digits=8,
            ),
        ),
    ]
