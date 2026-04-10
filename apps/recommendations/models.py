"""
AI Recommendation models for job matching and skill analysis.
Stores pre-calculated match scores and audit trails.
"""
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator


class UserSkillProfile(models.Model):
    """
    Processed skill profile for AI matching.
    Updated whenever user updates their profile.
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='skill_profile'
    )
    
    # Extracted and normalized skills
    skills_vector = models.JSONField(
        default=dict,
        help_text="Normalized skills with weights"
    )
    
    skill_keywords = models.TextField(
        blank=True,
        help_text="Cleaned skill keywords for matching"
    )
    
    # Experience and preferences as structured data
    experience_weight = models.FloatField(default=1.0)
    location_preference_vector = models.JSONField(default=dict)
    job_type_preferences = models.JSONField(default=list)
    
    # Metadata
    last_updated = models.DateTimeField(auto_now=True)
    needs_recalculation = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'user_skill_profiles'
        verbose_name = 'User Skill Profile'
        verbose_name_plural = 'User Skill Profiles'
    
    def __str__(self):
        return f"Skill Profile: {self.user.email}"
    
    def get_skills_list(self):
        """Return list of skills from vector."""
        return list(self.skills_vector.keys())


class JobMatchScore(models.Model):
    """
    Pre-calculated match score between a user and a job.
    Updated periodically by background tasks.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='job_matches'
    )
    
    job = models.ForeignKey(
        'jobs.JobVacancy',
        on_delete=models.CASCADE,
        related_name='user_matches'
    )
    
    # Core match score (0-100)
    match_score = models.FloatField(
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    
    # Component scores for explainability
    skill_match_score = models.FloatField(default=0)
    experience_match_score = models.FloatField(default=0)
    location_match_score = models.FloatField(default=0)
    job_type_match_score = models.FloatField(default=0)
    freshness_score = models.FloatField(default=0)
    
    # Match details
    matched_skills = models.JSONField(default=list)
    missing_skills = models.JSONField(default=list)
    match_reason = models.TextField(blank=True)
    
    # Calculated at
    calculated_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField()
    
    class Meta:
        db_table = 'job_match_scores'
        unique_together = ['user', 'job']
        indexes = [
            models.Index(fields=['user', 'match_score']),
            models.Index(fields=['job', 'match_score']),
            models.Index(fields=['calculated_at']),
        ]
        ordering = ['-match_score']
    
    def __str__(self):
        return f"{self.user.email} - {self.job.title}: {self.match_score:.1f}%"
    
    def get_explanation(self):
        """Return human-readable explanation of match."""
        reasons = []
        
        if self.skill_match_score > 70:
            reasons.append(f"Strong skill match ({len(self.matched_skills)} matching skills)")
        elif self.skill_match_score > 40:
            reasons.append(f"Partial skill match")
        
        if self.experience_match_score > 80:
            reasons.append("Experience level matches perfectly")
        
        if self.location_match_score > 80:
            reasons.append("Location matches your preference")
        
        if self.freshness_score > 80:
            reasons.append("Recently posted")
        
        return " • ".join(reasons) if reasons else "Basic match"


class RecommendationLog(models.Model):
    """
    Audit trail for all recommendations shown to users.
    Tracks what was recommended and why.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='recommendation_logs'
    )
    
    job = models.ForeignKey(
        'jobs.JobVacancy',
        on_delete=models.CASCADE
    )
    
    # Context of recommendation
    recommendation_type = models.CharField(
        max_length=50,
        choices=[
            ('HOMEPAGE', 'Homepage Feed'),
            ('SEARCH', 'Search Results'),
            ('EMAIL', 'Email Notification'),
            ('SIMILAR', 'Similar Jobs'),
        ]
    )
    
    match_score = models.FloatField()
    position_in_list = models.IntegerField(default=0)
    
    # User action tracking
    was_viewed = models.BooleanField(default=False)
    was_saved = models.BooleanField(default=False)
    was_ignored = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        db_table = 'recommendation_logs'
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['job', 'created_at']),
            models.Index(fields=['recommendation_type', 'was_viewed']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.email} - {self.job.title} ({self.recommendation_type})"


class SkillGapAnalysis(models.Model):
    """
    Analyzed skill gaps based on user's viewed/saved jobs.
    Updated periodically.
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='skill_gap_analysis'
    )
    
    # Common skills in jobs user interacts with
    in_demand_skills = models.JSONField(
        default=dict,
        help_text="Skill name -> frequency count"
    )
    
    # Skills user has vs skills in demand
    user_skills = models.JSONField(default=list)
    missing_skills = models.JSONField(default=list)
    
    # Analysis summary
    top_missing_skills = models.JSONField(
        default=list,
        help_text="Top 5 skills user doesn't have but are in demand"
    )
    
    analysis_summary = models.TextField(blank=True)
    
    # Metadata
    jobs_analyzed = models.IntegerField(default=0)
    last_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'skill_gap_analyses'
        verbose_name = 'Skill Gap Analysis'
        verbose_name_plural = 'Skill Gap Analyses'
    
    def __str__(self):
        return f"Gap Analysis: {self.user.email}"
    
    def get_recommendation_text(self):
        """Return insight text without teaching recommendations."""
        if not self.top_missing_skills:
            return "No significant skill gaps detected."
        
        skills_text = ", ".join([s['skill'] for s in self.top_missing_skills[:3]])
        return f"Most jobs you viewed require: {skills_text}"


class LocationDemandStats(models.Model):
    """
    Aggregated statistics about job demand by location.
    Pre-calculated for performance.
    """
    location_name = models.CharField(max_length=255, db_index=True)
    location_type = models.CharField(
        max_length=20,
        choices=[('CITY', 'City'), ('DISTRICT', 'District'), ('COUNTRY', 'Country')]
    )
    
    # Statistics
    total_jobs = models.IntegerField(default=0)
    active_jobs = models.IntegerField(default=0)
    
    # By category
    jobs_by_category = models.JSONField(default=dict)
    
    # By experience level
    jobs_by_experience = models.JSONField(default=dict)
    
    # Average salary (where available)
    avg_salary_min = models.DecimalField(max_digits=12, decimal_places=2, null=True)
    avg_salary_max = models.DecimalField(max_digits=12, decimal_places=2, null=True)
    
    # Top skills in this location
    top_skills = models.JSONField(default=list)
    
    # Metadata
    calculated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'location_demand_stats'
        unique_together = ['location_name', 'location_type']
        indexes = [
            models.Index(fields=['location_name']),
            models.Index(fields=['active_jobs']),
        ]
    
    def __str__(self):
        return f"Demand Stats: {self.location_name} ({self.active_jobs} jobs)"


class UserInteractionVector(models.Model):
    """
    User behavior vector for collaborative filtering.
    Built from views, saves, and applications.
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='interaction_vector'
    )
    
    # Job IDs that user interacted with
    viewed_job_ids = models.JSONField(default=list)
    saved_job_ids = models.JSONField(default=list)
    applied_job_ids = models.JSONField(default=list)
    
    # Category preferences (derived from interactions)
    category_preferences = models.JSONField(default=dict)
    
    # Skill preferences (derived from viewed jobs)
    preferred_skills = models.JSONField(default=dict)
    
    # Weight for recommendations
    interaction_weight = models.FloatField(default=0.5)
    
    last_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'user_interaction_vectors'
        verbose_name = 'User Interaction Vector'
        verbose_name_plural = 'User Interaction Vectors'
    
    def __str__(self):
        return f"Interaction Vector: {self.user.email}"