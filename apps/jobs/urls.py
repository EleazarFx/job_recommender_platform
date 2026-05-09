"""
URL patterns for job listings and interactions.
"""
from django.urls import path
from . import views

app_name = 'jobs'

urlpatterns = [
    # Public views
    path('', views.job_list, name='list'),
    path('export/', views.export_jobs_csv, name='export_csv'),
    path('category/<slug:slug>/', views.category_jobs, name='category'),
    
    # Employer actions (must come BEFORE generic <int:pk> pattern)
    path('post/', views.post_job, name='post'),
    path('my-jobs/', views.my_jobs, name='my_jobs'),
    
    # Job seeker actions (must come BEFORE generic <int:pk> pattern)
    path('saved/', views.saved_jobs, name='saved'),
    
    # Specific job actions (must come BEFORE generic <int:pk> pattern)
    path('<int:pk>/delete/', views.delete_job, name='delete'),
    path('<int:pk>/extend/', views.extend_job, name='extend'),
    path('<int:pk>/edit/', views.edit_job, name='edit'),
    path('<int:pk>/save/', views.save_job, name='save'),
    path('<int:pk>/apply/', views.apply_job, name='apply'),
    path('<int:pk>/report/', views.report_job, name='report'),
    path('<int:pk>/applicants/', views.view_applicants, name='view_applicants'),
    
    # Job detail (generic patterns MUST come LAST)
    path('<int:pk>/<slug:slug>/', views.job_detail, name='detail_with_slug'),
    path('<int:pk>/', views.job_detail, name='detail'),
]