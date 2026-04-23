"""
URL patterns for admin dashboard.
"""
from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    # Main dashboard
    path('', views.dashboard_home, name='home'),
    
    # Ingestion management
    path('ingestion/', views.ingestion_dashboard, name='ingestion'),
    path('ingestion/upload-csv/', views.upload_csv, name='upload_csv'),
    path('ingestion/preview-csv/', views.preview_csv_columns, name='preview_csv'),
    path('ingestion/source/create/', views.DataSourceCreateView.as_view(), name='create_source'),
    path('ingestion/source/<int:pk>/update/', views.DataSourceUpdateView.as_view(), name='update_source'),
    path('ingestion/source/<int:pk>/sync/', views.trigger_sync, name='trigger_sync'),
    
    # Job approval
    path('jobs/approval/', views.job_approval_queue, name='job_approval'),
    path('jobs/<int:pk>/approve/', views.approve_job, name='approve_job'),
    path('jobs/<int:pk>/reject/', views.reject_job, name='reject_job'),
    
    # Bulk Actions
    path('jobs/bulk-approve/', views.bulk_approve_jobs, name='bulk_approve_jobs'),
    path('jobs/bulk-delete/', views.bulk_delete_jobs, name='bulk_delete_jobs'),
    

    # Reports management
    path('reports/', views.reports_dashboard, name='reports'),
    path('reports/<int:pk>/resolve/', views.resolve_report, name='resolve_report'),

    # Employer Verification
    path('employers/verify/', views.employer_verification_queue, name='employer_verification'),
    path('employers/<int:pk>/verify/', views.verify_employer, name='verify_employer'),
    path('employers/<int:pk>/unverify/', views.unverify_employer, name='unverify_employer'),
    
    # Analytics
    path('analytics/', views.analytics_dashboard, name='analytics'),
    
    
    # System Health
    path('system-health/', views.system_health, name='system_health'),


    # Admin job posting (Quick Add) - THIS WAS MISSING!
    path('jobs/create/', views.admin_create_job, name='admin_create_job'),
    
    # Superuser only
    path('admin/create/', views.create_admin_user, name='create_admin_user'),
    path('settings/', views.system_settings, name='system_settings'),

]