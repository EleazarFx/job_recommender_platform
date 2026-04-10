"""
URL patterns for admin dashboard.
"""
from django.urls import path
from . import views


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
    
    # Reports management
    path('reports/', views.reports_dashboard, name='reports'),
    path('reports/<int:pk>/resolve/', views.resolve_report, name='resolve_report'),
]