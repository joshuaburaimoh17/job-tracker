from datetime import date, timedelta

from django.contrib import messages
from django.db.models import Count, Q
from django.db.models.functions import TruncWeek
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import ApplicationForm, JobLeadForm
from .models import Application, JobLead

_VALID_SORT_KEYS = {'date_applied', '-date_applied', 'company', 'status'}


def _status_counts():
    """Counts for every Application status, zero-filled, in STATUS_CHOICES order."""
    raw = dict(
        Application.objects.values('status')
        .annotate(n=Count('id'))
        .values_list('status', 'n')
    )
    return [
        {'status': value, 'label': label, 'count': raw.get(value, 0)}
        for value, label in Application.STATUS_CHOICES
    ]


# ── Dashboard ─────────────────────────────────────────────────────────────────

def dashboard(request):
    today = date.today()
    status_counts = _status_counts()
    offers = next(
        (s['count'] for s in status_counts if s['status'] == Application.STATUS_OFFER), 0
    )

    return render(request, 'tracker/dashboard.html', {
        'total': Application.objects.count(),
        'last_7_days': Application.objects.filter(
            date_applied__gte=today - timedelta(days=7)
        ).count(),
        'leads_in_queue': JobLead.objects.filter(
            status__in=[JobLead.STATUS_NEW, JobLead.STATUS_READY]
        ).count(),
        'offers': offers,
        'status_counts': status_counts,
        'recent_applications': Application.objects.all()[:5],
    })


def analytics(request):
    total = Application.objects.count()
    status_counts = _status_counts()

    responded = Application.objects.exclude(status=Application.STATUS_APPLIED).count()
    response_rate = round(responded / total * 100) if total else 0

    # Applications per week, last 12 ISO weeks, zero-filled
    today = date.today()
    this_week_start = today - timedelta(days=today.weekday())
    week_starts = [this_week_start - timedelta(weeks=i) for i in range(11, -1, -1)]

    weekly_raw = {
        row['week'].date() if hasattr(row['week'], 'date') else row['week']: row['n']
        for row in (
            Application.objects.filter(date_applied__gte=week_starts[0])
            .annotate(week=TruncWeek('date_applied'))
            .values('week')
            .annotate(n=Count('id'))
        )
    }
    weekly_labels = [w.strftime('%b %d') for w in week_starts]
    weekly_counts = [weekly_raw.get(w, 0) for w in week_starts]

    chart_data = {
        'weekly_labels': weekly_labels,
        'weekly_counts': weekly_counts,
        'status_labels': [s['label'] for s in status_counts],
        'status_values': [s['count'] for s in status_counts],
    }

    return render(request, 'tracker/analytics.html', {
        'total': total,
        'response_rate': response_rate,
        'responded': responded,
        'status_counts': status_counts,
        'chart_data': chart_data,
    })


# ── Applications ─────────────────────────────────────────────────────────────


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
            application = form.save(commit=False)
            application.status_updated_at = timezone.now()
            application.save()
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
        old_status = application.status
        form = ApplicationForm(request.POST, instance=application)
        if form.is_valid():
            application = form.save(commit=False)
            if application.status != old_status:
                application.status_updated_at = timezone.now()
            application.save()
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
        if new_status != application.status:
            application.status_updated_at = timezone.now()
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


@require_POST
def mark_applied(request, pk):
    """Convert a lead into a tracked Application and link the two."""
    lead = get_object_or_404(JobLead, pk=pk)

    if lead.application_id:
        messages.info(request, 'This lead already has a linked application.')
        return redirect('tracker:application_detail', pk=lead.application_id)

    application = Application.objects.create(
        company=lead.company,
        role=lead.role,
        location=lead.location,
        salary_range=lead.salary_range,
        date_applied=date.today(),
        status=Application.STATUS_APPLIED,
        status_updated_at=timezone.now(),
        job_url=lead.source_url,
        job_description=lead.job_description,
    )
    lead.application = application
    lead.status = JobLead.STATUS_APPLIED
    lead.save(update_fields=['application', 'status'])

    messages.success(request, f'Application created for {lead.role} at {lead.company}.')
    return redirect('tracker:application_detail', pk=application.pk)


def add_job(request):
    if request.method == 'POST':
        form = JobLeadForm(request.POST)
        if form.is_valid():
            lead = form.save()
            messages.success(request, 'Job lead added.')
            return redirect('tracker:job_lead_detail', pk=lead.pk)
    else:
        form = JobLeadForm()
    return render(request, 'tracker/add_job.html', {'form': form})


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
        lead.cv_tailored_json = result['tailored_json']
        lead.save(update_fields=['cv_original_text', 'cv_tailored_text', 'cv_changes', 'cv_tailored_json'])
        messages.success(request, 'CV tailored successfully.')
    except Exception as e:
        messages.error(request, f'CV tailoring failed: {e}')
    return redirect('tracker:job_lead_detail', pk=pk)


def download_cv(request, pk):
    from django.http import FileResponse
    lead = get_object_or_404(JobLead, pk=pk)

    if lead.cv_tailored_json:
        from .services.cv_tailor import build_tailored_docx
        try:
            buffer, filename = build_tailored_docx(lead)
        except Exception as e:
            messages.error(request, f'Could not generate the tailored CV: {e}')
            return redirect('tracker:job_lead_detail', pk=pk)
        return FileResponse(buffer, as_attachment=True, filename=filename)

    messages.error(request, 'No tailored CV available — run Tailor CV first.')
    return redirect('tracker:job_lead_detail', pk=pk)


