from datetime import timedelta, date
from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone
from tracker.models import JobLead, Application


class Command(BaseCommand):
    help = 'Send a daily digest email of new job leads to DIGEST_RECIPIENT.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Send the digest even if there are no new leads.',
        )
        parser.add_argument(
            '--app-url',
            default='http://localhost:8000/queue/',
            help='Base URL to the job queue (shown in the email CTA).',
        )

    def handle(self, *args, **options):
        recipient = getattr(settings, 'DIGEST_RECIPIENT', '')
        if not recipient:
            self.stderr.write(self.style.ERROR('DIGEST_RECIPIENT is not set — aborting.'))
            return

        since = timezone.now() - timedelta(hours=24)
        new_leads = JobLead.objects.filter(date_found__gte=since).order_by('-date_found')
        new_count = new_leads.count()

        if new_count == 0 and not options['force']:
            self.stdout.write('No new leads in the last 24 h — skipping digest.')
            return

        context = {
            'leads': new_leads,
            'new_count': new_count,
            'ready_count': JobLead.objects.filter(status='ready').count(),
            'applied_count': Application.objects.filter(status='applied').count(),
            'digest_date': date.today().strftime('%A, %d %B %Y'),
            'app_url': options['app_url'],
        }

        html_body = render_to_string('tracker/email_digest.html', context)
        subject = f'JobTrack — {new_count} new lead{"s" if new_count != 1 else ""} today ({date.today().strftime("%d %b")})'

        send_mail(
            subject=subject,
            message=f'{new_count} new job lead(s) found. Open the app to review them.',
            from_email=settings.DEFAULT_FROM_EMAIL or 'noreply@jobtrack.local',
            recipient_list=[recipient],
            html_message=html_body,
            fail_silently=False,
        )

        self.stdout.write(self.style.SUCCESS(
            f'Digest sent to {recipient} — {new_count} new lead(s), '
            f'{context["ready_count"]} ready, {context["applied_count"]} applied.'
        ))
