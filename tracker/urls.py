from django.urls import path

from . import views

app_name = 'tracker'

urlpatterns = [
    # Dashboard
    path('', views.dashboard, name='dashboard'),

    # Applications
    path('applications/', views.application_list, name='application_list'),
    path('applications/add/', views.application_add, name='application_add'),
    path('applications/<int:pk>/', views.application_detail, name='application_detail'),
    path('applications/<int:pk>/edit/', views.application_edit, name='application_edit'),
    path('applications/<int:pk>/delete/', views.application_delete, name='application_delete'),
    path('applications/<int:pk>/status/', views.update_status, name='update_status'),

    # Job Queue — static routes must come before <int:pk>
    path('queue/', views.job_queue, name='job_queue'),
    path('queue/add/', views.add_from_url, name='add_from_url'),
path('queue/<int:pk>/', views.job_lead_detail, name='job_lead_detail'),
    path('queue/<int:pk>/dismiss/', views.dismiss_lead, name='dismiss_lead'),
    path('queue/<int:pk>/ready/', views.mark_ready, name='mark_ready'),
]
