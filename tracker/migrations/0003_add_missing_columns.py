from django.db import migrations


_SQL = [
    "ALTER TABLE tracker_joblead ADD COLUMN IF NOT EXISTS cover_letter_path VARCHAR(500) NOT NULL DEFAULT ''",
    "ALTER TABLE tracker_application ADD COLUMN IF NOT EXISTS cover_letter_path VARCHAR(500) NOT NULL DEFAULT ''",
    "ALTER TABLE tracker_application ADD COLUMN IF NOT EXISTS contact_name VARCHAR(200)",
    "ALTER TABLE tracker_application ADD COLUMN IF NOT EXISTS follow_up_date DATE",
    "ALTER TABLE tracker_application ADD COLUMN IF NOT EXISTS job_description TEXT",
    "ALTER TABLE tracker_application ADD COLUMN IF NOT EXISTS cv_path VARCHAR(500) NOT NULL DEFAULT ''",
]


def _forward(apps, schema_editor):
    for sql in _SQL:
        schema_editor.execute(sql)


class Migration(migrations.Migration):

    dependencies = [
        ('tracker', '0002_sync_schema'),
    ]

    operations = [
        migrations.RunPython(_forward, migrations.RunPython.noop),
    ]
