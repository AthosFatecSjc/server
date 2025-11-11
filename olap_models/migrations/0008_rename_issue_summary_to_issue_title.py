from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("olap_models", "0007_create_dimissue_and_migrate"),
    ]

    operations = [
        migrations.RenameField(
            model_name="dimissue",
            old_name="issue_summary",
            new_name="issue_title",
        ),
    ]
