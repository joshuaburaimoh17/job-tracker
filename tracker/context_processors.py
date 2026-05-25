from .models import JobLead


def job_queue_counts(request):
    return {
        'new_lead_count': JobLead.objects.filter(status='new').count(),
    }
