"""
Drop dead schema: columns and a table no live code reads or writes.

- Application.cv_path / cover_letter_path: only ever rendered as hidden form
  inputs, never populated.
- JobLead.cv_path / cover_letter_path: cv_path was only a legacy fallback for
  files on Railway's ephemeral disk (long gone); cover_letter_path was never
  used anywhere.
- CVDocument: entire model unused — the base CV comes from settings.CV_BASE_PATH.

Idempotent on both vendors (prod has had schema drift from manual SQL):
Postgres uses DROP ... IF EXISTS; SQLite guards via introspection.
"""
from django.db import migrations


_DEAD_COLUMNS = [
    ('tracker_application', 'cv_path'),
    ('tracker_application', 'cover_letter_path'),
    ('tracker_joblead', 'cv_path'),
    ('tracker_joblead', 'cover_letter_path'),
]


def _forward(apps, schema_editor):
    connection = schema_editor.connection

    if connection.vendor == 'postgresql':
        for table, column in _DEAD_COLUMNS:
            schema_editor.execute(
                f'ALTER TABLE {table} DROP COLUMN IF EXISTS {column}'
            )
        schema_editor.execute('DROP TABLE IF EXISTS tracker_cvdocument')
        return

    # SQLite (local dev): no DROP COLUMN IF EXISTS — guard via introspection.
    with connection.cursor() as cursor:
        for table, column in _DEAD_COLUMNS:
            existing = [
                col.name
                for col in connection.introspection.get_table_description(cursor, table)
            ]
            if column in existing:
                schema_editor.execute(f'ALTER TABLE {table} DROP COLUMN {column}')
    schema_editor.execute('DROP TABLE IF EXISTS tracker_cvdocument')


class Migration(migrations.Migration):

    dependencies = [
        ('tracker', '0010_drop_leftover_source_column'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveField(model_name='application', name='cv_path'),
                migrations.RemoveField(model_name='application', name='cover_letter_path'),
                migrations.RemoveField(model_name='joblead', name='cv_path'),
                migrations.RemoveField(model_name='joblead', name='cover_letter_path'),
                migrations.DeleteModel(name='CVDocument'),
            ],
            database_operations=[
                migrations.RunPython(_forward, migrations.RunPython.noop),
            ],
        ),
    ]
