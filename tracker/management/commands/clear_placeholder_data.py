from django.core.management.base import BaseCommand

from tracker.models import Application, JobLead


class Command(BaseCommand):
    help = (
        'Delete ALL Application and JobLead records. '
        'Without --yes this is a dry run that only reports counts.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--yes',
            action='store_true',
            help='Actually delete the data. Without this flag nothing is changed.',
        )

    def handle(self, *args, **options):
        lead_count = JobLead.objects.count()
        app_count = Application.objects.count()

        if not options['yes']:
            self.stdout.write(
                f'DRY RUN: would delete {lead_count} job lead(s) and '
                f'{app_count} application(s). Re-run with --yes to delete.'
            )
            return

        JobLead.objects.all().delete()
        Application.objects.all().delete()

        self.stdout.write(self.style.SUCCESS(
            f'Deleted {lead_count} job lead(s) and {app_count} application(s). '
            f'Remaining: {JobLead.objects.count()} leads, '
            f'{Application.objects.count()} applications.'
        ))
