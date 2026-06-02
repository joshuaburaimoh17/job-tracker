from datetime import date

from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import ApplicationForm, JobLeadConfirmForm, URLPasteForm
from .models import Application, JobLead

_VALID_SORT_KEYS = {'date_applied', '-date_applied', 'company', 'status'}


# ── Applications ─────────────────────────────────────────────────────────────

def dashboard(request):
    return render(request, 'tracker/dashboard.html')


def application_list(request):
    qs = Application.objects.all()

    search = request.GET.get('search', '').strip()
    status_filter = request.GET.get('status', '').strip()
    sort = request.GET.get('sort', '-date_applied').strip()

    if search:
        qs = qs.filter(Q(company__icontains=search) | Q(role__icontains=search))
    if status_filter:
        qs = qs.filter(status=status_filter)
    if sort in _VALID_SORT_KEYS:
        qs = qs.order_by(sort)

    return render(request, 'tracker/application_list.html', {
        'applications': qs,
        'search': search,
        'status_filter': status_filter,
        'sort': sort,
        'status_choices': Application.STATUS_CHOICES,
        'total': qs.count(),
    })


def application_add(request):
    if request.method == 'POST':
        form = ApplicationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Application added.')
            return redirect('tracker:application_list')
    else:
        form = ApplicationForm(initial={'date_applied': date.today()})
    return render(request, 'tracker/application_form.html', {'form': form})


def application_detail(request, pk):
    application = get_object_or_404(Application, pk=pk)
    return render(request, 'tracker/application_detail.html', {
        'application': application,
        'status_choices': Application.STATUS_CHOICES,
    })


def application_edit(request, pk):
    application = get_object_or_404(Application, pk=pk)
    if request.method == 'POST':
        form = ApplicationForm(request.POST, instance=application)
        if form.is_valid():
            form.save()
            messages.success(request, 'Application updated.')
            return redirect('tracker:application_detail', pk=pk)
    else:
        form = ApplicationForm(instance=application)
    return render(request, 'tracker/application_form.html', {
        'form': form,
        'application': application,
    })


def application_delete(request, pk):
    application = get_object_or_404(Application, pk=pk)
    if request.method == 'POST':
        application.delete()
        messages.success(request, 'Application deleted.')
        return redirect('tracker:application_list')
    return render(request, 'tracker/application_confirm_delete.html', {
        'application': application,
    })


@require_POST
def update_status(request, pk):
    application = get_object_or_404(Application, pk=pk)
    new_status = request.POST.get('status', '')
    valid_statuses = [choice[0] for choice in Application.STATUS_CHOICES]
    if new_status in valid_statuses:
        application.status = new_status
        application.save()
        messages.success(request, f'Status updated to {application.get_status_display()}.')
    referer = request.META.get('HTTP_REFERER')
    if referer:
        return redirect(referer)
    return redirect('tracker:application_detail', pk=pk)


# ── Job Queue ─────────────────────────────────────────────────────────────────

_TAB_STATUS = {
    'new': JobLead.STATUS_NEW,
    'ready': JobLead.STATUS_READY,
    'applied': JobLead.STATUS_APPLIED,
    'dismissed': JobLead.STATUS_DISMISSED,
}


def job_queue(request):
    from .services.utils import has_location_mismatch

    tab = request.GET.get('tab', 'new')
    if tab not in _TAB_STATUS:
        tab = 'new'

    leads = JobLead.objects.filter(status=_TAB_STATUS[tab])
    flagged_pks = {lead.pk for lead in leads if has_location_mismatch(lead)}

    tabs = [
        ('new', 'New', JobLead.objects.filter(status=JobLead.STATUS_NEW).count()),
        ('ready', 'Ready to Apply', JobLead.objects.filter(status=JobLead.STATUS_READY).count()),
        ('applied', 'Applied', JobLead.objects.filter(status=JobLead.STATUS_APPLIED).count()),
        ('dismissed', 'Dismissed', JobLead.objects.filter(status=JobLead.STATUS_DISMISSED).count()),
    ]

    return render(request, 'tracker/job_queue.html', {
        'leads': leads,
        'tab': tab,
        'tabs': tabs,
        'flagged_pks': flagged_pks,
    })


def job_lead_detail(request, pk):
    from .services.utils import has_location_mismatch

    lead = get_object_or_404(JobLead, pk=pk)
    diff = None
    if lead.cv_original_text and lead.cv_tailored_text:
        from .services.cv_tailor import compute_diff
        diff = compute_diff(lead.cv_original_text, lead.cv_tailored_text)
    return render(request, 'tracker/job_lead_detail.html', {
        'lead': lead,
        'is_flagged': has_location_mismatch(lead),
        'diff': diff,
    })


@require_POST
def dismiss_lead(request, pk):
    lead = get_object_or_404(JobLead, pk=pk)
    lead.status = JobLead.STATUS_DISMISSED
    lead.save()
    messages.success(request, 'Lead dismissed.')
    return redirect('tracker:job_queue')


@require_POST
def mark_ready(request, pk):
    lead = get_object_or_404(JobLead, pk=pk)
    lead.status = JobLead.STATUS_READY
    lead.save()
    messages.success(request, 'Lead marked as ready to apply.')
    return redirect('tracker:job_lead_detail', pk=pk)


def add_from_url(request):
    if request.method == 'POST':
        action = request.POST.get('action', 'scrape')

        if action == 'scrape':
            url_form = URLPasteForm(request.POST)
            if url_form.is_valid():
                url = url_form.cleaned_data['url']
                try:
                    from .services.job_scraper import scrape_job_url
                    scraped = scrape_job_url(url)
                    confirm_form = JobLeadConfirmForm(initial={
                        'role': scraped['role'],
                        'company': scraped['company'],
                        'location': 'Dublin, Ireland',
                        'salary_range': '',
                        'job_description': scraped['job_description'],
                        'source_url': url,
                    })
                    return render(request, 'tracker/add_from_url.html', {
                        'step': 2,
                        'confirm_form': confirm_form,
                        'scraped_url': url,
                    })
                except Exception as e:
                    url_form.add_error('url', str(e))
            return render(request, 'tracker/add_from_url.html', {
                'step': 1,
                'url_form': url_form,
            })

        elif action == 'save':
            confirm_form = JobLeadConfirmForm(request.POST)
            if confirm_form.is_valid():
                lead = confirm_form.save()
                messages.success(request, 'Job lead saved.')
                return redirect('tracker:job_lead_detail', pk=lead.pk)
            return render(request, 'tracker/add_from_url.html', {
                'step': 2,
                'confirm_form': confirm_form,
                'scraped_url': request.POST.get('source_url', ''),
            })

    return render(request, 'tracker/add_from_url.html', {
        'step': 1,
        'url_form': URLPasteForm(),
    })


# ── CV Tailoring ──────────────────────────────────────────────────────────────

@require_POST
def tailor_cv_view(request, pk):
    lead = get_object_or_404(JobLead, pk=pk)
    try:
        from .services.cv_tailor import tailor_cv_for_lead
        result = tailor_cv_for_lead(lead)
        lead.cv_original_text = result['original_text']
        lead.cv_tailored_text = result['tailored_text']
        lead.cv_changes = result['changes_made']
        lead.cv_path = result['cv_path']
        lead.save(update_fields=['cv_original_text', 'cv_tailored_text', 'cv_changes', 'cv_path'])
        messages.success(request, 'CV tailored successfully.')
    except Exception as e:
        messages.error(request, f'CV tailoring failed: {e}')
    return redirect('tracker:job_lead_detail', pk=pk)


def download_cv(request, pk):
    import os
    from django.http import FileResponse
    lead = get_object_or_404(JobLead, pk=pk)
    if not lead.cv_path or not os.path.exists(lead.cv_path):
        messages.error(request, 'No tailored CV found for this lead.')
        return redirect('tracker:job_lead_detail', pk=pk)
    filename = os.path.basename(lead.cv_path)
    return FileResponse(open(lead.cv_path, 'rb'), as_attachment=True, filename=filename)


