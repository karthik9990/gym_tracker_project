# workouts/admin.py
from django.contrib import admin
from .models import Exercise, WorkoutSession, WorkoutLog

admin.site.register(Exercise)
admin.site.register(WorkoutSession)
admin.site.register(WorkoutLog)