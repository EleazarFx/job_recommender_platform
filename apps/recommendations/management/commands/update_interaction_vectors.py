"""
Update user interaction vectors based on job views and saves.
"""
from django.core.management.base import BaseCommand
from django.db.models import Count
from apps.accounts.models import User
from apps.jobs.models import JobView, SavedJob, JobVacancy
from apps.recommendations.models import UserInteractionVector
from collections import Counter


class Command(BaseCommand):
    help = 'Update user interaction vectors for collaborative filtering'
    
    def handle(self, *args, **options):
        users = User.objects.filter(is_active=True)
        updated = 0
        
        for user in users:
            # Get viewed jobs
            viewed_jobs = JobView.objects.filter(
                user=user
            ).values_list('job_id', flat=True)[:100]
            
            # Get saved jobs
            saved_jobs = SavedJob.objects.filter(
                user=user
            ).values_list('job_id', flat=True)
            
            # Get category preferences from viewed jobs
            viewed_categories = JobVacancy.objects.filter(
                id__in=viewed_jobs
            ).values('category__name').annotate(
                count=Count('id')
            )
            
            category_prefs = {
                item['category__name']: item['count']
                for item in viewed_categories if item['category__name']
            }
            
            # Get skill preferences from viewed jobs
            viewed_jobs_skills = JobVacancy.objects.filter(
                id__in=viewed_jobs
            ).values_list('required_skills', flat=True)
            
            skill_counter = Counter()
            for skills_str in viewed_jobs_skills:
                if skills_str:
                    skills = [s.strip().lower() for s in skills_str.split(',')]
                    skill_counter.update(skills)
            
            preferred_skills = dict(skill_counter.most_common(20))
            
            # Calculate interaction weight
            interaction_count = len(viewed_jobs) + len(saved_jobs) * 2
            interaction_weight = min(interaction_count / 50, 1.0)  # Cap at 1.0
            
            # Save or update
            UserInteractionVector.objects.update_or_create(
                user=user,
                defaults={
                    'viewed_job_ids': list(viewed_jobs),
                    'saved_job_ids': list(saved_jobs),
                    'category_preferences': category_prefs,
                    'preferred_skills': preferred_skills,
                    'interaction_weight': interaction_weight
                }
            )
            
            updated += 1
        
        self.stdout.write(
            self.style.SUCCESS(f'Updated interaction vectors for {updated} users')
        )