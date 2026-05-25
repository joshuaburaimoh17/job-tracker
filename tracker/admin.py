from django.contrib import admin
from .models import Application, JobLead


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ('company', 'role', 'status', 'date_applied')
    list_filter = ('status',)
    search_fields = ('company', 'role')


@admin.register(JobLead)
class JobLeadAdmin(admin.ModelAdmin):
    list_display = ('company', 'role', 'location', 'source', 'status', 'date_found')
    list_filter = ('status', 'source')
    search_fields = ('company', 'role')
