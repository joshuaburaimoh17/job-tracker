from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('applications/', views.application_list, name='application_list'),
    path('applications/add/', views.application_add, name='application_add'),
    path('applications/<int:pk>/edit/', views.application_edit, name='application_edit'),
    path('applications/<int:pk>/delete/', views.application_delete, name='application_delete'),
    path('applications/<int:pk>/', views.application_detail, name='application_detail'),
    path('kanban/', views.kanban, name='kanban'),
    path('analytics/', views.analytics, name='analytics'),
    path('applications/<int:pk>/update-status/', views.update_status, name='update_status'),
]
