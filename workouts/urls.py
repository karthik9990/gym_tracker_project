# workouts/urls.py
from django.urls import path
from . import views

app_name = 'workouts'  # Namespace for URLs

urlpatterns = [
    # We'll use one view for GET (show form/cart) and POST (add item)
    path('log/', views.log_workout_view, name='log_workout'),
    path('save/', views.save_workout_view, name='save_workout'),
    # Add other URLs later (dashboard, etc.)
]
