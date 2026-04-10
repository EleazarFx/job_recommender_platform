"""
AI-Powered Job Matching Engine using Scikit-Learn.
Explainable, auditable, production-ready.
"""
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import MinMaxScaler
from django.utils import timezone
from django.db.models import Q, F, Count
from datetime import timedelta
import logging
import json

from apps.jobs.models import JobVacancy
from apps.accounts.models import User, Profile
from .models import (
    UserSkillProfile, JobMatchScore, RecommendationLog,
    SkillGapAnalysis, LocationDemandStats, UserInteractionVector
)

logger = logging.getLogger(__name__)


class JobMatchingEngine:
    """
    Core matching engine using TF-IDF vectorization and cosine similarity.
    """
    
    def __init__(self, user):
        self.user = user
        self.profile = user.profile if hasattr(user, 'profile') else None
        
    def calculate_matches(self, limit=50, save_results=True):
        """
        Calculate job matches for the user.
        Returns top matching jobs with scores.
        """
        if not self.profile or not self.profile.skills:
            logger.warning(f"User {self.user.email} has no skills defined")
            return []
        
        # Get user skills
        user_skills = self._get_user_skills()
        if not user_skills:
            return []
        
        # Get active jobs
        active_jobs = self._get_active_jobs()
        if not active_jobs:
            return []
        
        # Extract job skills
        job_skills_list = [job.required_skills for job in active_jobs]
        
        # Calculate skill match scores
        skill_scores = self._calculate_skill_scores(user_skills, job_skills_list)
        
        # Calculate other component scores
        matches = []
        for i, job in enumerate(active_jobs):
            # Skip if skill score is too low
            if skill_scores[i] < 0.1:
                continue
            
            # Calculate component scores
            exp_score = self._calculate_experience_match(job)
            loc_score = self._calculate_location_match(job)
            type_score = self._calculate_job_type_match(job)
            fresh_score = self._calculate_freshness_score(job)
            
            # Weighted total score
            weights = {
                'skill': 0.40,
                'experience': 0.20,
                'location': 0.20,
                'job_type': 0.10,
                'freshness': 0.10
            }
            
            total_score = (
                skill_scores[i] * weights['skill'] +
                exp_score * weights['experience'] +
                loc_score * weights['location'] +
                type_score * weights['job_type'] +
                fresh_score * weights['freshness']
            ) * 100
            
            # Get matched and missing skills
            matched, missing = self._get_skill_overlap(user_skills, job.required_skills)
            
            match_data = {
                'job': job,
                'match_score': round(total_score, 2),
                'skill_match_score': round(skill_scores[i] * 100, 2),
                'experience_match_score': round(exp_score * 100, 2),
                'location_match_score': round(loc_score * 100, 2),
                'job_type_match_score': round(type_score * 100, 2),
                'freshness_score': round(fresh_score * 100, 2),
                'matched_skills': matched,
                'missing_skills': missing,
                'match_reason': self._generate_match_reason(
                    skill_scores[i], exp_score, loc_score, len(matched)
                )
            }
            
            matches.append(match_data)
        
        # Sort by match score
        matches.sort(key=lambda x: x['match_score'], reverse=True)
        top_matches = matches[:limit]
        
        # Save to database if requested
        if save_results:
            self._save_match_scores(top_matches)
        
        return top_matches
    
    def _get_user_skills(self):
        """Extract and normalize user skills."""
        if not self.profile.skills:
            return ""
        
        # Clean and normalize skills
        skills = self.profile.skills.lower().strip()
        # Remove extra spaces and standardize separators
        skills = ', '.join([s.strip() for s in skills.split(',') if s.strip()])
        return skills
    
    def _get_active_jobs(self):
        """Get active, approved jobs."""
        return JobVacancy.objects.filter(
            is_approved=True,
            expiry_date__gte=timezone.now().date()
        ).exclude(
            posted_by=self.user  # Don't recommend user's own jobs
        ).select_related('category')
    
    def _calculate_skill_scores(self, user_skills, job_skills_list):
        """
        Calculate skill match using TF-IDF and cosine similarity.
        """
        if not job_skills_list:
            return np.array([])
        
        # Prepare corpus
        corpus = [user_skills] + job_skills_list
        
        # Vectorize
        vectorizer = TfidfVectorizer(
            tokenizer=lambda x: x.split(', '),
            lowercase=True,
            token_pattern=None
        )
        
        try:
            tfidf_matrix = vectorizer.fit_transform(corpus)
            
            # Calculate similarities
            user_vector = tfidf_matrix[0:1]
            job_vectors = tfidf_matrix[1:]
            
            similarities = cosine_similarity(user_vector, job_vectors).flatten()
            return similarities
            
        except Exception as e:
            logger.error(f"Error in skill matching: {e}")
            # Fallback to simple keyword matching
            return self._simple_skill_match(user_skills, job_skills_list)
    
    def _simple_skill_match(self, user_skills, job_skills_list):
        """Fallback: Simple keyword overlap matching."""
        user_skill_set = set(s.strip().lower() for s in user_skills.split(',') if s.strip())
        scores = []
        
        for job_skills in job_skills_list:
            if not job_skills:
                scores.append(0.0)
                continue
            
            job_skill_set = set(s.strip().lower() for s in job_skills.split(',') if s.strip())
            
            if not job_skill_set:
                scores.append(0.0)
                continue
            
            overlap = len(user_skill_set.intersection(job_skill_set))
            score = overlap / len(job_skill_set)
            scores.append(min(score, 1.0))
        
        return np.array(scores)
    
    def _calculate_experience_match(self, job):
        """Calculate experience level match."""
        if not self.profile.experience_level:
            return 0.5  # Neutral if not specified
        
        exp_levels = ['ENTRY', 'JUNIOR', 'MID', 'SENIOR', 'LEAD']
        user_level_idx = exp_levels.index(self.profile.experience_level) if self.profile.experience_level in exp_levels else 2
        job_level_idx = exp_levels.index(job.experience_level) if job.experience_level in exp_levels else 2
        
        # Calculate similarity (closer levels = higher score)
        diff = abs(user_level_idx - job_level_idx)
        
        if diff == 0:
            return 1.0  # Perfect match
        elif diff == 1:
            return 0.7  # Adjacent level
        elif diff == 2:
            return 0.3  # Two levels apart
        else:
            return 0.1  # Far apart
    
    def _calculate_location_match(self, job):
        """Calculate location preference match."""
        if not self.profile.preferred_locations:
            return 0.5  # Neutral if not specified
        
        user_locations = self.profile.get_preferred_locations_list()
        job_location = job.location_display.lower()
        
        # Check for remote preference
        if 'remote' in [l.lower() for l in user_locations] and job.is_remote:
            return 1.0
        
        # Check for exact location match
        for loc in user_locations:
            if loc.lower() in job_location:
                return 1.0
        
        # Check for partial match (e.g., "Lilongwe" matches "Lilongwe, Malawi")
        for loc in user_locations:
            loc_parts = loc.lower().split()
            for part in loc_parts:
                if len(part) > 2 and part in job_location:
                    return 0.7
        
        return 0.2  # No match
    
    def _calculate_job_type_match(self, job):
        """Calculate job type preference match."""
        if not self.profile.preferred_job_types:
            return 0.5
        
        preferred = self.profile.preferred_job_types
        if isinstance(preferred, str):
            preferred = json.loads(preferred)
        
        if job.job_type in preferred:
            return 1.0
        
        return 0.3
    
    def _calculate_freshness_score(self, job):
        """Calculate freshness score based on post date."""
        days_old = (timezone.now().date() - job.date_posted.date()).days
        
        if days_old <= 1:
            return 1.0  # Today or yesterday
        elif days_old <= 3:
            return 0.9
        elif days_old <= 7:
            return 0.7
        elif days_old <= 14:
            return 0.5
        elif days_old <= 30:
            return 0.3
        else:
            return 0.1
    
    def _get_skill_overlap(self, user_skills, job_skills):
        """Get matched and missing skills."""
        user_set = set(s.strip().lower() for s in user_skills.split(',') if s.strip())
        job_set = set(s.strip().lower() for s in job_skills.split(',') if s.strip()) if job_skills else set()
        
        matched = list(user_set.intersection(job_set))
        missing = list(job_set - user_set)
        
        return matched, missing
    
    def _generate_match_reason(self, skill_score, exp_score, loc_score, match_count):
        """Generate human-readable match reason."""
        if skill_score > 0.8:
            return f"Excellent skill match ({match_count}+ matching skills)"
        elif skill_score > 0.5:
            return f"Good skill match ({match_count} matching skills)"
        elif exp_score > 0.8:
            return "Perfect experience level match"
        elif loc_score > 0.8:
            return "Matches your preferred location"
        else:
            return "Potential match based on your profile"
    
    def _save_match_scores(self, matches):
        """Save calculated match scores to database."""
        expires_at = timezone.now() + timedelta(hours=6)  # Recalculate every 6 hours
        
        for match in matches:
            job = match['job']
            
            JobMatchScore.objects.update_or_create(
                user=self.user,
                job=job,
                defaults={
                    'match_score': match['match_score'],
                    'skill_match_score': match['skill_match_score'],
                    'experience_match_score': match['experience_match_score'],
                    'location_match_score': match['location_match_score'],
                    'job_type_match_score': match['job_type_match_score'],
                    'freshness_score': match['freshness_score'],
                    'matched_skills': match['matched_skills'],
                    'missing_skills': match['missing_skills'],
                    'match_reason': match['match_reason'],
                    'expires_at': expires_at
                }
            )


class SkillGapAnalyzer:
    """
    Analyze skill gaps based on user's job interactions.
    No teaching - insights only.
    """
    
    def __init__(self, user):
        self.user = user
    
    def analyze(self, save=True):
        """
        Analyze viewed and saved jobs to identify skill gaps.
        """
        from apps.jobs.models import JobView, SavedJob
        
        # Get jobs user interacted with
        viewed_jobs = JobView.objects.filter(
            user=self.user
        ).select_related('job')[:50]
        
        saved_jobs = SavedJob.objects.filter(
            user=self.user
        ).select_related('job')
        
        # Collect all skills from these jobs
        all_skills_count = {}
        jobs_analyzed = 0
        
        # Process viewed jobs
        for view in viewed_jobs:
            if view.job.required_skills:
                skills = [s.strip().lower() for s in view.job.required_skills.split(',') if s.strip()]
                for skill in skills:
                    all_skills_count[skill] = all_skills_count.get(skill, 0) + 1
                jobs_analyzed += 1
        
        # Process saved jobs (weighted higher)
        for saved in saved_jobs:
            if saved.job.required_skills:
                skills = [s.strip().lower() for s in saved.job.required_skills.split(',') if s.strip()]
                for skill in skills:
                    all_skills_count[skill] = all_skills_count.get(skill, 0) + 2  # Double weight
                jobs_analyzed += 1
        
        # Get user's current skills
        profile = self.user.profile if hasattr(self.user, 'profile') else None
        user_skills = []
        if profile and profile.skills:
            user_skills = [s.strip().lower() for s in profile.skills.split(',') if s.strip()]
        
        # Find missing skills
        missing_skills = []
        for skill, count in all_skills_count.items():
            if skill not in user_skills:
                missing_skills.append({
                    'skill': skill,
                    'frequency': count
                })
        
        # Sort by frequency
        missing_skills.sort(key=lambda x: x['frequency'], reverse=True)
        top_missing = missing_skills[:5]
        
        # Generate summary
        if top_missing:
            skills_text = ", ".join([s['skill'].title() for s in top_missing[:3]])
            summary = f"Most jobs you viewed require: {skills_text}"
        else:
            summary = "Your skills align well with jobs you're viewing."
        
        if save:
            SkillGapAnalysis.objects.update_or_create(
                user=self.user,
                defaults={
                    'in_demand_skills': all_skills_count,
                    'user_skills': user_skills,
                    'missing_skills': missing_skills,
                    'top_missing_skills': top_missing,
                    'analysis_summary': summary,
                    'jobs_analyzed': jobs_analyzed
                }
            )
        
        return {
            'in_demand': all_skills_count,
            'user_skills': user_skills,
            'missing': missing_skills,
            'top_missing': top_missing,
            'summary': summary
        }


class LocationDemandAnalyzer:
    """
    Analyze job demand by location.
    Pre-calculates statistics for fast retrieval.
    """
    
    @classmethod
    def calculate_all_locations(cls):
        """
        Calculate demand statistics for all locations.
        Should be run as a background task.
        """
        from django.db.models import Count, Avg, Q
        
        # Get all unique locations
        locations = JobVacancy.objects.filter(
            is_approved=True,
            expiry_date__gte=timezone.now().date()
        ).values('city', 'district', 'country').distinct()
        
        stats_created = 0
        
        for loc_data in locations:
            city = loc_data['city']
            
            if not city:
                continue
            
            # Build query for this location
            query = Q(city=city) & Q(is_approved=True)
            
            # Get jobs for this location
            jobs = JobVacancy.objects.filter(query)
            active_jobs = jobs.filter(expiry_date__gte=timezone.now().date())
            
            if active_jobs.count() == 0:
                continue
            
            # Calculate statistics
            jobs_by_category = {}
            for job in active_jobs:
                if job.category:
                    cat_name = job.category.name
                    jobs_by_category[cat_name] = jobs_by_category.get(cat_name, 0) + 1
            
            jobs_by_experience = {}
            for job in active_jobs:
                exp = job.get_experience_level_display()
                jobs_by_experience[exp] = jobs_by_experience.get(exp, 0) + 1
            
            # Extract top skills
            all_skills = []
            for job in active_jobs[:100]:  # Sample for performance
                if job.required_skills:
                    skills = [s.strip().lower() for s in job.required_skills.split(',')]
                    all_skills.extend(skills)
            
            from collections import Counter
            skill_counter = Counter(all_skills)
            top_skills = [{'skill': skill, 'count': count} 
                         for skill, count in skill_counter.most_common(10)]
            
            # Save or update
            LocationDemandStats.objects.update_or_create(
                location_name=city,
                location_type='CITY',
                defaults={
                    'total_jobs': jobs.count(),
                    'active_jobs': active_jobs.count(),
                    'jobs_by_category': jobs_by_category,
                    'jobs_by_experience': jobs_by_experience,
                    'top_skills': top_skills
                }
            )
            stats_created += 1
        
        return stats_created