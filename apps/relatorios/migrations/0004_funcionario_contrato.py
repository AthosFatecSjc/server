from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("relatorios", "0003_registro_produtividade_meta_produtividade"),
    ]

    operations = [
        migrations.AddField(
            model_name="funcionario",
            name="contrato",
            field=models.CharField(
                choices=[("CLT", "CLT"), ("ESTAGIARIO", "Estagiário")],
                default="CLT",
                max_length=20,
            ),
        ),
    ]
