"""
Authentication forms with custom styling and validation.
"""
from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
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
            'placeholder': 'First Name'
        })
    )
    
    last_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Last Name'
        })
    )
    
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'you@example.com'
        })
    )
    
    user_type = forms.ChoiceField(
        choices=User.USER_TYPE_CHOICES,
        required=True,
        widget=forms.Select(attrs={
            'class': 'form-select'
        })
    )
    
    password1 = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Minimum 8 characters'
        })
    )
    
    password2 = forms.CharField(
        label='Confirm Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm your password'
        })
    )
    
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'user_type', 'password1', 'password2']
    
    def clean_email(self):
        """Ensure email is unique."""
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('This email is already registered.')
        return email
    
    def clean_password1(self):
        """Enforce strong password policy."""
        password = self.cleaned_data.get('password1')
        if len(password) < 8:
            raise forms.ValidationError('Password must be at least 8 characters.')
        if password.isdigit():
            raise forms.ValidationError('Password cannot be entirely numeric.')
        return password


class CustomAuthenticationForm(AuthenticationForm):
    """Custom login form with email instead of username."""
    
    username = forms.EmailField(
        label='Email',
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'you@example.com',
            'autofocus': True
        })
    )
    
    password = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Your password'
        })
    )
    
    def __init__(self, request=None, *args, **kwargs):
        super().__init__(request, *args, **kwargs)
        self.fields['username'].label = 'Email'
    
    def clean(self):
        """Add rate limiting check."""
        cleaned_data = super().clean()
        email = cleaned_data.get('username')
        password = cleaned_data.get('password')
        
        if email and password:
            # Check rate limiting
            request = self.request
            if request:
                ip = self.get_client_ip(request)
                if LoginAttempt.is_rate_limited(email, ip):
                    raise forms.ValidationError(
                        'Too many failed attempts. Please try again in 15 minutes.'
                    )
        
        return cleaned_data
    
    @staticmethod
    def get_client_ip(request):
        """Extract client IP from request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class PasswordResetRequestForm(forms.Form):
    """Form to request password reset OTP."""
    
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your registered email'
        })
    )
    
    def clean_email(self):
        """Verify email exists in system."""
        email = self.cleaned_data.get('email')
        try:
            User.objects.get(email=email)
        except User.DoesNotExist:
            raise forms.ValidationError('No account found with this email address.')
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
            'autocomplete': 'off'
        })
    )
    
    new_password1 = forms.CharField(
        label='New Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Minimum 8 characters'
        })
    )
    
    new_password2 = forms.CharField(
        label='Confirm Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm new password'
        })
    )
    
    def __init__(self, *args, **kwargs):
        email = kwargs.pop('email', None)
        super().__init__(*args, **kwargs)
        if email:
            self.fields['email'].initial = email
    
    def clean(self):
        """Validate passwords match and OTP is valid."""
        cleaned_data = super().clean()
        password1 = cleaned_data.get('new_password1')
        password2 = cleaned_data.get('new_password2')
        
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError('Passwords do not match.')
        
        if len(password1) < 8:
            raise forms.ValidationError('Password must be at least 8 characters.')
        
        return cleaned_data
    
    def clean_otp_code(self):
        """Verify OTP is valid and not expired."""
        otp_code = self.cleaned_data.get('otp_code')
        email = self.cleaned_data.get('email')
        
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


class ProfileUpdateForm(forms.ModelForm):
    """Form for updating user profile."""
    
    skills = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Accounting, Django, Project Management, Data Analysis...'
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
    
    class Meta:
        model = Profile
        fields = [
            'avatar', 'skills', 'qualifications', 
            'experience_level', 'years_of_experience',
            'preferred_locations', 'preferred_job_types'
        ]
        widgets = {
            'avatar': forms.FileInput(attrs={'class': 'form-control'}),
            'experience_level': forms.Select(attrs={'class': 'form-select'}),
            'years_of_experience': forms.NumberInput(attrs={'class': 'form-control'}),
            'preferred_job_types': forms.SelectMultiple(attrs={'class': 'form-select'}),
        }