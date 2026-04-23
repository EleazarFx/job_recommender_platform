"""
URL patterns for AI recommendations.
"""
from django.urls import path
from . import views

app_name = 'recommendations'

urlpatterns = [
    # Main views
    path('', views.recommended_jobs, name='recommended'),
    path('skill-gaps/', views.skill_gap_insights, name='skill_gaps'),
    path('location-demand/', views.location_demand, name='location_demand'),
    
    # Actions
    path('track-action/', views.track_recommendation_action, name='track_action'),
    path('refresh/', views.refresh_recommendations, name='refresh'),
    path('refresh-analysis/', views.refresh_skill_analysis, name='refresh_analysis'),
    
    # API endpoints
    path('api/match/<int:job_id>/', views.get_match_score_api, name='match_score_api'),
    path('api/similar/<int:job_id>/', views.similar_jobs_api, name='similar_jobs_api'),
    path('api/skill-demand/', views.skill_demand_api, name='skill_demand_api'),
]