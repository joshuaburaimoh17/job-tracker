"""
Production sync migration.

Every schema change since initial deploy is enforced here with
IF NOT EXISTS / DROP NOT NULL so this is safe to run against any
database state — fresh, partially-applied, or fully up to date.
"""
from django.db import migrations


_PG_SQL = [

    # ── tracker_joblead ──────────────────────────────────────────────────────

    # Columns added after the original deploy (0002 RunPython may not have run)
    "ALTER TABLE tracker_joblead ADD COLUMN IF NOT EXISTS location VARCHAR(200) NOT NULL DEFAULT ''",
    "ALTER TABLE tracker_joblead ADD COLUMN IF NOT EXISTS salary_range VARCHAR(100) NOT NULL DEFAULT ''",
    "ALTER TABLE tracker_joblead ADD COLUMN IF NOT EXISTS cv_original_text TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE tracker_joblead ADD COLUMN IF NOT EXISTS cv_tailored_text TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE tracker_joblead ADD COLUMN IF NOT EXISTS cv_path VARCHAR(500) NOT NULL DEFAULT ''",
    "ALTER TABLE tracker_joblead ADD COLUMN IF NOT EXISTS cover_letter_path VARCHAR(500) NOT NULL DEFAULT ''",

    # cv_changes added in 0004 / 0005 — enforce here (0005 RunPython may not have run)
    "ALTER TABLE tracker_joblead ADD COLUMN IF NOT EXISTS cv_changes TEXT NOT NULL DEFAULT ''",

    # source_url: ensure column exists, then drop NOT NULL (0006 AlterField may not have applied)
    "ALTER TABLE tracker_joblead ADD COLUMN IF NOT EXISTS source_url VARCHAR(200)",
    "ALTER TABLE tracker_joblead ALTER COLUMN source_url DROP NOT NULL",

    # Re-create unique constraint on source_url if it was lost
    """
    DO $$ BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE conname = 'tracker_joblead_source_url_key'
        ) THEN
            ALTER TABLE tracker_joblead
                ADD CONSTRAINT tracker_joblead_source_url_key UNIQUE (source_url);
        END IF;
    END $$
    """,

    # FK to tracker_application (in case table was created without it)
    """
    DO $$ BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'tracker_joblead'
              AND column_name = 'application_id'
        ) THEN
            ALTER TABLE tracker_joblead
                ADD COLUMN application_id BIGINT NULL
                    REFERENCES tracker_application(id)
                    DEFERRABLE INITIALLY DEFERRED;
        END IF;
    END $$
    """,

    # ── tracker_application ──────────────────────────────────────────────────

    # Columns added after the original deploy (0002 RunPython may not have run)
    "ALTER TABLE tracker_application ADD COLUMN IF NOT EXISTS job_url VARCHAR(200) NULL",
    "ALTER TABLE tracker_application ADD COLUMN IF NOT EXISTS job_description TEXT NULL",
    "ALTER TABLE tracker_application ADD COLUMN IF NOT EXISTS cv_path VARCHAR(500) NOT NULL DEFAULT ''",
    "ALTER TABLE tracker_application ADD COLUMN IF NOT EXISTS cover_letter_path VARCHAR(500) NOT NULL DEFAULT ''",
    "ALTER TABLE tracker_application ADD COLUMN IF NOT EXISTS notes TEXT NULL",
    "ALTER TABLE tracker_application ADD COLUMN IF NOT EXISTS contact_name VARCHAR(200) NULL",
    "ALTER TABLE tracker_application ADD COLUMN IF NOT EXISTS follow_up_date DATE NULL",

    # ── tracker_cvdocument ───────────────────────────────────────────────────

    # Created in 0001_initial but also guarded in 0002 — enforce again
    """
    CREATE TABLE IF NOT EXISTS tracker_cvdocument (
        id BIGSERIAL PRIMARY KEY,
        label VARCHAR(200) NOT NULL,
        file_path VARCHAR(500) NOT NULL,
        is_active BOOLEAN NOT NULL DEFAULT FALSE,
        uploaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        notes TEXT NULL
    )
    """,
]


def _forward(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    for sql in _PG_SQL:
        schema_editor.execute(sql)


class Migration(migrations.Migration):

    dependencies = [
        ('tracker', '0006_alter_joblead_source_url'),
    ]

    operations = [
        migrations.RunPython(_forward, migrations.RunPython.noop),
    ]
