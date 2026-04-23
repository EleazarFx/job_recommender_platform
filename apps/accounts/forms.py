"""
Authentication forms with custom styling and validation.
"""
import re
from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm, PasswordChangeForm
from django.core.validators import validate_email
from django.contrib.auth import authenticate
from .models import User, Profile, PasswordResetOTP, LoginAttempt


class CustomUserCreationForm(UserCreationForm):
    """Custom registration form with email as primary identifier."""
    
    first_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'First Name',
            'autocomplete': 'given-name'
        })
    )
    
    last_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Last Name',
            'autocomplete': 'family-name'
        })
    )
    
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'you@example.com',
            'autocomplete': 'email'
        })
    )
    
    # FIX: Remove ADMIN from user type choices for public registration
    USER_TYPE_CHOICES = [
        ('JOB_SEEKER', '💼 Job Seeker - Looking for opportunities'),
        ('EMPLOYER', '🏢 Employer - Hiring talent'),
        # ('ADMIN', 'Administrator'),  # REMOVED - Not available for public registration
    ]
    
    user_type = forms.ChoiceField(
        choices=USER_TYPE_CHOICES,
        required=True,
        widget=forms.Select(attrs={
            'class': 'form-select'
        })
    )
    
    password1 = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Minimum 8 characters',
            'autocomplete': 'new-password'
        })
    )
    
    password2 = forms.CharField(
        label='Confirm Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm your password',
            'autocomplete': 'new-password'
        })
    )
    
    terms_accepted = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        error_messages={
            'required': 'You must accept the Terms of Service and Privacy Policy.'
        }
    )
    
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'user_type', 'password1', 'password2']
    
    def clean_first_name(self):
        """Capitalize first name."""
        first_name = self.cleaned_data.get('first_name', '').strip()
        if not first_name:
            raise forms.ValidationError('First name is required.')
        return first_name.title()
    
    def clean_last_name(self):
        """Capitalize last name."""
        last_name = self.cleaned_data.get('last_name', '').strip()
        if not last_name:
            raise forms.ValidationError('Last name is required.')
        return last_name.title()
    
    def clean_email(self):
        """Ensure email is unique and properly formatted."""
        email = self.cleaned_data.get('email', '').lower().strip()
        
        # Check for disposable email domains
        disposable_domains = ['mailinator.com', 'tempmail.com', 'guerrillamail.com', '10minutemail.com']
        domain = email.split('@')[-1] if '@' in email else ''
        
        if domain in disposable_domains:
            raise forms.ValidationError('Please use a permanent email address.')
        
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('This email is already registered.')
        
        return email
    
    def clean_password1(self):
        """Enforce strong password policy."""
        password = self.cleaned_data.get('password1', '')
        
        if len(password) < 8:
            raise forms.ValidationError('Password must be at least 8 characters.')
        
        if password.isdigit():
            raise forms.ValidationError('Password cannot be entirely numeric.')
        
        if password.isalpha():
            raise forms.ValidationError('Password must contain at least one number or special character.')
        
        # Check for common passwords
        common_passwords = ['password', '12345678', 'qwerty123', 'admin123', 'welcome1']
        if password.lower() in common_passwords:
            raise forms.ValidationError('This password is too common. Please choose a stronger password.')
        
        return password
    
    def clean(self):
        """Additional cross-field validation."""
        cleaned_data = super().clean()
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')
        
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError('Passwords do not match.')
        
        # Check if password contains personal information
        email = cleaned_data.get('email', '')
        first_name = cleaned_data.get('first_name', '')
        last_name = cleaned_data.get('last_name', '')
        
        if password1:
            email_prefix = email.split('@')[0] if '@' in email else ''
            if (email_prefix and email_prefix.lower() in password1.lower()) or \
               (first_name and first_name.lower() in password1.lower()) or \
               (last_name and last_name.lower() in password1.lower()):
                raise forms.ValidationError('Password cannot contain your email or name.')
        
        return cleaned_data
    
    def save(self, commit=True):
        """Override save to ensure user_type cannot be ADMIN."""
        user = super().save(commit=False)
        user.email = user.email.lower()
        
        # Force user_type to JOB_SEEKER if somehow ADMIN was submitted
        if user.user_type == 'ADMIN':
            user.user_type = 'JOB_SEEKER'
        
        if commit:
            user.save()
        return user


class CustomAuthenticationForm(AuthenticationForm):
    """Custom login form with email instead of username."""
    
    username = forms.EmailField(
        label='Email',
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'you@example.com',
            'autofocus': True,
            'autocomplete': 'email'
        })
    )
    
    password = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Your password',
            'autocomplete': 'current-password'
        })
    )
    
    remember_me = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )
    
    def __init__(self, request=None, *args, **kwargs):
        super().__init__(request, *args, **kwargs)
        self.fields['username'].label = 'Email'
    
    def clean_username(self):
        """Normalize email to lowercase."""
        username = self.cleaned_data.get('username', '')
        return username.lower().strip()
    
    def clean(self):
        """Add rate limiting check."""
        cleaned_data = super().clean()
        email = cleaned_data.get('username')
        password = cleaned_data.get('password')
        
        if email and password:
            request = self.request
            if request:
                ip = self.get_client_ip(request)
                
                # Check rate limiting
                if LoginAttempt.is_rate_limited(email, ip):
                    raise forms.ValidationError(
                        'Too many failed attempts. Please try again in 15 minutes.'
                    )
                
                # Check if user exists and is active
                try:
                    user = User.objects.get(email=email)
                    if not user.is_active:
                        raise forms.ValidationError(
                            'Your account is not active. Please check your email for verification instructions.'
                        )
                except User.DoesNotExist:
                    # Don't reveal if email exists (security)
                    pass
        
        return cleaned_data
    
    @staticmethod
    def get_client_ip(request):
        """Extract client IP from request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', '')
        return ip


class PasswordResetRequestForm(forms.Form):
    """Form to request password reset OTP."""
    
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your registered email',
            'autocomplete': 'email'
        })
    )
    
    def clean_email(self):
        """Verify email exists in system and normalize."""
        email = self.cleaned_data.get('email', '').lower().strip()
        
        try:
            user = User.objects.get(email=email)
            if not user.is_active:
                raise forms.ValidationError(
                    'This account is not active. Please contact support.'
                )
        except User.DoesNotExist:
            # Don't reveal if email exists (security) - but log it
            pass
        
        return email


class PasswordResetVerifyForm(forms.Form):
    """Form to verify OTP and set new password."""
    
    email = forms.EmailField(widget=forms.HiddenInput())
    
    otp_code = forms.CharField(
        max_length=6,
        min_length=6,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter 6-digit code',
            'autocomplete': 'off',
            'inputmode': 'numeric',
            'pattern': '[0-9]*'
        })
    )
    
    new_password1 = forms.CharField(
        label='New Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Minimum 8 characters',
            'autocomplete': 'new-password'
        })
    )
    
    new_password2 = forms.CharField(
        label='Confirm Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm new password',
            'autocomplete': 'new-password'
        })
    )
    
    def __init__(self, *args, **kwargs):
        email = kwargs.pop('email', None)
        super().__init__(*args, **kwargs)
        if email:
            self.fields['email'].initial = email
    
    def clean_otp_code(self):
        """Verify OTP is valid and not expired."""
        otp_code = self.cleaned_data.get('otp_code', '').strip()
        email = self.cleaned_data.get('email')
        
        if not otp_code.isdigit():
            raise forms.ValidationError('Code must contain only numbers.')
        
        try:
            user = User.objects.get(email=email)
            otp = PasswordResetOTP.objects.filter(
                user=user,
                code=otp_code,
                is_used=False
            ).latest('created_at')
            
            if not otp.is_valid():
                raise forms.ValidationError('Invalid or expired code.')
            
            # Increment attempt counter
            otp.attempts += 1
            otp.save(update_fields=['attempts'])
            
            if otp.attempts >= 3:
                otp.is_used = True
                otp.save(update_fields=['is_used'])
                raise forms.ValidationError('Too many attempts. Please request a new code.')
            
            self.valid_otp = otp  # Store for later use
            
        except (User.DoesNotExist, PasswordResetOTP.DoesNotExist):
            raise forms.ValidationError('Invalid code.')
        
        return otp_code
    
    def clean_new_password1(self):
        """Enforce strong password policy."""
        password = self.cleaned_data.get('new_password1', '')
        
        if len(password) < 8:
            raise forms.ValidationError('Password must be at least 8 characters.')
        
        if password.isdigit():
            raise forms.ValidationError('Password cannot be entirely numeric.')
        
        return password
    
    def clean(self):
        """Validate passwords match."""
        cleaned_data = super().clean()
        password1 = cleaned_data.get('new_password1')
        password2 = cleaned_data.get('new_password2')
        
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError('Passwords do not match.')
        
        return cleaned_data


class ProfileUpdateForm(forms.ModelForm):
    """Form for updating user profile with role-specific fields."""
    
    skills = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Python, Django, Project Management, Data Analysis...'
        })
    )
    
    qualifications = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'BSc Computer Science, PMP Certification...'
        })
    )
    
    preferred_locations = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Lilongwe, Blantyre, Remote, International'
        })
    )
    
    # Job type preferences
    preferred_job_types = forms.MultipleChoiceField(
        choices=[
            ('FULL_TIME', 'Full Time'),
            ('PART_TIME', 'Part Time'),
            ('CONTRACT', 'Contract'),
            ('INTERNSHIP', 'Internship'),
            ('REMOTE', 'Remote'),
            ('HYBRID', 'Hybrid'),
        ],
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'})
    )
    
    class Meta:
        model = Profile
        fields = [
            'avatar', 'skills', 'qualifications', 
            'experience_level', 'years_of_experience',
            'preferred_locations', 'preferred_job_types'
        ]
        widgets = {
            'avatar': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'experience_level': forms.Select(attrs={'class': 'form-select'}),
            'years_of_experience': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 0,
                'max': 50
            }),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Set initial value for preferred_job_types from JSON field
        if self.instance and self.instance.preferred_job_types:
            self.fields['preferred_job_types'].initial = self.instance.preferred_job_types
        
        # Add employer-specific fields if user is employer
        if self.user and self.user.user_type == 'EMPLOYER':
            self.fields['company_name'] = forms.CharField(
                required=False,
                max_length=255,
                widget=forms.TextInput(attrs={
                    'class': 'form-control',
                    'placeholder': 'Your company name'
                })
            )
            self.fields['company_website'] = forms.URLField(
                required=False,
                widget=forms.URLInput(attrs={
                    'class': 'form-control',
                    'placeholder': 'https://www.example.com'
                })
            )
            self.fields['company_description'] = forms.CharField(
                required=False,
                widget=forms.Textarea(attrs={
                    'class': 'form-control',
                    'rows': 3,
                    'placeholder': 'Tell us about your company...'
                })
            )
    
    def clean_skills(self):
        """Normalize skills format."""
        skills = self.cleaned_data.get('skills', '')
        if skills:
            # Remove extra spaces and standardize
            skills_list = [s.strip().lower() for s in skills.split(',') if s.strip()]
            skills = ', '.join(sorted(set(skills_list)))
        return skills
    
    def clean_preferred_locations(self):
        """Normalize locations format."""
        locations = self.cleaned_data.get('preferred_locations', '')
        if locations:
            locations_list = [l.strip().title() for l in locations.split(',') if l.strip()]
            locations = ', '.join(sorted(set(locations_list)))
        return locations
    
    def clean_years_of_experience(self):
        """Validate years of experience."""
        years = self.cleaned_data.get('years_of_experience', 0)
        if years and years < 0:
            raise forms.ValidationError('Years of experience cannot be negative.')
        if years > 50:
            raise forms.ValidationError('Please enter a valid number of years.')
        return years
    
    def clean_preferred_job_types(self):
        """Ensure preferred_job_types is always a list."""
        value = self.cleaned_data.get('preferred_job_types', [])
        if value is None:
            return []
        return list(value)


class CustomPasswordChangeForm(PasswordChangeForm):
    """Enhanced password change form with better styling."""
    
    old_password = forms.CharField(
        label='Current Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter current password',
            'autocomplete': 'current-password'
        })
    )
    
    new_password1 = forms.CharField(
        label='New Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Minimum 8 characters',
            'autocomplete': 'new-password'
        })
    )
    
    new_password2 = forms.CharField(
        label='Confirm New Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm new password',
            'autocomplete': 'new-password'
        })
    )
    
    def clean_new_password1(self):
        """Enforce strong password policy."""
        password = self.cleaned_data.get('new_password1', '')
        
        if len(password) < 8:
            raise forms.ValidationError('Password must be at least 8 characters.')
        
        if password.isdigit():
            raise forms.ValidationError('Password cannot be entirely numeric.')
        
        # Check if new password is different from old
        if self.user.check_password(password):
            raise forms.ValidationError('New password must be different from current password.')
        
        return password



class DeleteAccountForm(forms.Form):
    """Form for account deletion confirmation."""
    
    password = forms.CharField(
        label='Enter your password to confirm',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Your password',
            'autocomplete': 'current-password'
        })
    )
    
    confirmation = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        error_messages={
            'required': 'You must confirm that you understand this action cannot be undone.'
        }
    )
    
    def __init__(self, user=None, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
    
    def clean_password(self):
        """Verify password matches user."""
        password = self.cleaned_data.get('password')
        if self.user and not self.user.check_password(password):
            raise forms.ValidationError('Incorrect password.')
        return password