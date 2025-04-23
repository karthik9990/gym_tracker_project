# workouts/models.py
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import pytz
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver


class Exercise(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    # --- ADD THIS FIELD ---
    # Links to the user who created this exercise.
    # null=True means admin/global exercises don't need a user.
    # blank=True allows the field to be empty in forms (like the admin).
    # on_delete=models.CASCADE means if a user is deleted, their custom exercises are also deleted.
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.CASCADE, related_name='custom_exercises')

    # --------------------
    class Meta:
        # Ensure exercise names are unique *per user* (or globally if preferred)
        # If user is NULL (global), name must be unique among other global ones.
        # If user is set, name must be unique *for that specific user*.
        unique_together = ('user', 'name')  # Makes name unique for a specific user (or globally if user is None)
        ordering = ['name']  # Keep exercises ordered alphabetically

    def __str__(self):
        return self.name


class WorkoutSession(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    date = models.DateField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True, null=True)

    class Meta:
        unique_together = ('user', 'date')
        ordering = ['-date']

    def __str__(self):
        return f"{self.user.username}'s workout on {self.date}"


class WorkoutLog(models.Model):
    session = models.ForeignKey(WorkoutSession, related_name='logs', on_delete=models.CASCADE)
    exercise = models.ForeignKey(Exercise, on_delete=models.PROTECT)  # Protect exercise from deletion if used
    sets = models.PositiveIntegerField(blank=True, null=True)
    reps = models.PositiveIntegerField(blank=True, null=True)
    weight = models.DecimalField(max_digits=6, decimal_places=2, blank=True, null=True)
    duration = models.DurationField(blank=True, null=True)  # e.g., for cardio
    notes = models.TextField(blank=True, null=True)

    def __str__(self):
        details = f"{self.exercise.name}"
        if self.sets and self.reps: details += f" - {self.sets}x{self.reps}"
        if self.weight: details += f" @ {self.weight}kg"
        if self.duration: details += f" for {self.duration}"
        return details


# --- User Profile Model ---
class UserProfile(models.Model):
    # Ensure pytz is installed: pip install pytz
    TIMEZONE_CHOICES = [(tz, tz) for tz in pytz.common_timezones]  # Use common_timezones for a reasonable list

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    timezone = models.CharField(
        max_length=63,  # Max length of tz database names
        choices=TIMEZONE_CHOICES,
        default=settings.TIME_ZONE,  # Default to project's timezone
        # Or use 'UTC' as a safer default: default='UTC'
        help_text="Select your local time zone."
    )

    def __str__(self):
        return f"{self.user.username}'s Profile"


# --- Signal to create/update UserProfile automatically ---
@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    """Create a UserProfile when a new User is created."""
    if created:
        UserProfile.objects.create(user=instance)
    # If you want updates to User to potentially update profile:
    # instance.profile.save() # But be careful what you save here
