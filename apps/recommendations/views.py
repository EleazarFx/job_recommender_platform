"""
Views for AI-powered job recommendations with scikit-learn integration.
"""
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q, Count, F
from datetime import timedelta
import json

from apps.jobs.models import JobVacancy, JobCategory, JobView, SavedJob
from apps.accounts.decorators import job_seeker_required
from .models import (
    JobMatchScore, RecommendationLog, SkillGapAnalysis, 
    LocationDemandStats, UserInteractionVector
)
from .matching_engine import JobMatchingEngine, SkillGapAnalyzer, LocationDemandAnalyzer


# ============================================
# JOB SEEKER ONLY VIEWS
# ============================================

@job_seeker_required
def recommended_jobs(request):
    """
    Display personalized job recommendations for job seekers.
    Uses pre-calculated match scores for instant loading.
    """
    user = request.user
    
    # Check if user has completed profile
    has_completed_profile = user.profile_completion_percentage >= 50
    
    if not has_completed_profile:
        messages.info(
            request, 
            'Complete your profile to get personalized job recommendations!'
        )
        return render(request, 'recommendations/recommended.html', {
            'page_obj': [],
            'total_recommendations': 0,
            'has_completed_profile': False,
        })
    
    # Get recent match scores (expires after 6 hours)
    recent_scores = JobMatchScore.objects.filter(
        user=user,
        expires_at__gte=timezone.now(),
        match_score__gte=30  # Only show decent matches
    ).select_related('job', 'job__category').order_by('-match_score')
    
    # If no recent scores, calculate on-the-fly (limited to avoid timeout)
    if recent_scores.count() == 0:
        try:
            engine = JobMatchingEngine(user)
            matches = engine.calculate_matches(limit=30, save_results=True)
            recent_scores = JobMatchScore.objects.filter(
                user=user,
                expires_at__gte=timezone.now(),
                match_score__gte=30
            ).select_related('job', 'job__category').order_by('-match_score')
        except Exception as e:
            messages.warning(request, 'Unable to calculate recommendations. Please try again later.')
            recent_scores = []
    
    total_recommendations = recent_scores.count()
    
    # Pagination
    paginator = Paginator(recent_scores, 12)
    page = request.GET.get('page', 1)
    
    try:
        page_obj = paginator.page(page)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)
    
    # Log these recommendations for tracking
    for score in page_obj:
        RecommendationLog.objects.get_or_create(
            user=user,
            job=score.job,
            recommendation_type='HOMEPAGE',
            defaults={
                'match_score': score.match_score,
                'position_in_list': list(page_obj).index(score)
            }
        )
    
    # Get skill gap insights for sidebar
    skill_gap = None
    try:
        skill_gap = SkillGapAnalysis.objects.filter(
            user=user,
            last_updated__gte=timezone.now() - timedelta(days=1)
        ).first()
    except SkillGapAnalysis.DoesNotExist:
        pass
    
    # Get saved job IDs for button states
    saved_job_ids = list(SavedJob.objects.filter(
        user=user
    ).values_list('job_id', flat=True))
    
    context = {
        'page_obj': page_obj,
        'total_recommendations': total_recommendations,
        'has_completed_profile': has_completed_profile,
        'skill_gap': skill_gap,
        'saved_job_ids': saved_job_ids,
    }
    
    return render(request, 'recommendations/recommended.html', context)


@job_seeker_required
def skill_gap_insights(request):
    """
    Display skill gap insights for the user.
    No teaching - just factual insights about in-demand skills.
    """
    user = request.user
    
    # Get or calculate skill gap analysis
    try:
        analysis = SkillGapAnalysis.objects.get(user=user)
        
        # Refresh if older than 6 hours
        if analysis.last_updated < timezone.now() - timedelta(hours=6):
            analyzer = SkillGapAnalyzer(user)
            analyzer.analyze()
            analysis.refresh_from_db()
    except SkillGapAnalysis.DoesNotExist:
        analyzer = SkillGapAnalyzer(user)
        analyzer.analyze()
        analysis = SkillGapAnalysis.objects.get(user=user)
    
    # Get user's current skills
    user_skills = user.profile.get_skills_list() if hasattr(user, 'profile') else []
    
    # Get recommended jobs based on missing skills
    recommended_jobs = []
    if analysis.top_missing_skills:
        top_skill = analysis.top_missing_skills[0]['skill']
        recommended_jobs = JobVacancy.objects.filter(
            is_approved=True,
            expiry_date__gte=timezone.now().date(),
            required_skills__icontains=top_skill
        ).exclude(
            required_skills__in=user_skills
        ).order_by('-date_posted')[:5]
    
    context = {
        'analysis': analysis,
        'user_skills': user_skills,
        'recommended_jobs': recommended_jobs,
        'jobs_analyzed': analysis.jobs_analyzed,
        'last_updated': analysis.last_updated,
    }
    
    return render(request, 'recommendations/skill_gaps.html', context)


@login_required
def location_demand(request):
    """
    Display job demand by location.
    Malawi-focused with international comparison.
    Access: All authenticated users
    """
    # Get all location stats
    all_stats = LocationDemandStats.objects.filter(
        calculated_at__gte=timezone.now() - timedelta(days=1)
    ).order_by('-active_jobs')
    
    # If stats are stale, recalculate
    if all_stats.count() == 0:
        LocationDemandAnalyzer.calculate_all_locations()
        all_stats = LocationDemandStats.objects.all().order_by('-active_jobs')
    
    # Malawi cities
    malawi_cities = ['Lilongwe', 'Blantyre', 'Mzuzu', 'Zomba', 'Mangochi', 'Kasungu']
    malawi_stats = [s for s in all_stats if s.location_name in malawi_cities]
    other_stats = [s for s in all_stats if s.location_name not in malawi_cities][:10]
    
    # Calculate totals
    total_malawi_jobs = sum(s.active_jobs for s in malawi_stats)
    total_international_jobs = sum(s.active_jobs for s in other_stats)
    total_jobs = total_malawi_jobs + total_international_jobs
    
    # Get user's preferred location for comparison
    user_location_match = None
    if request.user.is_authenticated and hasattr(request.user, 'profile'):
        user_locations = request.user.profile.get_preferred_locations_list()
        if user_locations:
            user_location_match = next(
                (s for s in all_stats if s.location_name in user_locations), 
                None
            )
    
    context = {
        'malawi_stats': malawi_stats,
        'other_stats': other_stats,
        'total_malawi_jobs': total_malawi_jobs,
        'total_international_jobs': total_international_jobs,
        'total_jobs': total_jobs,
        'user_location_match': user_location_match,
        'last_updated': all_stats.first().calculated_at if all_stats else timezone.now(),
    }
    
    return render(request, 'recommendations/location_demand.html', context)


# ============================================
# AJAX/API ENDPOINTS
# ============================================

@job_seeker_required
@require_POST
def track_recommendation_action(request):
    """
    Track user actions on recommendations for learning loop.
    """
    job_id = request.POST.get('job_id')
    action = request.POST.get('action')  # 'save', 'ignore', 'view', 'apply'
    
    if not job_id or not action:
        return JsonResponse({'success': False, 'error': 'Missing parameters'})
    
    try:
        log = RecommendationLog.objects.filter(
            user=request.user,
            job_id=job_id
        ).first()
        
        if log:
            if action == 'save':
                log.was_saved = True
            elif action == 'ignore':
                log.was_ignored = True
            elif action == 'view':
                log.was_viewed = True
            
            log.save()
            
            # Update interaction vector for better future recommendations
            update_user_interaction_vector(request.user, job_id, action)
        
        return JsonResponse({'success': True})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@job_seeker_required
def refresh_recommendations(request):
    """
    AJAX endpoint to trigger background recommendation refresh.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'})
    
    try:
        from background_task import background
        
        @background(schedule=1)
        def recalculate_task(user_id):
            from apps.accounts.models import User
            user = User.objects.get(id=user_id)
            engine = JobMatchingEngine(user)
            engine.calculate_matches(limit=50, save_results=True)
        
        recalculate_task(request.user.id)
        
        return JsonResponse({
            'success': True,
            'message': 'Recommendations are being refreshed. This may take a minute.'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': 'Background tasks not available. Please try again later.'
        })


@job_seeker_required
def get_match_score_api(request, job_id):
    """
    API endpoint to get match score for a specific job.
    """
    if not request.user.is_authenticated:
        return JsonResponse({'match_score': None})
    
    try:
        match_score = JobMatchScore.objects.get(
            user=request.user,
            job_id=job_id
        )
        
        return JsonResponse({
            'match_score': match_score.match_score,
            'skill_match': match_score.skill_match_score,
            'matched_skills': match_score.matched_skills,
            'missing_skills': match_score.missing_skills,
            'match_reason': match_score.match_reason,
        })
        
    except JobMatchScore.DoesNotExist:
        # Calculate on the fly
        job = get_object_or_404(JobVacancy, id=job_id, is_approved=True)
        engine = JobMatchingEngine(request.user)
        
        user_skills = request.user.profile.skills if hasattr(request.user, 'profile') else ""
        skill_score = engine._simple_skill_match(user_skills, [job.required_skills])[0]
        
        return JsonResponse({
            'match_score': round(skill_score * 100, 1),
            'skill_match': round(skill_score * 100, 1),
            'matched_skills': [],
            'missing_skills': [],
            'match_reason': 'Calculated on demand',
        })


@login_required
def similar_jobs_api(request, job_id):
    """
    API endpoint to get similar jobs based on skills.
    """
    job = get_object_or_404(JobVacancy, id=job_id, is_approved=True)
    
    similar_jobs = []
    if job.required_skills:
        first_skill = job.required_skills.split(',')[0].strip()
        similar = JobVacancy.objects.filter(
            is_approved=True,
            expiry_date__gte=timezone.now().date()
        ).exclude(id=job.id).filter(
            Q(required_skills__icontains=first_skill) | Q(category=job.category)
        ).order_by('-date_posted')[:6]
        
        similar_jobs = [{
            'id': j.id,
            'title': j.title,
            'company_name': j.company_name,
            'location_display': j.location_display,
            'date_posted': j.date_posted.strftime('%b %d, %Y'),
        } for j in similar]
    
    return JsonResponse({'similar_jobs': similar_jobs})


# ============================================
# HELPER FUNCTIONS
# ============================================

def update_user_interaction_vector(user, job_id, action):
    """
    Update user interaction vector for better recommendations.
    """
    try:
        vector, created = UserInteractionVector.objects.get_or_create(user=user)
        
        # Update based on action
        if action == 'view' and job_id not in vector.viewed_job_ids:
            vector.viewed_job_ids.append(job_id)
            vector.viewed_job_ids = vector.viewed_job_ids[-50:]  # Keep last 50
            
        elif action == 'save' and job_id not in vector.saved_job_ids:
            vector.saved_job_ids.append(job_id)
            
        elif action == 'apply' and job_id not in vector.applied_job_ids:
            vector.applied_job_ids.append(job_id)
        
        # Recalculate interaction weight
        interaction_count = len(vector.viewed_job_ids) + len(vector.saved_job_ids) * 2
        vector.interaction_weight = min(interaction_count / 50, 1.0)
        
        vector.save()
        
    except Exception as e:
        # Silently fail - interaction tracking shouldn't break the user experience
        pass


@login_required
def skill_demand_api(request):
    """
    API endpoint for skill demand data.
    """
    skill = request.GET.get('skill', '')
    
    if not skill:
        return JsonResponse({'success': False, 'error': 'Skill parameter required'})
    
    # Count jobs requiring this skill
    job_count = JobVacancy.objects.filter(
        is_approved=True,
        expiry_date__gte=timezone.now().date(),
        required_skills__icontains=skill
    ).count()
    
    # Get locations with this skill demand
    locations = JobVacancy.objects.filter(
        is_approved=True,
        expiry_date__gte=timezone.now().date(),
        required_skills__icontains=skill
    ).values('city').annotate(
        count=Count('id')
    ).order_by('-count')[:5]
    
    return JsonResponse({
        'success': True,
        'skill': skill,
        'job_count': job_count,
        'top_locations': list(locations),
    })


@job_seeker_required
def refresh_skill_analysis(request):
    """
    Force refresh skill gap analysis.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'})
    
    try:
        analyzer = SkillGapAnalyzer(request.user)
        analyzer.analyze()
        
        return JsonResponse({
            'success': True,
            'message': 'Skill analysis updated successfully.'
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})