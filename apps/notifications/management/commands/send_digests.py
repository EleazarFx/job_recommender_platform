"""
Management command to send daily/weekly digests.
Run via cron:
0 8 * * * python manage.py send_digests --type=daily
0 8 * * 1 python manage.py send_digests --type=weekly
"""
from django.core.management.base import BaseCommand
from apps.notifications.services import NotificationService


class Command(BaseCommand):
    help = 'Send notification digests to users'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--type',
            type=str,
            default='daily',
            choices=['daily', 'weekly'],
            help='Type of digest to send'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview without sending'
        )
    
    def handle(self, *args, **options):
        digest_type = options['type']
        dry_run = options['dry_run']
        
        self.stdout.write(f'Processing {digest_type} digests...')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN - No emails will be sent'))
            return
        
        if digest_type == 'daily':
            count = NotificationService.create_daily_digests()
            self.stdout.write(
                self.style.SUCCESS(f'Created and sent {count} daily digests')
            )
        else:
            # Weekly digest implementation would go here
            self.stdout.write('Weekly digests not yet implemented')