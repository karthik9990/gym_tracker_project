# workouts/urls.py
from django.urls import path
from . import views

app_name = 'workouts'

urlpatterns = [
    path('', views.dashboard_view, name='dashboard'),
    # New URL for logging today (will redirect)
    path('log/today/', views.log_workout_today_redirect_view, name='log_workout_today'),
    # Updated URL to handle specific dates
    path('log/<str:date_str>/', views.log_workout_view, name='log_workout_date'),
    path('save/', views.save_workout_view, name='save_workout'),
    path('session/<int:session_id>/', views.workout_detail_view, name='workout_detail'),
    path('log/delete/<int:log_id>/', views.delete_workout_log_view, name='delete_workout_log'),
    path('profile/', views.profile_view, name='profile'),
]
