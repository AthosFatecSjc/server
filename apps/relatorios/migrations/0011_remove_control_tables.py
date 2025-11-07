# Generated manually to remover tabelas de controle antigas
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("relatorios", "0010_alter_issue_status_alter_projeto_jira_key_and_more"),
    ]

    operations = [
        migrations.DeleteModel(
            name="TempoControleValores",
        ),
        migrations.DeleteModel(
            name="TempoGastoEquipe",
        ),
        migrations.DeleteModel(
            name="MetaTempoControle",
        ),
        migrations.DeleteModel(
            name="ControleHorasEquipe",
        ),
        migrations.DeleteModel(
            name="ControleHorasEquipeResumo",
        ),
    ]
