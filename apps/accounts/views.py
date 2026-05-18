"""
Authentication views with Email OTP reset functionality.
Simplified - No email verification on registration.
"""
import socket
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse_lazy, reverse
from django.views.generic import CreateView, UpdateView
from django.views import View
from django.utils.decorators import method_decorator
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.views import LoginView

from .models import User, Profile, PasswordResetOTP, LoginAttempt
from .forms import (
    CustomUserCreationForm, CustomAuthenticationForm,
    PasswordResetRequestForm, PasswordResetVerifyForm,
    ProfileUpdateForm
)


# ============================================
# REGISTRATION
# ============================================

class RegisterView(CreateView):
    """User registration - simple, no email verification."""
    model = User
    form_class = CustomUserCreationForm
    template_name = 'accounts/register.html'
    success_url = reverse_lazy('accounts:profile_setup')
    
    def form_valid(self, form):
        """Create user, log them in, redirect to profile setup."""
        print("\n=== REGISTRATION FORM IS VALID ===")
        print(f"Email: {form.cleaned_data.get('email')}")
        print(f"User Type: {form.cleaned_data.get('user_type')}")
        
        if form.cleaned_data.get('user_type') == 'ADMIN':
            messages.error(self.request, 'Administrator accounts cannot be created through public registration.')
            return self.form_invalid(form)
        
        try:
            with transaction.atomic():
                self.object = form.save()
                
                # Set proper permissions
                self.object.is_staff = False
                self.object.is_superuser = False
                self.object.is_active = True
                self.object.save(update_fields=['is_staff', 'is_superuser', 'is_active'])
                
                # Create profile
                profile, created = Profile.objects.get_or_create(user=self.object)
                print(f"Profile created: {created}, Profile ID: {profile.id}")
                
                # Log user in
                login(self.request, self.object)
                print(f"User logged in: {self.object.email}")
                
                messages.success(self.request, f'Welcome {self.object.first_name}! Please complete your profile.')
            
            print("=== REDIRECTING TO PROFILE SETUP ===\n")
            return redirect(self.success_url)
            
        except Exception as e:
            print(f"\n=== REGISTRATION ERROR ===\n{str(e)}\n")
            messages.error(self.request, f'An error occurred: {str(e)}')
            return self.form_invalid(form)
    
    def form_invalid(self, form):
        """Handle invalid form with debug output."""
        print("\n=== REGISTRATION FORM IS INVALID ===")
        print(f"Errors: {form.errors}")
        print(f"Non-field errors: {form.non_field_errors()}")
        
        for field, errors in form.errors.items():
            print(f"  {field}: {errors}")
        
        messages.error(self.request, 'Please correct the errors below.')
        return super().form_invalid(form)


# ============================================
# LOGIN
# ============================================

class CustomLoginView(LoginView):
    """Custom login view with rate limiting."""
    form_class = CustomAuthenticationForm
    template_name = 'accounts/login.html'
    redirect_authenticated_user = True
    
    def form_valid(self, form):
        """Log successful login."""
        email = form.cleaned_data.get('username')
        ip = self.get_client_ip(self.request)
        
        # Log successful attempt
        LoginAttempt.objects.create(email=email, ip_address=ip, is_successful=True)
        
        # Update last activity
        user = form.get_user()
        user.last_activity = timezone.now()
        user.save(update_fields=['last_activity'])
        
        messages.success(self.request, f'Welcome back, {user.first_name}!')
        return super().form_valid(form)
    
    def form_invalid(self, form):
        """Log failed attempt and apply rate limiting."""
        email = self.request.POST.get('username', '')
        ip = self.get_client_ip(self.request)
        
        LoginAttempt.objects.create(email=email, ip_address=ip, is_successful=False)
        
        recent_failures = LoginAttempt.objects.filter(
            email=email, ip_address=ip, is_successful=False,
            attempt_time__gte=timezone.now() - timezone.timedelta(minutes=15)
        ).count()
        
        if recent_failures >= 5:
            messages.error(self.request, 'Too many failed attempts. Please try again in 15 minutes.')
        else:
            messages.error(self.request, 'Invalid email or password. Please try again.')


        #added
        """Handle invalid form with detailed error messages."""
        # Print errors to console for debugging
        print("Form errors:", form.errors)
        
        # Add a general error message
        messages.error(
            self.request,
            'Please correct the errors below.'
        )
        


        return super().form_invalid(form)
    
    @staticmethod
    def get_client_ip(request):
        """Extract client IP from request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '')


# ============================================
# PASSWORD RESET WITH OTP
# ============================================

class PasswordResetRequestView(View):
    """Handle password reset request and send OTP."""
    template_name = 'accounts/password_reset_request.html'
    
    def get(self, request):
        form = PasswordResetRequestForm()
        return render(request, self.template_name, {'form': form})
    
    def post(self, request):
        form = PasswordResetRequestForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            
            try:
                with transaction.atomic():
                    user = User.objects.get(email=email)
                    
                    PasswordResetOTP.objects.filter(user=user, is_used=False).update(is_used=True)
                    otp = PasswordResetOTP.objects.create(user=user)
                    
                    self.send_otp_email(user, otp)
                    request.session['reset_email'] = email
                    
                    messages.success(request, 'A 6-digit code has been sent to your email. Valid for 10 minutes.')
                    return redirect('accounts:password_reset_verify')
                    
            except User.DoesNotExist:
                messages.success(request, 'If an account exists with this email, a reset code has been sent.')
                return redirect('accounts:login')
        
        return render(request, self.template_name, {'form': form})
    
    def send_otp_email(self, user, otp):
        """Send OTP via email."""
        subject = f'Password Reset Code - {settings.SITE_NAME}'
        message = f"""
        Hello {user.get_full_name()},
        
        You requested to reset your password. Use the code below:
        
        {otp.code}
        
        This code will expire in 10 minutes.
        
        If you didn't request this, please ignore this email.
        
        Best regards,
        {settings.SITE_NAME} Team
        """
        
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False)


class PasswordResetVerifyView(View):
    """Verify OTP and set new password."""
    template_name = 'accounts/password_reset_verify.html'
    
    def get(self, request):
        email = request.session.get('reset_email')
        if not email:
            messages.error(request, 'Please request a password reset first.')
            return redirect('accounts:password_reset_request')
        
        form = PasswordResetVerifyForm(email=email)
        return render(request, self.template_name, {'form': form})
    
    def post(self, request):
        email = request.session.get('reset_email')
        form = PasswordResetVerifyForm(request.POST, email=email)
        
        if form.is_valid():
            with transaction.atomic():
                user = User.objects.get(email=email)
                user.set_password(form.cleaned_data['new_password1'])
                user.save()
                
                form.valid_otp.mark_used()
                del request.session['reset_email']
                
                messages.success(request, 'Password reset successful! Please login with your new password.')
                return redirect('accounts:login')
        
        return render(request, self.template_name, {'form': form})


@login_required
@require_POST
def resend_otp(request):
    """Resend OTP for password reset."""
    email = request.session.get('reset_email')
    if not email:
        return JsonResponse({'success': False, 'message': 'Session expired'})
    
    try:
        user = User.objects.get(email=email)
        
        recent_otp = PasswordResetOTP.objects.filter(
            user=user, is_used=False,
            created_at__gte=timezone.now() - timezone.timedelta(minutes=2)
        ).exists()
        
        if recent_otp:
            return JsonResponse({'success': False, 'message': 'Please wait 2 minutes before requesting another code.'})
        
        otp = PasswordResetOTP.objects.create(user=user)
        view = PasswordResetRequestView()
        view.send_otp_email(user, otp)
        
        return JsonResponse({'success': True, 'message': 'New code sent successfully!'})
        
    except User.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'User not found'})


# ============================================
# PASSWORD CHANGE (Logged-in Users)
# ============================================

@login_required
def change_password(request):
    """Change password for logged-in users."""
    from django.contrib.auth.forms import PasswordChangeForm
    
    if request.method == 'POST':
        form = PasswordChangeForm(user=request.user, data=request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, 'Your password was successfully updated!')
            return redirect('accounts:profile')
        else:
            messages.error(request, 'Please correct the error below.')
    else:
        form = PasswordChangeForm(user=request.user)
    
    return render(request, 'accounts/change_password.html', {'form': form})


# ============================================
# PROFILE MANAGEMENT
# ============================================

@method_decorator(login_required, name='dispatch')
class ProfileSetupView(UpdateView):
    """Complete profile after registration - role-specific form fields."""
    model = Profile
    form_class = ProfileUpdateForm
    template_name = 'accounts/profile_setup.html'
    success_url = reverse_lazy('core:home')
    
    def get_object(self, queryset=None):
        return self.request.user.profile
    
    def get_form(self, form_class=None):
        """Get form and filter fields based on user role."""
        form = super().get_form(form_class)
        user_type = self.request.user.user_type
        
        # JobSeeker fields
        job_seeker_fields = {
            'avatar', 'skills', 'qualifications', 'experience_level', 
            'years_of_experience', 'preferred_locations', 'preferred_job_types'
        }
        
        # Employer/Admin fields
        employer_fields = {
            'avatar', 'company_name', 'company_website', 'company_description',
            'company_location', 'company_size', 'industry'
        }
        
        # Determine which fields to show
        admin_fields = {'avatar'}
        if self.request.user.is_staff or user_type == 'ADMIN':
            allowed_fields = admin_fields
        elif user_type == 'JOB_SEEKER':
            allowed_fields = job_seeker_fields
        elif user_type == 'EMPLOYER':
            allowed_fields = employer_fields
        else:
            allowed_fields = job_seeker_fields  # Default
        
        # Remove disallowed fields
        for field_name in list(form.fields.keys()):
            if field_name not in allowed_fields:
                del form.fields[field_name]
        
        return form
    
    def form_valid(self, form):
        response = super().form_valid(form)
        self.request.user.update_profile_completion()
        messages.success(self.request, 'Profile completed successfully!')
        return response


@login_required
def profile_view(request):
    """View user profile (role-specific content)."""
    profile = request.user.profile
    completion_percentage = request.user.profile_completion_percentage
    user_type = request.user.user_type
    if request.user.is_staff or user_type == 'ADMIN':
        completion_percentage = 100
        user_type = 'ADMIN'
    
    # Role-specific context
    context = {
        'profile': profile,
        'completion_percentage': completion_percentage,
        'user_type': user_type,
    }
    
    # JobSeeker-specific fields
    if user_type == 'JOB_SEEKER':
        context.update({
            'skills_list': profile.get_skills_list(),
            'locations_list': profile.get_preferred_locations_list(),
        })
    
    # Employer/Admin-specific fields
    if user_type in ['EMPLOYER', 'ADMIN']:
        context.update({
            'is_verified': request.user.is_verified_employer,
        })
    
    return render(request, 'accounts/profile.html', context)


@login_required
def user_profile_view(request, user_id):
    """
    View a specific user's profile.
    Access: 
    - Admin/Superuser can view any profile
    - Users can view their own profile
    - Employers can view applicant profiles for their jobs
    """
    user = get_object_or_404(User, pk=user_id)
    
    # Allow viewing own profile
    if request.user.id == user.id:
        pass  # Allow
    # Allow admins to view any profile
    elif request.user.is_superuser:
        pass  # Allow
    # Allow employers to view applicant profiles
    elif request.user.user_type == 'EMPLOYER':
        from apps.interactions.models import JobApplication
        # Check if the viewed user has applied to any of the employer's jobs
        has_applied = JobApplication.objects.filter(
            job__posted_by=request.user,
            applicant=user
        ).exists()
        if not has_applied:
            messages.error(request, 'You do not have permission to view this profile.')
            return redirect('core:home')
    else:
        messages.error(request, 'You do not have permission to view this profile.')
        return redirect('core:home')
    
    profile = user.profile
    completion_percentage = user.profile_completion_percentage
    user_type = user.user_type
    
    # Role-specific context
    can_edit = request.user.id == user.id

    context = {
        'profile': profile,
        'viewed_user': user,
        'completion_percentage': completion_percentage,
        'user_type': user_type,
        'is_admin_view': request.user.is_superuser or request.user.user_type == 'EMPLOYER',
        'can_edit': can_edit,
    }

    
    # JobSeeker-specific fields
    if user_type == 'JOB_SEEKER':
        context.update({
            'skills_list': profile.get_skills_list(),
            'locations_list': profile.get_preferred_locations_list(),
        })
    
    # Employer-specific fields
    if user_type in ['EMPLOYER', 'ADMIN']:
        context.update({
            'is_verified': user.is_verified_employer,
        })
    
    return render(request, 'accounts/profile.html', context)


# ============================================
# LOGOUT
# ============================================

@login_required
def logout_view(request):
    """Log out user."""
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('core:home')


# ============================================
# ACCOUNT DELETION
# ============================================

@login_required
@require_POST
def delete_account(request):
    """Allow users to delete their own account."""
    user = request.user
    password = request.POST.get('password')
    
    if not user.check_password(password):
        return JsonResponse({'success': False, 'message': 'Incorrect password. Account not deleted.'})
    
    user.delete()
    logout(request)
    
    return JsonResponse({'success': True, 'message': 'Your account has been deleted successfully.'})


# ============================================
# PROFILE API ENDPOINTS
# ============================================

@login_required
def profile_stats_api(request):
    """API endpoint for profile statistics (JobSeeker-specific)."""
    # Only JobSeekers should access profile stats
    if request.user.user_type != 'JOB_SEEKER':
        return JsonResponse(
            {'success': False, 'message': 'This feature is for job seekers only.'},
            status=403
        )
    
    profile = request.user.profile
    
    data = {
        'completion_percentage': request.user.profile_completion_percentage,
        'skills': profile.get_skills_list(),
        'locations': profile.get_preferred_locations_list(),
        'experience_level': profile.get_experience_level_display(),
        'years_of_experience': profile.years_of_experience,
    }
    
    return JsonResponse(data)


@login_required
@require_POST
def update_profile_ajax(request):
    """AJAX endpoint for updating profile fields (role-based)."""
    import json
    from json import JSONDecodeError
    
    try:
        data = json.loads(request.body or b'{}')
    except JSONDecodeError:
        return JsonResponse({'success': False, 'message': 'Invalid JSON payload.'}, status=400)
    
    field = data.get('field')
    value = data.get('value')
    user_type = request.user.user_type
    
    # Role-specific allowed fields
    if user_type == 'JOB_SEEKER':
        allowed_fields = ['skills', 'qualifications', 'preferred_locations']
    elif user_type in ['EMPLOYER', 'ADMIN']:
        allowed_fields = ['company_name', 'company_website', 'company_size']
    else:
        return JsonResponse({'success': False, 'message': 'Invalid user type.'}, status=403)
    
    if field not in allowed_fields:
        return JsonResponse({'success': False, 'message': 'Invalid field for your role.'})
    
    profile = request.user.profile
    setattr(profile, field, value)
    profile.save()
    
    request.user.update_profile_completion()
    
    return JsonResponse({'success': True, 'completion': request.user.profile_completion_percentage})