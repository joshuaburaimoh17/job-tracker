from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.db.models import Count, Q
from datetime import timedelta, date
import json
from .models import Application
from .forms import ApplicationForm


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
