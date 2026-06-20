from django.db import models
from django.contrib.auth.models import User


class UserRole(models.TextChoices):
    ADMIN = 'admin', 'Admin'
    SALESMAN = 'salesman', 'Salesman'
    PRODUCTION = 'production', 'Production'
    VIEWER = 'viewer', 'Viewer'


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=UserRole.choices, default=UserRole.VIEWER)
    phone = models.CharField(max_length=20, blank=True)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} [{self.role}]"

    @property
    def is_admin(self):
        return self.role == UserRole.ADMIN

    @property
    def is_salesman(self):
        return self.role == UserRole.SALESMAN

    @property
    def is_production(self):
        return self.role == UserRole.PRODUCTION


class ActivityLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=200)
    model_name = models.CharField(max_length=100, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    details = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user} – {self.action} @ {self.created_at:%Y-%m-%d %H:%M}"
