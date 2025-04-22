# workouts/middleware.py
from django.utils import timezone
import pytz
from .models import UserProfile # Assuming UserProfile is in the same app

class TimezoneMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Check if user is authenticated and has a profile
        # Important: Middleware runs *after* authentication middleware
        if request.user.is_authenticated:
            try:
                # Adjust 'profile' if your related_name on OneToOneField is different
                user_profile = request.user.profile
                user_tz_name = user_profile.timezone
                if user_tz_name:
                    try:
                        # Activate the user's specified timezone
                        timezone.activate(pytz.timezone(user_tz_name))
                    except pytz.UnknownTimeZoneError:
                        # Handle case where stored timezone is invalid
                        # Log this error ideally
                        print(f"Warning: Invalid timezone '{user_tz_name}' for user {request.user.username}")
                        timezone.deactivate() # Fall back to default
                else:
                     # User profile exists but timezone field is empty/null
                     timezone.deactivate() # Use default timezone
            except UserProfile.DoesNotExist:
                 # User is logged in but has no profile (shouldn't happen with signals)
                 # Log this error ideally
                 print(f"Warning: UserProfile DoesNotExist for user {request.user.username}")
                 timezone.deactivate() # Use default timezone
        else:
            # User is not authenticated, use the default timezone
            timezone.deactivate()

        response = self.get_response(request)
        # You could potentially deactivate after response, but usually not necessary
        # timezone.deactivate()
        return response