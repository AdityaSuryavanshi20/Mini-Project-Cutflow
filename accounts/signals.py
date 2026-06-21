from django.db.models.signals import post_save
from django.contrib.auth.models import User
from django.dispatch import receiver
from .models import UserProfile, UserRole

@receiver(post_save, sender=User)
def create_profile(sender, instance, created, **kwargs):
    if created:
        # Superusers (e.g. via `createsuperuser`) get the admin role by
        # default so they aren't blocked by admin-only checks (project
        # lock/unlock, etc.) on their very first login.
        default_role = UserRole.ADMIN if instance.is_superuser else UserRole.VIEWER
        UserProfile.objects.get_or_create(user=instance, defaults={'role': default_role})

@receiver(post_save, sender=User)
def save_profile(sender, instance, **kwargs):
    if hasattr(instance, 'profile'):
        instance.profile.save()
