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
    path('log/remove/<str:date_str>/<int:item_index>/', views.remove_from_cart_view, name='remove_from_cart'),
    path('save/', views.save_workout_view, name='save_workout'),
    path('session/<int:session_id>/', views.workout_detail_view, name='workout_detail'),
    path('log/delete/<int:log_id>/', views.delete_workout_log_view, name='delete_workout_log'),
    path('stats/exercise/<int:exercise_id>/', views.exercise_stats_view, name='exercise_stats'),
    path('report/monthly/', views.monthly_report_view, name='monthly_report'),
    path('report/monthly/<int:year>/<int:month>/', views.monthly_report_view, name='monthly_report_specific'),
    path('tools/health/', views.health_tools_view, name='health_tools'),
    path('profile/', views.profile_view, name='profile'),
    path('exercises/add/', views.add_custom_exercise_view, name='add_custom_exercise'),
    path('exercises/delete/<int:exercise_id>/', views.delete_custom_exercise_view, name='delete_custom_exercise'),

]
