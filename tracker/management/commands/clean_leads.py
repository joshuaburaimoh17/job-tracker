from django.core.management.base import BaseCommand
from tracker.models import JobLead
from tracker.services.job_search import _should_include


class Command(BaseCommand):
    help = 'Dismiss existing new leads that fail the current relevance filter.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be dismissed without saving.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        leads = JobLead.objects.filter(status='new')
        to_dismiss = []

        for lead in leads:
            if not _should_include(lead.role, lead.job_description):
                to_dismiss.append(lead.pk)
                prefix = '[dry-run] ' if dry_run else ''
                self.stdout.write(f'  {prefix}Dismissing: {lead.role} at {lead.company}')

        if not dry_run and to_dismiss:
            JobLead.objects.filter(pk__in=to_dismiss).update(status='dismissed')

        label = '[dry-run] ' if dry_run else ''
        self.stdout.write(self.style.SUCCESS(
            f'{label}Done — {len(to_dismiss)} lead(s) dismissed.'
        ))
