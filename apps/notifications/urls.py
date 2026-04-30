"""
URL patterns for notifications.
"""
from django.urls import path
from . import views

app_name = 'notifications'

urlpatterns = [
    # Notification list
    path('', views.notification_list, name='list'),
    path('<int:pk>/read/', views.mark_as_read, name='mark_read'),
    path('mark-all-read/', views.mark_all_read, name='mark_all_read'),
    
    # Preferences
    path('preferences/', views.notification_preferences, name='preferences'),
    
    # Job Alerts (Job Seekers only)
    path('alerts/', views.job_alerts, name='job_alerts'),
    path('alerts/create/', views.create_job_alert, name='create_alert'),
    path('alerts/<int:pk>/toggle/', views.toggle_alert, name='toggle_alert'),
    path('alerts/<int:pk>/delete/', views.delete_alert, name='delete_alert'),
    
    # Digests
    path('digest/<int:pk>/', views.digest_detail, name='digest_detail'),
    
    # API endpoints
    path('api/unread-count/', views.get_unread_count, name='unread_count'),
    path('api/recent/', views.recent_notifications_api, name='recent_notifications_api'),
    path('api/alerts/', views.job_alerts_api, name='alerts_api'),
]