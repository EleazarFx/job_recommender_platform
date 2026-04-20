"""
URL patterns for job listings and interactions.
"""
from django.urls import path
from . import views

app_name = 'jobs'

urlpatterns = [
    # Job listing and search
    path('', views.job_list, name='list'),
    path('export/', views.export_jobs_csv, name='export_csv'),
    
    # Job detail
    path('<int:pk>/', views.job_detail, name='detail'),
    path('<int:pk>/<slug:slug>/', views.job_detail, name='detail_with_slug'),
    
    # Job interactions
    path('<int:pk>/save/', views.save_job, name='save'),
    path('<int:pk>/apply/', views.apply_job, name='apply'),
    path('<int:pk>/report/', views.report_job, name='report'),
    
    # Category views
    path('category/<slug:slug>/', views.category_jobs, name='category'),
    
    # User's saved jobs
    path('saved/', views.saved_jobs, name='saved'),
    
    # Job posting (for users/employers)
    path('post/', views.post_job, name='post'),
    path('my-jobs/', views.my_jobs, name='my_jobs'),
    path('<int:pk>/delete/', views.delete_job, name='delete'),
    path('<int:pk>/extend/', views.extend_job, name='extend'),
]