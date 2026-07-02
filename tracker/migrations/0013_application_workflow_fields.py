"""
New Application fields for the daily workflow:

- location / salary_range: carried over from the JobLead when a lead is
  converted via the new "Mark Applied" flow.
- status_updated_at: set only when status actually changes — foundation for
  follow-up reminders ("no status change in 7+ days"), which updated_at
  cannot provide because it bumps on every save. Backfilled from updated_at.

Idempotent: ADD COLUMN IF NOT EXISTS on Postgres, introspection guard on
SQLite, and the backfill only touches NULL rows.
"""
from django.db import migrations, models


_NEW_COLUMNS = [
    ('location', "varchar(200) NOT NULL DEFAULT ''"),
    ('salary_range', "varchar(100) NOT NULL DEFAULT ''"),
    ('status_updated_at', 'timestamptz NULL'),
]

_SQLITE_TYPES = {
    'location': "varchar(200) NOT NULL DEFAULT ''",
    'salary_range': "varchar(100) NOT NULL DEFAULT ''",
    'status_updated_at': 'datetime NULL',
}


def _forward(apps, schema_editor):
    connection = schema_editor.connection

    if connection.vendor == 'postgresql':
        for column, ddl in _NEW_COLUMNS:
            schema_editor.execute(
                f'ALTER TABLE tracker_application ADD COLUMN IF NOT EXISTS {column} {ddl}'
            )
    else:
        with connection.cursor() as cursor:
            existing = [
                col.name
                for col in connection.introspection.get_table_description(
                    cursor, 'tracker_application'
                )
            ]
        for column, _ in _NEW_COLUMNS:
            if column not in existing:
                schema_editor.execute(
                    f'ALTER TABLE tracker_application ADD COLUMN {column} {_SQLITE_TYPES[column]}'
                )

    # Backfill: treat the last row update as the last known status change.
    schema_editor.execute(
        'UPDATE tracker_application SET status_updated_at = updated_at '
        'WHERE status_updated_at IS NULL'
    )


class Migration(migrations.Migration):

    dependencies = [
        ('tracker', '0012_widen_url_fields'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name='application',
                    name='location',
                    field=models.CharField(blank=True, max_length=200),
                ),
                migrations.AddField(
                    model_name='application',
                    name='salary_range',
                    field=models.CharField(blank=True, max_length=100),
                ),
                migrations.AddField(
                    model_name='application',
                    name='status_updated_at',
                    field=models.DateTimeField(blank=True, null=True),
                ),
            ],
            database_operations=[
                migrations.RunPython(_forward, migrations.RunPython.noop),
            ],
        ),
    ]
