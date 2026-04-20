"""
Authentication views with Email OTP reset functionality.
"""
from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse_lazy, reverse
from django.views.generic import CreateView, UpdateView, TemplateView
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

class RegisterView(CreateView):
    """User registration view - restricted account types."""
    model = User
    form_class = CustomUserCreationForm
    template_name = 'accounts/register.html'
    success_url = reverse_lazy('accounts:profile_setup')
    
    def form_valid(self, form):
        """Log user in after successful registration with security checks."""
        # Security: Prevent admin account creation through registration
        if form.cleaned_data.get('user_type') == 'ADMIN':
            messages.error(
                self.request,
                'Administrator accounts cannot be created through public registration.'
            )
            return self.form_invalid(form)
        
        # Ensure is_staff and is_superuser are False for all public registrations
        with transaction.atomic():
            response = super().form_valid(form)
            
            # Explicitly set staff/superuser status to False
            self.object.is_staff = False
            self.object.is_superuser = False
            self.object.save(update_fields=['is_staff', 'is_superuser'])
            
            login(self.request, self.object)
            messages.success(
                self.request,
                f'Welcome {self.object.first_name}! Please complete your profile.'
            )
        
        return response


class CustomLoginView(LoginView):
    """Custom login view with rate limiting."""
    form_class = CustomAuthenticationForm
    template_name = 'accounts/login.html'
    redirect_authenticated_user = True
    
    def form_valid(self, form):
        """Log successful login."""
        email = form.cleaned_data.get('username')
        ip = self.get_client_ip()
        
        # Log successful attempt
        LoginAttempt.objects.create(
            email=email,
            ip_address=ip,
            is_successful=True
        )
        
        messages.success(self.request, f'Welcome back!')
        return super().form_valid(form)
    
    def form_invalid(self, form):
        """Log failed attempt and apply rate limiting."""
        email = self.request.POST.get('username', '')
        ip = self.get_client_ip()
        
        # Log failed attempt
        LoginAttempt.objects.create(
            email=email,
            ip_address=ip,
            is_successful=False
        )
        
        messages.error(
            self.request,
            'Invalid email or password. Please try again.'
        )
        return super().form_invalid(form)
    
    @staticmethod
    def get_client_ip():
        """Extract client IP from request."""
        import socket
        return socket.gethostbyname(socket.gethostname())


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
                    
                    # Invalidate old unused OTPs
                    PasswordResetOTP.objects.filter(
                        user=user,
                        is_used=False
                    ).update(is_used=True)
                    
                    # Create new OTP
                    otp = PasswordResetOTP.objects.create(user=user)
                    
                    # Send email (Console for now)
                    self.send_otp_email(user, otp)
                    
                    # Store email in session for verification step
                    request.session['reset_email'] = email
                    
                    messages.success(
                        request,
                        'A 6-digit code has been sent to your email. Valid for 10 minutes.'
                    )
                    
                    return redirect('accounts:password_reset_verify')
                    
            except User.DoesNotExist:
                # Don't reveal if email exists (security)
                messages.success(
                    request,
                    'If an account exists with this email, a reset code has been sent.'
                )
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
        
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=False,
        )


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
                
                # Set new password
                user.set_password(form.cleaned_data['new_password1'])
                user.save()
                
                # Mark OTP as used
                otp = form.valid_otp
                otp.mark_used()
                
                # Clear session
                del request.session['reset_email']
                
                messages.success(
                    request,
                    'Password reset successful! Please login with your new password.'
                )
                
                return redirect('accounts:login')
        
        return render(request, self.template_name, {'form': form})


@method_decorator(login_required, name='dispatch')
class ProfileSetupView(UpdateView):
    """Complete profile after registration."""
    model = Profile
    form_class = ProfileUpdateForm
    template_name = 'accounts/profile_setup.html'
    success_url = reverse_lazy('core:home')
    
    def get_object(self, queryset=None):
        return self.request.user.profile
    
    def form_valid(self, form):
        response = super().form_valid(form)
        
        # Update profile completion percentage
        self.request.user.update_profile_completion()
        
        messages.success(self.request, 'Profile completed successfully!')
        return response


@login_required
def profile_view(request):
    """View user profile."""
    profile = request.user.profile
    completion_percentage = request.user.profile_completion_percentage
    
    context = {
        'profile': profile,
        'completion_percentage': completion_percentage,
        'skills_list': profile.get_skills_list(),
        'locations_list': profile.get_preferred_locations_list(),
    }
    return render(request, 'accounts/profile.html', context)


@login_required
def logout_view(request):
    """Log out user."""
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('core:home')


@login_required
@require_POST
def resend_otp(request):
    """Resend OTP for password reset."""
    email = request.session.get('reset_email')
    if not email:
        return JsonResponse({'success': False, 'message': 'Session expired'})
    
    try:
        user = User.objects.get(email=email)
        
        # Check if we can resend (prevent spam)
        recent_otp = PasswordResetOTP.objects.filter(
            user=user,
            is_used=False,
            created_at__gte=timezone.now() - timezone.timedelta(minutes=2)
        ).exists()
        
        if recent_otp:
            return JsonResponse({
                'success': False,
                'message': 'Please wait 2 minutes before requesting another code.'
            })
        
        # Create new OTP
        otp = PasswordResetOTP.objects.create(user=user)
        
        # Send email
        view = PasswordResetRequestView()
        view.send_otp_email(user, otp)
        
        return JsonResponse({
            'success': True,
            'message': 'New code sent successfully!'
        })
        
    except User.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'User not found'})