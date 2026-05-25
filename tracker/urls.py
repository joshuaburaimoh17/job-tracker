from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('applications/', views.application_list, name='application_list'),
    path('applications/<int:pk>/edit/', views.application_edit, name='application_edit'),
    path('applications/<int:pk>/delete/', views.application_delete, name='application_delete'),
    path('applications/<int:pk>/', views.application_detail, name='application_detail'),
    path('kanban/', views.kanban, name='kanban'),
    path('analytics/', views.analytics, name='analytics'),
    path('applications/<int:pk>/update-status/', views.update_status, name='update_status'),
    # Job queue
    path('queue/', views.job_queue, name='job_queue'),
    path('queue/add/', views.add_from_url, name='add_from_url'),
    path('queue/<int:pk>/', views.job_lead_detail, name='job_lead_detail'),
    path('queue/<int:pk>/dismiss/', views.dismiss_lead, name='dismiss_lead'),
    path('queue/<int:pk>/tailor/', views.tailor_cv_view, name='tailor_cv'),
    path('queue/<int:pk>/mark-ready/', views.mark_ready, name='mark_ready'),
    path('queue/<int:pk>/apply/', views.apply_lead, name='apply_lead'),
]
