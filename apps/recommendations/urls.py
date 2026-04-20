"""
URL patterns for AI recommendations.
"""
from django.urls import path
from . import views

app_name = 'recommendations'

urlpatterns = [
    path('', views.recommended_jobs, name='recommended'),
    path('skill-gaps/', views.skill_gap_insights, name='skill_gaps'),
    path('location-demand/', views.location_demand, name='location_demand'),
    path('track-action/', views.track_recommendation_action, name='track_action'),
    path('refresh/', views.refresh_recommendations, name='refresh'),
]