"""
Django management command to pre-calculate job matches for all users.
Run nightly via cron: python manage.py calculate_matches
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.accounts.models import User
from apps.recommendations.matching_engine import JobMatchingEngine, SkillGapAnalyzer, LocationDemandAnalyzer
import logging
import time

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Calculate job match scores for all users with completed profiles'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--user',
            type=str,
            help='Calculate matches for specific user email'
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=50,
            help='Number of matches to calculate per user'
        )
        parser.add_argument(
            '--skip-gaps',
            action='store_true',
            help='Skip skill gap analysis'
        )
        parser.add_argument(
            '--locations-only',
            action='store_true',
            help='Only calculate location demand stats'
        )
    
    def handle(self, *args, **options):
        start_time = time.time()
        
        if options['locations_only']:
            self.stdout.write('Calculating location demand statistics...')
            stats_count = LocationDemandAnalyzer.calculate_all_locations()
            self.stdout.write(
                self.style.SUCCESS(f'Updated demand stats for {stats_count} locations')
            )
            return
        
        # Get users to process
        if options['user']:
            try:
                users = [User.objects.get(email=options['user'])]
            except User.DoesNotExist:
                self.stderr.write(f"User {options['user']} not found")
                return
        else:
            # Get users with completed profiles
            users = User.objects.filter(
                profile_completion_percentage__gte=50,
                is_active=True
            ).select_related('profile')
        
        total_users = len(users) if isinstance(users, list) else users.count()
        processed = 0
        total_matches = 0
        
        self.stdout.write(f'Processing {total_users} users...')
        
        for user in users:
            try:
                # Check if user has skills defined
                if not user.profile or not user.profile.skills:
                    self.stdout.write(f'  Skipping {user.email} - no skills defined')
                    continue
                
                # Calculate matches
                engine = JobMatchingEngine(user)
                matches = engine.calculate_matches(limit=options['limit'])
                
                if matches:
                    total_matches += len(matches)
                    processed += 1
                    self.stdout.write(
                        f'  ✓ {user.email}: {len(matches)} matches calculated'
                    )
                else:
                    self.stdout.write(f'  - {user.email}: No matches found')
                
                # Calculate skill gaps
                if not options['skip_gaps']:
                    analyzer = SkillGapAnalyzer(user)
                    analyzer.analyze()
                
            except Exception as e:
                self.stderr.write(f'  ✗ Error processing {user.email}: {str(e)}')
                logger.error(f"Error calculating matches for {user.email}: {e}")
        
        # Also update location demand stats
        self.stdout.write('Updating location demand statistics...')
        stats_count = LocationDemandAnalyzer.calculate_all_locations()
        
        elapsed_time = time.time() - start_time
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\nCompleted in {elapsed_time:.2f}s\n'
                f'Processed {processed} users\n'
                f'Created {total_matches} total matches\n'
                f'Updated demand stats for {stats_count} locations'
            )
        )