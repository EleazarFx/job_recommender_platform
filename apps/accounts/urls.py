"""
URL patterns for authentication and profile management.
"""
from django.urls import path
from . import views

#app_name = 'accounts'

urlpatterns = [
    # Authentication
    path('register/', views.RegisterView.as_view(), name='register'),
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    # Password Reset with OTP
    path('password-reset/', views.PasswordResetRequestView.as_view(), name='password_reset_request'),
    path('password-reset/verify/', views.PasswordResetVerifyView.as_view(), name='password_reset_verify'),
    path('password-reset/resend-otp/', views.resend_otp, name='resend_otp'),
    
    # Profile Management
    path('profile/setup/', views.ProfileSetupView.as_view(), name='profile_setup'),
    path('profile/', views.profile_view, name='profile'),
]