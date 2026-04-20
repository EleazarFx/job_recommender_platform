"""
Views for AI recommendations.
"""

#ADDED  DURING DEBUGGING


from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse


@login_required
def recommended_jobs(request):
    return render(request, 'recommendations/recommended.html', {
        'page_obj': [],
        'total_recommendations': 0,
        'has_completed_profile': True,
    })


@login_required
def skill_gap_insights(request):
    return render(request, 'recommendations/skill_gaps.html')


@login_required
def location_demand(request):
    return render(request, 'recommendations/location_demand.html')


@login_required
def track_recommendation_action(request):
    return JsonResponse({'success': True})


@login_required
def refresh_recommendations(request):
    return JsonResponse({'success': True})