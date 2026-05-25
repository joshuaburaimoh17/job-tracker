from django.core.management.base import BaseCommand
from tracker.services.job_search import AdzunaSearcher, RSSSearcher, save_leads


class Command(BaseCommand):
    help = 'Search for new job leads and populate the queue'

    def handle(self, *args, **options):
        self.stdout.write('Searching Adzuna...')
        adzuna_jobs = AdzunaSearcher().run_all_searches()
        self.stdout.write(f'  {len(adzuna_jobs)} results from Adzuna')

        self.stdout.write('Searching RSS feeds...')
        rss_jobs = RSSSearcher().run_all_searches()
        self.stdout.write(f'  {len(rss_jobs)} results from RSS feeds')

        created, skipped = save_leads(adzuna_jobs + rss_jobs)
        self.stdout.write(
            self.style.SUCCESS(
                f'\nDone — {created} new leads added, {skipped} duplicates/invalid skipped.'
            )
        )
