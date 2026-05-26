from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.db.models import Count, Q
from datetime import timedelta, date
import json
from .models import Application, JobLead
from .forms import ApplicationForm, URLPasteForm, JobLeadConfirmForm


def dashboard(request):
    apps = Application.objects.all()
    total = apps.count()
    by_status = apps.values('status').annotate(count=Count('status'))
    recent = apps[:5]
    status_counts = {item['status']: item['count'] for item in by_status}
    follow_ups = apps.filter(
        follow_up_date__lte=date.today() + timedelta(days=3),
        follow_up_date__gte=date.today(),
        status__in=['applied', 'interview_scheduled', 'interview_done']
    )
    context = {
        'total': total,
        'status_counts': status_counts,
        'recent': recent,
        'follow_ups': follow_ups,
    }
    return render(request, 'tracker/dashboard.html', context)


def application_list(request):
    apps = Application.objects.all()
    status_filter = request.GET.get('status', '')
    search = request.GET.get('search', '')
    sort = request.GET.get('sort', '-date_applied')
    if status_filter:
        apps = apps.filter(status=status_filter)
    if search:
        apps = apps.filter(Q(company__icontains=search) | Q(role__icontains=search))
    valid_sorts = ['date_applied', '-date_applied', 'company', 'status']
    if sort in valid_sorts:
        apps = apps.order_by(sort)
    context = {
        'applications': apps,
        'status_filter': status_filter,
        'search': search,
        'sort': sort,
        'status_choices': Application.STATUS_CHOICES,
    }
    return render(request, 'tracker/application_list.html', context)


def application_add(request):
    if request.method == 'POST':
        form = ApplicationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Application added successfully.')
            return redirect('application_list')
    else:
        form = ApplicationForm(initial={'date_applied': date.today()})
    return render(request, 'tracker/application_form.html', {'form': form, 'action': 'Add'})


def application_edit(request, pk):
    app = get_object_or_404(Application, pk=pk)
    if request.method == 'POST':
        form = ApplicationForm(request.POST, instance=app)
        if form.is_valid():
            form.save()
            messages.success(request, 'Application updated.')
            return redirect('application_list')
    else:
        form = ApplicationForm(instance=app)
    return render(request, 'tracker/application_form.html', {'form': form, 'action': 'Edit'})


def application_delete(request, pk):
    app = get_object_or_404(Application, pk=pk)
    if request.method == 'POST':
        app.delete()
        messages.success(request, 'Application deleted.')
        return redirect('application_list')
    return render(request, 'tracker/application_confirm_delete.html', {'application': app})


def application_detail(request, pk):
    app = get_object_or_404(Application, pk=pk)
    return render(request, 'tracker/application_detail.html', {'application': app})


def kanban(request):
    statuses = Application.STATUS_CHOICES
    board = {}
    for key, label in statuses:
        board[key] = {
            'label': label,
            'applications': Application.objects.filter(status=key)
        }
    return render(request, 'tracker/kanban.html', {'board': board})


def update_status(request, pk):
    app = get_object_or_404(Application, pk=pk)
    if request.method == 'POST':
        new_status = request.POST.get('status')
        valid_statuses = [s[0] for s in Application.STATUS_CHOICES]
        if new_status in valid_statuses:
            app.status = new_status
            app.save()
    return redirect(request.META.get('HTTP_REFERER', 'kanban'))


def job_queue(request):
    status_filter = request.GET.get('status', 'new')
    leads = JobLead.objects.filter(status=status_filter)
    context = {
        'leads': leads,
        'status_filter': status_filter,
        'new_count': JobLead.objects.filter(status='new').count(),
        'ready_count': JobLead.objects.filter(status='ready').count(),
        'status_tabs': [
            ('new', 'New'),
            ('ready', 'Ready to Apply'),
            ('applied', 'Applied'),
            ('dismissed', 'Dismissed'),
        ],
    }
    return render(request, 'tracker/job_queue.html', context)


def job_lead_detail(request, pk):
    from .services.cv_tailor import compute_diff
    lead = get_object_or_404(JobLead, pk=pk)
    diff = None
    if lead.cv_original_text and lead.cv_tailored_text:
        diff = compute_diff(lead.cv_original_text, lead.cv_tailored_text)
    return render(request, 'tracker/job_lead_detail.html', {'lead': lead, 'diff': diff})


def tailor_cv_view(request, pk):
    from .services.cv_tailor import tailor_cv_for_lead
    lead = get_object_or_404(JobLead, pk=pk)
    if request.method == 'POST':
        try:
            result = tailor_cv_for_lead(lead)
            lead.cv_original_text = result['original_text']
            lead.cv_tailored_text = result['tailored_text']
            lead.cv_path = result['cv_path']
            lead.save(update_fields=['cv_original_text', 'cv_tailored_text', 'cv_path'])
            messages.success(request, 'CV tailored — review the changes below and approve when ready.')
        except Exception as exc:
            messages.error(request, f'CV tailoring failed: {exc}')
    return redirect('job_lead_detail', pk=pk)


def mark_ready(request, pk):
    lead = get_object_or_404(JobLead, pk=pk)
    if request.method == 'POST':
        lead.status = 'ready'
        lead.save(update_fields=['status'])
        messages.success(request, f'"{lead.role} at {lead.company}" marked as ready to apply.')
    return redirect('job_lead_detail', pk=pk)


def dismiss_lead(request, pk):
    lead = get_object_or_404(JobLead, pk=pk)
    if request.method == 'POST':
        lead.status = 'dismissed'
        lead.save()
        messages.success(request, f'Dismissed {lead.role} at {lead.company}.')
    return redirect('job_queue')


def add_from_url(request):
    """Two-step: paste URL → scrape → confirm/edit form → create JobLead."""
    from .services.job_scraper import scrape_job_url

    scraped = None
    url_form = URLPasteForm()
    confirm_form = None

    if request.method == 'POST':
        if 'url_submit' in request.POST:
            url_form = URLPasteForm(request.POST)
            if url_form.is_valid():
                url = url_form.cleaned_data['url']
                try:
                    scraped = scrape_job_url(url)
                    scraped['source_url'] = url
                    scraped['source'] = 'manual'
                    confirm_form = JobLeadConfirmForm(initial=scraped)
                except Exception as exc:
                    messages.error(request, f'Could not extract job data: {exc}')
                    confirm_form = JobLeadConfirmForm(initial={'source_url': url})

        elif 'confirm_submit' in request.POST:
            confirm_form = JobLeadConfirmForm(request.POST)
            if confirm_form.is_valid():
                from .services.utils import clean_job_description
                lead = confirm_form.save(commit=False)
                lead.source = 'manual'
                lead.status = 'new'
                lead.job_description = clean_job_description(lead.job_description)
                lead.save()
                messages.success(request, f'Job lead added: {lead.role} at {lead.company}.')
                return redirect('job_lead_detail', pk=lead.pk)

    return render(request, 'tracker/add_from_url.html', {
        'url_form': url_form,
        'confirm_form': confirm_form,
    })


def apply_lead(request, pk):
    """Create an Application from a ready lead and open the job URL in a new tab."""
    lead = get_object_or_404(JobLead, pk=pk)
    if request.method == 'POST' and lead.status in ('new', 'ready'):
        app = Application.objects.create(
            company=lead.company,
            role=lead.role,
            date_applied=date.today(),
            status='applied',
            job_url=lead.source_url,
            job_description=lead.job_description,
            cv_path=lead.cv_path or '',
        )
        lead.application = app
        lead.status = 'applied'
        lead.save(update_fields=['application', 'status'])
        messages.success(request, f'Application recorded for {lead.role} at {lead.company}.')
        return render(request, 'tracker/apply_redirect.html', {
            'application': app,
            'lead': lead,
        })
    return redirect('job_lead_detail', pk=pk)


def send_digest_now(request):
    if request.method == 'POST':
        from django.core.management import call_command
        try:
            call_command('send_digest', force=True)
            messages.success(request, 'Digest email sent to joshuaburaimoh17@gmail.com.')
        except Exception as exc:
            messages.error(request, f'Could not send digest: {exc}')
    return redirect(request.META.get('HTTP_REFERER', 'job_queue'))


def analytics(request):
    apps = Application.objects.all()
    total = apps.count()
    by_status = {item['status']: item['count'] for item in apps.values('status').annotate(count=Count('status'))}
    responded = apps.filter(status__in=['interview_scheduled', 'interview_done', 'offer', 'rejected'])
    response_rate = round((responded.count() / total * 100), 1) if total > 0 else 0
    thirty_days_ago = date.today() - timedelta(days=30)
    recent_apps = apps.filter(date_applied__gte=thirty_days_ago)
    apps_per_day = recent_apps.values('date_applied').annotate(count=Count('id')).order_by('date_applied')
    apps_per_day_labels = [str(item['date_applied']) for item in apps_per_day]
    apps_per_day_data = [item['count'] for item in apps_per_day]
    context = {
        'total': total,
        'by_status': by_status,
        'response_rate': response_rate,
        'offers': by_status.get('offer', 0),
        'interviews': by_status.get('interview_scheduled', 0) + by_status.get('interview_done', 0),
        'rejected': by_status.get('rejected', 0),
        'apps_per_day_labels': json.dumps(apps_per_day_labels),
        'apps_per_day_data': json.dumps(apps_per_day_data),
        'status_labels': json.dumps(list(by_status.keys())),
        'status_data': json.dumps(list(by_status.values())),
    }
    return render(request, 'tracker/analytics.html', context)
