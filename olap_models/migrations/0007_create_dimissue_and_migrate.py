# Generated migration: create DimIssue, add FK to FatoRegistroHoras, migrate existing issue_* data, remove old fields
import django.db.models.deletion
from django.db import migrations, models


def forwards(apps, schema_editor):
    DimIssue = apps.get_model("olap_models", "DimIssue")
    Fato = apps.get_model("olap_models", "FatoRegistroHoras")

    for fato in Fato.objects.using(schema_editor.connection.alias).all():
        # dados antigos nas colunas issue_key / issue_type / issue_summary
        issue_key = getattr(fato, "issue_key", None)
        issue_type = getattr(fato, "issue_type", None)
        issue_summary = getattr(fato, "issue_summary", None)
        if issue_key or issue_type or issue_summary:
            # migrar usando o valor antigo issue_key para popular o novo campo issue_id
            obj, _ = DimIssue.objects.using(
                schema_editor.connection.alias
            ).get_or_create(
                issue_id=issue_key,
                defaults={"issue_type": issue_type, "issue_summary": issue_summary},
            )
            fato.issue_id = obj.id
            fato.save()


def backwards(apps, schema_editor):
    DimIssue = apps.get_model("olap_models", "DimIssue")
    Fato = apps.get_model("olap_models", "FatoRegistroHoras")

    for fato in Fato.objects.using(schema_editor.connection.alias).all():
        if fato.issue_id:
            try:
                dim = DimIssue.objects.using(schema_editor.connection.alias).get(
                    id=fato.issue_id
                )
                fato.issue_type = dim.issue_type
                fato.issue_key = dim.issue_id
                fato.issue_summary = dim.issue_summary
                fato.save()
            except DimIssue.DoesNotExist:
                continue


class Migration(migrations.Migration):

    dependencies = [
        ("olap_models", "0006_add_issue_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="DimIssue",
            fields=[
                ("id", models.AutoField(primary_key=True, serialize=False)),
                (
                    "issue_id",
                    models.CharField(max_length=50, unique=True, null=True, blank=True),
                ),
                ("issue_type", models.CharField(max_length=30, null=True, blank=True)),
                (
                    "issue_summary",
                    models.CharField(max_length=200, null=True, blank=True),
                ),
                ("created_date", models.DateField(null=True, blank=True)),
            ],
            options={"db_table": "dim_issue"},
        ),
        migrations.AddField(
            model_name="fatoregistrohoras",
            name="issue",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.SET_NULL,
                to="olap_models.dimissue",
                null=True,
                blank=True,
            ),
        ),
        migrations.RunPython(forwards, backwards),
        migrations.RemoveField(
            model_name="fatoregistrohoras",
            name="issue_type",
        ),
        migrations.RemoveField(
            model_name="fatoregistrohoras",
            name="issue_key",
        ),
        migrations.RemoveField(
            model_name="fatoregistrohoras",
            name="issue_summary",
        ),
    ]
