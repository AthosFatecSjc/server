import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("relatorios", "0002_planejamento_projeto"),
    ]

    operations = [
        migrations.CreateModel(
            name="RegistroProdutividade",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("dia", models.DateField()),
                (
                    "valor",
                    models.DecimalField(decimal_places=2, default=0, max_digits=6),
                ),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
                (
                    "funcionario",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="registros_produtividade",
                        to="relatorios.funcionario",
                    ),
                ),
            ],
            options={
                "db_table": "registro_produtividade",
                "ordering": ("dia",),
                "unique_together": {("funcionario", "dia")},
            },
        ),
        migrations.CreateModel(
            name="MetaProdutividade",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("ano", models.PositiveIntegerField()),
                ("mes", models.PositiveIntegerField()),
                (
                    "meta_horas",
                    models.DecimalField(decimal_places=2, default=154.0, max_digits=6),
                ),
                (
                    "funcionario",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="metas_produtividade",
                        to="relatorios.funcionario",
                    ),
                ),
            ],
            options={
                "db_table": "meta_produtividade",
                "ordering": ("funcionario_id", "ano", "mes"),
                "unique_together": {("funcionario", "ano", "mes")},
            },
        ),
    ]
