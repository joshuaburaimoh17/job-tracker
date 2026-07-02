from django.contrib import admin

from .models import Application, JobLead


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ['role', 'company', 'status', 'date_applied', 'follow_up_date']


@admin.register(JobLead)
class JobLeadAdmin(admin.ModelAdmin):
    list_display = ['role', 'company', 'location', 'status', 'date_found']
