"""
Secure management command to create administrator accounts.
Usage: python manage.py create_admin --email=admin@example.com --password=SecurePass123!
"""
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
import re

User = get_user_model()


class Command(BaseCommand):
    help = 'Securely create an administrator account'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--email',
            type=str,
            required=True,
            help='Email address for the admin account'
        )
        parser.add_argument(
            '--password',
            type=str,
            required=True,
            help='Password for the admin account'
        )
        parser.add_argument(
            '--first-name',
            type=str,
            default='Admin',
            help='First name (optional)'
        )
        parser.add_argument(
            '--last-name',
            type=str,
            default='User',
            help='Last name (optional)'
        )
    
    def handle(self, *args, **options):
        email = options['email']
        password = options['password']
        first_name = options['first_name']
        last_name = options['last_name']
        
        # Validate email
        try:
            validate_email(email)
        except ValidationError:
            raise CommandError(f"Invalid email address: {email}")
        
        # Validate password strength
        if len(password) < 12:
            self.stdout.write(
                self.style.WARNING(
                    'Warning: Password is less than 12 characters. Consider using a stronger password.'
                )
            )
        
        # Check if user already exists
        if User.objects.filter(email=email).exists():
            raise CommandError(f"User with email {email} already exists.")
        
        # Create admin user
        try:
            admin_user = User.objects.create_user(
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                user_type='ADMIN',
                is_staff=True,
                is_superuser=True,
                is_active=True
            )
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'\n✅ Administrator account created successfully!\n'
                    f'Email: {email}\n'
                    f'Name: {first_name} {last_name}\n'
                    f'Admin Privileges: Full access\n'
                )
            )
            
            # Log this action
            self.stdout.write(
                self.style.WARNING(
                    '⚠️  IMPORTANT: Store these credentials securely.\n'
                    '   This action has been logged for security audit purposes.'
                )
            )
            
        except Exception as e:
            raise CommandError(f"Failed to create admin user: {str(e)}")