# workouts/models.py
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class Exercise(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)

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
    exercise = models.ForeignKey(Exercise, on_delete=models.PROTECT) # Protect exercise from deletion if used
    sets = models.PositiveIntegerField(blank=True, null=True)
    reps = models.PositiveIntegerField(blank=True, null=True)
    weight = models.DecimalField(max_digits=6, decimal_places=2, blank=True, null=True)
    duration = models.DurationField(blank=True, null=True) # e.g., for cardio
    notes = models.TextField(blank=True, null=True)

    def __str__(self):
        details = f"{self.exercise.name}"
        if self.sets and self.reps: details += f" - {self.sets}x{self.reps}"
        if self.weight: details += f" @ {self.weight}kg"
        if self.duration: details += f" for {self.duration}"
        return details