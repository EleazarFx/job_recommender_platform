"""
URL patterns for authentication and profile management.
"""
from django.urls import path
from . import views

app_name = 'accounts'

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
    path('profile/<int:user_id>/', views.user_profile_view, name='user_profile'),
    path('profile/', views.profile_view, name='profile'),

    # Password Management
    path('change-password/', views.change_password, name='change_password'),
    
    # Account Management
    path('delete-account/', views.delete_account, name='delete_account'),
    
    # API Endpoints
    path('api/profile/stats/', views.profile_stats_api, name='profile_stats_api'),
    path('api/profile/update/', views.update_profile_ajax, name='update_profile_ajax'),
]