"""
Django Admin configuration for Recommendations app.
"""
from django.contrib import admin
from django.utils.html import format_html
from .models import (
    UserSkillProfile, JobMatchScore, RecommendationLog,
    SkillGapAnalysis, LocationDemandStats, UserInteractionVector
)


@admin.register(JobMatchScore)
class JobMatchScoreAdmin(admin.ModelAdmin):
    """Job Match Scores admin."""
    
    list_display = ['user', 'job_link', 'match_score_badge', 'calculated_at']
    list_filter = ['calculated_at']
    search_fields = ['user__email', 'job__title']
    raw_id_fields = ['user', 'job']
    readonly_fields = [
        'match_score', 'skill_match_score', 'experience_match_score',
        'location_match_score', 'job_type_match_score', 'freshness_score',
        'matched_skills', 'missing_skills', 'match_reason',
        'calculated_at', 'expires_at'
    ]
    
    def job_link(self, obj):
        from django.urls import reverse
        url = reverse('admin:jobs_jobvacancy_change', args=[obj.job.id])
        return format_html('<a href="{}">{}</a>', url, obj.job.title)
    job_link.short_description = 'Job'
    
    def match_score_badge(self, obj):
        score = obj.match_score
        if score >= 80:
            color = 'green'
        elif score >= 60:
            color = 'blue'
        elif score >= 40:
            color = 'orange'
        else:
            color = 'gray'
        
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 10px; font-weight: bold;">{:.1f}%</span>',
            color, score
        )
    match_score_badge.short_description = 'Match Score'
    match_score_badge.admin_order_field = 'match_score'
    
    def has_add_permission(self, request):
        return False


@admin.register(RecommendationLog)
class RecommendationLogAdmin(admin.ModelAdmin):
    """Recommendation audit log."""
    
    list_display = ['user', 'job_link', 'recommendation_type', 'match_score', 'was_viewed', 'created_at']
    list_filter = ['recommendation_type', 'was_viewed', 'was_saved', 'was_ignored', 'created_at']
    search_fields = ['user__email', 'job__title']
    readonly_fields = [
        'user', 'job', 'recommendation_type', 'match_score', 'position_in_list',
        'was_viewed', 'was_saved', 'was_ignored', 'created_at'
    ]
    
    def job_link(self, obj):
        from django.urls import reverse
        url = reverse('admin:jobs_jobvacancy_change', args=[obj.job.id])
        return format_html('<a href="{}">{}</a>', url, obj.job.title)
    job_link.short_description = 'Job'
    
    def has_add_permission(self, request):
        return False


@admin.register(SkillGapAnalysis)
class SkillGapAnalysisAdmin(admin.ModelAdmin):
    """Skill Gap Analysis admin."""
    
    list_display = ['user', 'jobs_analyzed', 'top_missing_preview', 'last_updated']
    search_fields = ['user__email']
    raw_id_fields = ['user']
    readonly_fields = [
        'in_demand_skills', 'user_skills', 'missing_skills',
        'top_missing_skills', 'analysis_summary', 'jobs_analyzed', 'last_updated'
    ]
    
    def top_missing_preview(self, obj):
        """Preview top missing skills."""
        if obj.top_missing_skills:
            skills = [s['skill'] for s in obj.top_missing_skills[:3]]
            return ', '.join(skills)
        return '-'
    top_missing_preview.short_description = 'Top Missing Skills'


@admin.register(LocationDemandStats)
class LocationDemandStatsAdmin(admin.ModelAdmin):
    """Location demand statistics."""
    
    list_display = ['location_name', 'location_type', 'active_jobs', 'calculated_at']
    list_filter = ['location_type', 'calculated_at']
    search_fields = ['location_name']
    readonly_fields = [
        'location_name', 'location_type', 'total_jobs', 'active_jobs',
        'jobs_by_category', 'jobs_by_experience', 'avg_salary_min',
        'avg_salary_max', 'top_skills', 'calculated_at'
    ]
    
    def has_add_permission(self, request):
        return False


@admin.register(UserInteractionVector)
class UserInteractionVectorAdmin(admin.ModelAdmin):
    """User interaction vectors for ML."""
    
    list_display = ['user', 'viewed_count', 'saved_count', 'interaction_weight', 'last_updated']
    search_fields = ['user__email']
    raw_id_fields = ['user']
    readonly_fields = [
        'viewed_job_ids', 'saved_job_ids', 'applied_job_ids',
        'category_preferences', 'preferred_skills', 'interaction_weight', 'last_updated'
    ]
    
    def viewed_count(self, obj):
        return len(obj.viewed_job_ids) if obj.viewed_job_ids else 0
    viewed_count.short_description = 'Jobs Viewed'
    
    def saved_count(self, obj):
        return len(obj.saved_job_ids) if obj.saved_job_ids else 0
    saved_count.short_description = 'Jobs Saved'


@admin.register(UserSkillProfile)
class UserSkillProfileAdmin(admin.ModelAdmin):
    """User skill profiles for AI matching."""
    
    list_display = ['user', 'skill_count', 'needs_recalculation', 'last_updated']
    search_fields = ['user__email']
    raw_id_fields = ['user']
    readonly_fields = ['skills_vector', 'skill_keywords', 'last_updated']
    
    def skill_count(self, obj):
        return len(obj.skills_vector) if obj.skills_vector else 0
    skill_count.short_description = 'Skills Count'