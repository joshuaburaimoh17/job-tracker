"""
Schema sync for Railway: the squashed 0001 was recorded as already-applied on
the existing production DB, so columns/tables added after the original 0001
were never created.  This migration brings the live schema in line with
models.py using ADD COLUMN IF NOT EXISTS (PostgreSQL only — SQLite already
has the full schema from the new 0001).
"""
from django.db import migrations


_PG_SQL = [
    # Application — add anything that may be missing from the original 0001
    "ALTER TABLE tracker_application ADD COLUMN IF NOT EXISTS job_url VARCHAR(200) NULL",
    "ALTER TABLE tracker_application ADD COLUMN IF NOT EXISTS job_description TEXT NULL",
    "ALTER TABLE tracker_application ADD COLUMN IF NOT EXISTS cv_path VARCHAR(500) NOT NULL DEFAULT ''",
    "ALTER TABLE tracker_application ADD COLUMN IF NOT EXISTS cover_letter_path VARCHAR(500) NOT NULL DEFAULT ''",
    "ALTER TABLE tracker_application ADD COLUMN IF NOT EXISTS notes TEXT NULL",
    "ALTER TABLE tracker_application ADD COLUMN IF NOT EXISTS contact_name VARCHAR(200) NULL",
    "ALTER TABLE tracker_application ADD COLUMN IF NOT EXISTS follow_up_date DATE NULL",

    # CVDocument — create table if missing
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

    # JobLead — create table if missing
    """
    CREATE TABLE IF NOT EXISTS tracker_joblead (
        id BIGSERIAL PRIMARY KEY,
        company VARCHAR(200) NOT NULL,
        role VARCHAR(200) NOT NULL,
        location VARCHAR(200) NOT NULL DEFAULT '',
        salary_range VARCHAR(100) NOT NULL DEFAULT '',
        job_description TEXT NOT NULL DEFAULT '',
        source_url VARCHAR(200) NOT NULL,
        status VARCHAR(20) NOT NULL DEFAULT 'new',
        cv_original_text TEXT NOT NULL DEFAULT '',
        cv_tailored_text TEXT NOT NULL DEFAULT '',
        cv_path VARCHAR(500) NOT NULL DEFAULT '',
        cover_letter_path VARCHAR(500) NOT NULL DEFAULT '',
        date_found TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        application_id BIGINT NULL
            REFERENCES tracker_application(id)
            DEFERRABLE INITIALLY DEFERRED
    )
    """,

    # Unique constraint on source_url (idempotent via DO block)
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

    # JobLead — add columns that may be absent from an older version of the table
    "ALTER TABLE tracker_joblead ADD COLUMN IF NOT EXISTS location VARCHAR(200) NOT NULL DEFAULT ''",
    "ALTER TABLE tracker_joblead ADD COLUMN IF NOT EXISTS salary_range VARCHAR(100) NOT NULL DEFAULT ''",
    "ALTER TABLE tracker_joblead ADD COLUMN IF NOT EXISTS cv_original_text TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE tracker_joblead ADD COLUMN IF NOT EXISTS cv_tailored_text TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE tracker_joblead ADD COLUMN IF NOT EXISTS cv_path VARCHAR(500) NOT NULL DEFAULT ''",
    "ALTER TABLE tracker_joblead ADD COLUMN IF NOT EXISTS cover_letter_path VARCHAR(500) NOT NULL DEFAULT ''",
]


def _forward(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    for sql in _PG_SQL:
        schema_editor.execute(sql)


class Migration(migrations.Migration):

    dependencies = [
        ('tracker', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(_forward, migrations.RunPython.noop),
    ]
