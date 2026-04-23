"""
Mixins for role-based access control in class-based views.
"""
from django.contrib.auth.mixins import UserPassesTestMixin, LoginRequiredMixin
from django.shortcuts import redirect
from django.contrib import messages
from django.core.exceptions import PermissionDenied


class JobSeekerRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Only allow job seekers."""
    
    def test_func(self):
        return self.request.user.user_type == 'JOB_SEEKER'
    
    def handle_no_permission(self):
        messages.error(self.request, "This area is for job seekers only.")
        return redirect('core:home')


class EmployerRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Only allow employers."""
    
    def test_func(self):
        return self.request.user.user_type in ['EMPLOYER', 'ADMIN']
    
    def handle_no_permission(self):
        messages.error(self.request, "This area is for employers only.")
        return redirect('core:home')


class VerifiedEmployerRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Only allow verified employers."""
    
    def test_func(self):
        user = self.request.user
        return (user.user_type == 'EMPLOYER' and user.is_verified_employer) or user.user_type == 'ADMIN'
    
    def handle_no_permission(self):
        messages.error(self.request, "This feature requires a verified employer account.")
        return redirect('core:home')


class StaffRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Only allow staff members."""
    
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser
    
    def handle_no_permission(self):
        raise PermissionDenied("Staff access required.")


class AdminRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Only allow superusers."""
    
    def test_func(self):
        return self.request.user.is_superuser
    
    def handle_no_permission(self):
        raise PermissionDenied("Administrator access required.")


class ObjectOwnerRequiredMixin:
    """
    Mixin to ensure user owns the object.
    Must set owner_field and pk_url_kwarg.
    """
    owner_field = 'user'
    pk_url_kwarg = 'pk'
    model = None
    
    def dispatch(self, request, *args, **kwargs):
        if not self.model:
            raise ValueError("model attribute must be set")
        
        pk = kwargs.get(self.pk_url_kwarg)
        obj = self.model.objects.get(pk=pk)
        
        owner = getattr(obj, self.owner_field)
        
        if owner != request.user and not request.user.is_staff:
            messages.error(request, "You don't have permission to access this.")
            return redirect('core:home')
        
        return super().dispatch(request, *args, **kwargs)