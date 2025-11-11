import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("relatorios", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="PlanejamentoProjeto",
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
                (
                    "horas_previstas",
                    models.DecimalField(decimal_places=2, default=0, max_digits=10),
                ),
                (
                    "projeto",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="planejamentos",
                        to="relatorios.projeto",
                    ),
                ),
            ],
            options={
                "db_table": "planejamento_projeto",
                "ordering": ("projeto_id", "ano"),
                "unique_together": {("projeto", "ano")},
            },
        ),
    ]
