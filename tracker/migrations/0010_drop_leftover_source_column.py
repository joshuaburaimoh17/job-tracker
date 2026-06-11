"""
Drop the leftover `source` column on tracker_joblead in production.

The column was added manually via SQL during the old URL-scraping flow
and never existed in the Django model. It is NOT NULL with no default,
so every INSERT from the current model fails with an IntegrityError.
Postgres-only and idempotent; local SQLite never had the column.
"""
from django.db import migrations


def _forward(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    schema_editor.execute(
        "ALTER TABLE tracker_joblead DROP COLUMN IF EXISTS source"
    )


class Migration(migrations.Migration):

    dependencies = [
        ('tracker', '0009_alter_application_status'),
    ]

    operations = [
        migrations.RunPython(_forward, migrations.RunPython.noop),
    ]
