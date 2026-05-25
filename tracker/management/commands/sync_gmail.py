"""
Scans Gmail (via IMAP) for emails related to tracked applications and
auto-updates Application.status based on keyword classification.

Requires EMAIL_HOST_USER and EMAIL_HOST_PASSWORD to be set (Gmail App Password).
Designed to run as a Railway cron: e.g. twice daily at 8am and 6pm UTC.

Status transitions (only forward-progress moves are made):
  applied           → interview_scheduled | rejected | offer
  interview_scheduled → rejected | offer
  interview_done    → rejected | offer
  offer / rejected  → (terminal — untouched)
"""

import imaplib
import email
import re
from email.header import decode_header as _decode_header
from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.conf import settings

from tracker.models import Application


# --- Classification patterns (searched in subject + first 2000 chars of body) ---

_OFFER_RE = re.compile(
    r'pleased to offer|job offer|formal offer|delighted to offer|'
    r"we'?d like to offer|extend.*offer|offer.*position",
    re.I,
)
_INTERVIEW_RE = re.compile(
    r'interview|schedule a call|schedule a chat|'
    r"we'?d like to invite|next step|speak with you|"
    r'hiring manager|technical assessment|coding test|phone screen|video call|'
    r'assessment centre',
    re.I,
)
_REJECTION_RE = re.compile(
    r'unfortunately|not moving forward|not successful|regret to inform|'
    r'not been selected|not selected|other candidate|position has been filled|'
    r'decided not to proceed|will not be moving forward|not be proceeding|'
    r'not taken forward|unsuccessful|not progress',
    re.I,
)

# Status ordering — higher index = further along / more final
_STATUS_RANK = {
    'applied': 0,
    'interview_scheduled': 1,
    'interview_done': 2,
    'offer': 3,
    'rejected': 3,  # same rank as offer — both are terminal
    'withdrawn': 4,
}

_TRACKABLE = {'applied', 'interview_scheduled', 'interview_done'}
_TERMINAL = {'offer', 'rejected', 'withdrawn'}


def _decode_str(raw) -> str:
    """Decode an email header value (may be encoded bytes or plain str)."""
    if raw is None:
        return ''
    parts = _decode_header(raw)
    result = []
    for chunk, charset in parts:
        if isinstance(chunk, bytes):
            result.append(chunk.decode(charset or 'utf-8', errors='replace'))
        else:
            result.append(chunk)
    return ' '.join(result)


def _classify(subject: str, body: str) -> str | None:
    """Return new status keyword or None if no pattern matches."""
    text = subject + ' ' + body[:2000]
    if _OFFER_RE.search(text):
        return 'offer'
    if _INTERVIEW_RE.search(text):
        return 'interview_scheduled'
    if _REJECTION_RE.search(text):
        return 'rejected'
    return None


def _get_body(msg) -> str:
    """Extract plain-text body from an email.Message object."""
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            cd = str(part.get('Content-Disposition', ''))
            if ct == 'text/plain' and 'attachment' not in cd:
                payload = part.get_payload(decode=True)
                if payload:
                    return payload.decode(
                        part.get_content_charset() or 'utf-8', errors='replace'
                    )
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            return payload.decode(
                msg.get_content_charset() or 'utf-8', errors='replace'
            )
    return ''


class Command(BaseCommand):
    help = 'Sync Gmail inbox → auto-update Application statuses.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=90,
            help='How many days back to search (default: 90).',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Print what would change without saving.',
        )

    def handle(self, *args, **options):
        user = getattr(settings, 'EMAIL_HOST_USER', '')
        password = getattr(settings, 'EMAIL_HOST_PASSWORD', '')

        if not user or not password:
            self.stderr.write(self.style.ERROR(
                'EMAIL_HOST_USER and EMAIL_HOST_PASSWORD must be set.'
            ))
            return

        apps = list(Application.objects.filter(status__in=_TRACKABLE))
        if not apps:
            self.stdout.write('No trackable applications — nothing to do.')
            return

        dry_run = options['dry_run']
        since_date = date.today() - timedelta(days=options['days'])
        # IMAP date format: DD-Mon-YYYY
        imap_since = since_date.strftime('%d-%b-%Y')

        self.stdout.write(f'Connecting to Gmail as {user} …')
        try:
            mail = imaplib.IMAP4_SSL('imap.gmail.com', 993)
            mail.login(user, password)
        except Exception as exc:
            self.stderr.write(self.style.ERROR(f'IMAP login failed: {exc}'))
            return

        try:
            mail.select('INBOX', readonly=True)
            # Fetch all message IDs since the cutoff date (one IMAP call)
            _, data = mail.search(None, f'(SINCE {imap_since})')
            all_ids = data[0].split() if data[0] else []
            self.stdout.write(f'  {len(all_ids)} messages since {imap_since}')

            if not all_ids:
                self.stdout.write('Inbox is empty for that window — done.')
                return

            # Fetch headers in one batch (RFC822.HEADER is lightweight)
            id_list = ','.join(i.decode() for i in all_ids)
            _, msg_data = mail.fetch(id_list, '(RFC822)')

            # Parse all messages once, build list of (subject, from, body_getter)
            parsed = []
            for response in msg_data:
                if isinstance(response, tuple):
                    msg = email.message_from_bytes(response[1])
                    subject = _decode_str(msg.get('Subject', ''))
                    sender = _decode_str(msg.get('From', ''))
                    body = _get_body(msg)
                    parsed.append((subject, sender, body))

            self.stdout.write(f'  Parsed {len(parsed)} messages')

        finally:
            try:
                mail.logout()
            except Exception:
                pass

        updated = 0
        for app in apps:
            company_lower = app.company.lower()
            # Words in company name (≥3 chars) — match any of them
            keywords = [w for w in re.split(r'\W+', company_lower) if len(w) >= 3]
            if not keywords:
                continue

            best_new_status = None
            for subject, sender, body in parsed:
                combined = (subject + ' ' + sender).lower()
                if not any(kw in combined for kw in keywords):
                    continue  # this email isn't about this company
                new_status = _classify(subject, body)
                if new_status is None:
                    continue
                # Keep highest-rank classification across all matching emails
                if best_new_status is None or (
                    _STATUS_RANK.get(new_status, 0) > _STATUS_RANK.get(best_new_status, 0)
                ):
                    best_new_status = new_status

            if best_new_status is None:
                continue

            # Only move forward — never downgrade
            if _STATUS_RANK.get(best_new_status, 0) <= _STATUS_RANK.get(app.status, 0):
                continue

            if dry_run:
                self.stdout.write(
                    f'  [dry-run] {app} | {app.status} -> {best_new_status}'
                )
            else:
                old = app.status
                app.status = best_new_status
                app.save(update_fields=['status'])
                self.stdout.write(
                    self.style.SUCCESS(f'  Updated: {app} | {old} -> {best_new_status}')
                )
                updated += 1

        suffix = ' (dry run)' if dry_run else ''
        self.stdout.write(f'Done{suffix} — {updated} application(s) updated.')
