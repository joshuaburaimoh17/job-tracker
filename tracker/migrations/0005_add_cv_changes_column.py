from django.db import migrations


def _forward(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    schema_editor.execute(
        "ALTER TABLE tracker_joblead ADD COLUMN IF NOT EXISTS cv_changes TEXT NOT NULL DEFAULT ''"
    )


class Migration(migrations.Migration):

    dependencies = [
        ('tracker', '0004_joblead_cv_changes'),
    ]

    operations = [
        migrations.RunPython(_forward, migrations.RunPython.noop),
    ]
