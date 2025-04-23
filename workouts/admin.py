# workouts/admin.py
from django.contrib import admin
from .models import Exercise, WorkoutSession, WorkoutLog, UserProfile

admin.site.register(Exercise)
admin.site.register(WorkoutSession)
admin.site.register(WorkoutLog)
admin.site.register(UserProfile)