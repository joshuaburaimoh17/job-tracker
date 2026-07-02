"""
Widen Application.job_url and JobLead.source_url from the URLField default
of 200 chars to 500 — real ATS URLs (Workday, LinkedIn with tracking params,
Greenhouse) routinely exceed 200 and were failing form validation.

Postgres: ALTER COLUMN TYPE varchar(500) is safe to run whatever the current
width is. SQLite does not enforce varchar length, so no database change is
needed there. Widening does not disturb the unique constraint on source_url.
"""
from django.db import migrations, models


def _forward(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    schema_editor.execute(
        'ALTER TABLE tracker_application ALTER COLUMN job_url TYPE varchar(500)'
    )
    schema_editor.execute(
        'ALTER TABLE tracker_joblead ALTER COLUMN source_url TYPE varchar(500)'
    )


class Migration(migrations.Migration):

    dependencies = [
        ('tracker', '0011_drop_dead_fields'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterField(
                    model_name='application',
                    name='job_url',
                    field=models.URLField(blank=True, max_length=500, null=True),
                ),
                migrations.AlterField(
                    model_name='joblead',
                    name='source_url',
                    field=models.URLField(blank=True, max_length=500, null=True, unique=True),
                ),
            ],
            database_operations=[
                migrations.RunPython(_forward, migrations.RunPython.noop),
            ],
        ),
    ]
