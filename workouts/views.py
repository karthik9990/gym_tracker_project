# workouts/views.py
import calendar
import datetime
import json
import pytz
import traceback
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.db.models import Count, Max
from django.db.models.functions import TruncDate
from django.http import HttpResponseNotAllowed
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone

from .forms import CustomUserCreationForm, UserProfileForm
from .models import Exercise, WorkoutSession, WorkoutLog, UserProfile


# --- Homepage View ---
def home_view(request):
    if request.user.is_authenticated:
        return redirect('workouts:dashboard')
    return render(request, 'workouts/home.html')  # Assuming you created home.html


# --- Dashboard Calendar View ---
@login_required
def dashboard_view(request):
    try:
        year = int(request.GET.get('year', timezone.now().year))
        month = int(request.GET.get('month', timezone.now().month))
        if not (1 <= month <= 12):
            month = timezone.now().month
        current_month_date = datetime.date(year, month, 1)
    except ValueError:
        current_month_date = timezone.now().date().replace(day=1)
        year = current_month_date.year
        month = current_month_date.month

    user_sessions = WorkoutSession.objects.filter(
        user=request.user,
        date__year=year,
        date__month=month
    ).annotate(
        log_count=Count('logs')  # 'logs' is the related_name from WorkoutLog model
    ).filter(
        log_count__gt=0  # Only include sessions where log_count is greater than 0
    )
    sessions_map = {session.date: session for session in user_sessions}

    cal = calendar.Calendar(firstweekday=6)  # Sunday as first day
    month_calendar_weeks = cal.monthdatescalendar(year, month)

    first_day_current_month = datetime.date(year, month, 1)
    last_day_prev_month = first_day_current_month - datetime.timedelta(days=1)
    prev_month_date = last_day_prev_month.replace(day=1)

    if month == 12:
        first_day_next_month = datetime.date(year + 1, 1, 1)
    else:
        first_day_next_month = datetime.date(year, month + 1, 1)
    next_month_date = first_day_next_month

    context = {
        'calendar_weeks': month_calendar_weeks,
        'sessions_map': sessions_map,
        'current_month_date': current_month_date,
        'prev_month_date': prev_month_date,
        'next_month_date': next_month_date,
        'todays_date_str': timezone.now().strftime('%Y-%m-%d'),
    }
    return render(request, 'workouts/dashboard.html', context)


# --- Redirect View for Logging Today ---
@login_required
def log_workout_today_redirect_view(request):
    """Redirects to the log view for today's date."""
    today_str = timezone.now().strftime('%Y-%m-%d')
    return redirect(reverse('workouts:log_workout_date', kwargs={'date_str': today_str}))


# --- Workout Logging View (for specific date) ---
@login_required
def log_workout_view(request, date_str):
    available_exercises = Exercise.objects.all().order_by('name')
    today = timezone.now().date()

    try:
        view_date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
        # Server-side date validation
        if view_date > today:
            messages.error(request, "You cannot log workouts for future dates.")
            return redirect('workouts:log_workout_today')
    except ValueError:
        messages.error(request, "Invalid date format provided.")
        return redirect('workouts:log_workout_today')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'add_item':
            # Re-check date just in case
            if view_date > today:
                messages.error(request, "Cannot add items for a future date.")
                return redirect('workouts:log_workout_today')

            try:
                exercise_id = request.POST.get('exercise')
                sets = request.POST.get('sets')
                reps = request.POST.get('reps')
                weight = request.POST.get('weight')
                # Add duration, notes fields if needed

                if not exercise_id:
                    raise ValueError("Exercise must be selected.")

                exercise = get_object_or_404(Exercise, pk=exercise_id)
                cart = request.session.get('workout_cart', {})

                if date_str not in cart:
                    cart[date_str] = []

                # Ensure values are stored appropriately (handle empty strings)
                item_data = {
                    'exercise_id': exercise.id,
                    'exercise_name': exercise.name,
                    'sets': sets if sets else None,
                    'reps': reps if reps else None,
                    'weight': weight if weight else None,
                    # Add duration, notes here if needed
                }
                cart[date_str].append(item_data)

                request.session['workout_cart'] = cart
                request.session.modified = True
                # messages.success(request, f"{exercise.name} added to workout for {date_str}.") # Optional feedback
                return redirect('workouts:log_workout_date', date_str=date_str)

            except (ValueError, Exercise.DoesNotExist) as e:
                messages.error(request, f"Error adding item: {e}")
                # Fall through to render GET

        elif action == 'change_date':
            new_date_str = request.POST.get('selected_date')
            if new_date_str:
                try:
                    new_date = datetime.datetime.strptime(new_date_str, '%Y-%m-%d').date()
                    # Validate new date against today
                    if new_date > today:
                        messages.error(request, "You cannot select a future date.")
                        return redirect('workouts:log_workout_date', date_str=date_str)  # Stay on current page
                    # Redirect to the valid selected date
                    return redirect('workouts:log_workout_date', date_str=new_date_str)
                except ValueError:
                    messages.error(request, f"Invalid date format selected: {new_date_str}")
            # If date is invalid or missing, just reload the current page
            return redirect('workouts:log_workout_date', date_str=date_str)

    # --- GET request or after failed POST ---
    cart = request.session.get('workout_cart', {})
    cart_items_for_date = cart.get(date_str, [])

    context = {
        'available_exercises': available_exercises,
        'cart_items': cart_items_for_date,
        'view_date': view_date,
        'view_date_str': date_str,
        'today_date_str': today.strftime('%Y-%m-%d'),  # Pass today's date string for max attribute
    }
    return render(request, 'workouts/log_workout.html', context)


# --- Save Workout View ---
@login_required
def save_workout_view(request):
    if request.method != 'POST':
        messages.error(request, "Invalid request method.")
        return redirect('workouts:dashboard')

    date_to_save_str = request.POST.get('date_to_save')
    today = timezone.now().date()

    if not date_to_save_str:
        messages.error(request, "Date missing from save request.")
        # Try to redirect back if possible, otherwise dashboard
        referer = request.META.get('HTTP_REFERER')
        if referer:
            return redirect(referer)
        else:
            return redirect('workouts:dashboard')

    try:
        session_date = datetime.datetime.strptime(date_to_save_str, '%Y-%m-%d').date()
        # Server-side validation before saving
        if session_date > today:
            messages.error(request, "Cannot save workout sessions for future dates.")
            return redirect('workouts:log_workout_date', date_str=date_to_save_str)
    except ValueError:
        messages.error(request, f"Invalid date format received for saving: {date_to_save_str}")
        referer = request.META.get('HTTP_REFERER')
        if referer:
            return redirect(referer)
        else:
            return redirect('workouts:dashboard')

    cart = request.session.get('workout_cart', {})
    cart_items_for_date = cart.get(date_to_save_str, [])

    # --- DEBUGGING ---
    print(f"--- Saving Workout for {date_to_save_str} ---")
    print(f"DEBUG: Raw cart from session: {request.session.get('workout_cart', {})}")
    print(f"DEBUG: Items found for this date ({date_to_save_str}): {cart_items_for_date}")
    # ---------------

    if not cart_items_for_date:
        print(f"DEBUG: Cart is empty for {date_to_save_str}, redirecting.")  # DEBUG
        messages.warning(request, f"Workout for {date_to_save_str} was empty, nothing saved.")
        return redirect('workouts:log_workout_date', date_str=date_to_save_str)

    try:
        # Transaction block could be added here for atomicity if needed
        # from django.db import transaction
        # with transaction.atomic():

        workout_session, created = WorkoutSession.objects.get_or_create(
            user=request.user,
            date=session_date,
            defaults={'notes': request.POST.get('session_notes', '')}  # Example: Optionally save notes
        )
        print(f"DEBUG: Got/Created WorkoutSession ID: {workout_session.id}, Created: {created}")  # DEBUG

        # --- DEBUG THE LOOP ---
        print("DEBUG: Entering loop to create WorkoutLog entries...")
        log_count = 0
        for item in cart_items_for_date:
            print(f"DEBUG: Processing item: {item}")  # See item dictionary
            try:
                if 'exercise_id' not in item or not item['exercise_id']:
                    print("DEBUG: Skipping item - 'exercise_id' is missing or empty.")
                    continue

                exercise = Exercise.objects.get(pk=item['exercise_id'])
                print(f"DEBUG: Found Exercise: {exercise.name}")  # DEBUG

                # Prepare data, handling potential None/empty strings
                sets_val = item.get('sets')
                reps_val = item.get('reps')
                weight_val = item.get('weight')
                # Add duration, notes retrieval if needed

                log = WorkoutLog.objects.create(
                    session=workout_session,
                    exercise=exercise,
                    sets=int(sets_val) if sets_val else None,
                    reps=int(reps_val) if reps_val else None,
                    weight=float(weight_val) if weight_val else None,
                    # duration=... # Add similarly
                    # notes=item.get('notes') # Add similarly
                )
                log_count += 1
                print(f"DEBUG: Successfully created WorkoutLog ID: {log.id} for {exercise.name}")  # DEBUG

            except Exercise.DoesNotExist:
                print(f"DEBUG: Skipping item - Exercise with ID {item.get('exercise_id')} not found.")
                messages.warning(request, f"Exercise ID {item.get('exercise_id')} not found, skipped.")
                continue
            except (KeyError, ValueError, TypeError) as e:
                print(f"DEBUG: ERROR processing item {item}: {type(e).__name__} - {e}")
                messages.error(request, f"Error processing item {item.get('exercise_name', 'Unknown')}: {e}")
                continue  # Skip this item but try to save others
        # --- END LOOP DEBUG ---

        print(f"DEBUG: Finished loop. Created {log_count} WorkoutLog entries.")  # DEBUG

        # Clear the specific date's items from the cart ONLY if logs were created successfully
        # (Or adjust logic based on whether partial saves are acceptable)
        if log_count > 0 or not cart_items_for_date:  # Clear if successful or if cart was empty initially
            if date_to_save_str in request.session.get('workout_cart', {}):
                print(f"DEBUG: Clearing cart key: {date_to_save_str}")  # DEBUG
                del request.session['workout_cart'][date_to_save_str]
                request.session.modified = True
            else:
                print(f"DEBUG: Warning - Cart key {date_to_save_str} not found during clearing, though items existed.")

        if log_count > 0:
            messages.success(request, f"Workout for {session_date.strftime('%B %d, %Y')} saved successfully!")
        else:
            messages.warning(request,
                             f"Workout for {session_date.strftime('%B %d, %Y')} saved, but no valid exercises were logged.")

        return redirect('workouts:dashboard')

    except Exception as e:
        # This block handles errors during session creation or other unexpected issues
        error_context_date_str = request.POST.get('date_to_save', 'unknown_date')

        print(f"DEBUG: UNEXPECTED ERROR during save for date '{error_context_date_str}': {type(e).__name__} - {e}")
        traceback.print_exc()  # Print full traceback to console

        messages.error(request,
                       f"An unexpected error occurred while saving the workout. Please check logs or contact support.")

        # Redirect back robustly
        if error_context_date_str != 'unknown_date':
            try:
                datetime.datetime.strptime(error_context_date_str, '%Y-%m-%d')
                return redirect('workouts:log_workout_date', date_str=error_context_date_str)
            except ValueError:
                pass
        return redirect('workouts:dashboard')


# --- Workout Detail View ---
@login_required
def workout_detail_view(request, session_id):
    workout_session = get_object_or_404(WorkoutSession, pk=session_id, user=request.user)
    # Fetch logs once
    session_logs = workout_session.logs.all().order_by('id')

    # --- Calculate Number of Exercises ---
    log_count = session_logs.count()
    # -----------------------------------

    # --- Find Heaviest Lift ---
    heaviest_lift_weight = None
    heaviest_lift_exercise_name = None
    if log_count > 0: # Optimization: Only query max weight if logs exist
        max_weight_aggregate = session_logs.filter(weight__isnull=False).aggregate(max_w=Max('weight'))
        if max_weight_aggregate and max_weight_aggregate['max_w'] is not None:
            heaviest_lift_weight = max_weight_aggregate['max_w']
            # Find the exercise name (get first log matching the max weight)
            first_log_with_max = session_logs.filter(weight=heaviest_lift_weight).select_related('exercise').first()
            if first_log_with_max:
                heaviest_lift_exercise_name = first_log_with_max.exercise.name
    # --------------------------

    context = {
        'session': workout_session,
        'logs': session_logs,
        'log_count': log_count, # Pass count
        'heaviest_lift_weight': heaviest_lift_weight, # Pass max weight
        'heaviest_lift_exercise_name': heaviest_lift_exercise_name, # Pass exercise name
    }
    return render(request, 'workouts/workout_detail.html', context)



def signup_view(request):
    if request.user.is_authenticated:
        # If user is already logged in, redirect them away
        return redirect('workouts:dashboard')  # Or 'home'

    if request.method == 'POST':
        # Use the standard UserCreationForm
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()  # Creates the standard (non-staff) user
            messages.success(request, "Registration successful! Please log in.")
            # Redirect to the LOGIN page
            return redirect('login')  # Redirect to the view named 'login'
        else:
            # Form is invalid, re-render with errors
            # Errors will be embedded in the form object
            messages.error(request, "Please correct the errors shown below.")
    else:
        # Display an empty standard form for a GET request
        form = UserCreationForm()

    context = {'form': form}
    # Use the same template name for consistency
    return render(request, 'registration/signup.html', context)


@login_required
def delete_workout_log_view(request, log_id):
    """Deletes a specific WorkoutLog entry."""
    # Ensure this view only accepts POST requests for safety
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])  # Return 405 Method Not Allowed

    # Get the log entry, ensuring it exists and belongs to the current user's session
    log_entry = get_object_or_404(WorkoutLog, pk=log_id, session__user=request.user)

    # Store the session ID *before* deleting the log, so we can redirect back
    session_id = log_entry.session.id

    try:
        # Delete the log entry
        log_entry.delete()
        messages.success(request, f"Workout entry '{log_entry.exercise.name}' deleted successfully.")
    except Exception as e:
        # Handle potential errors during deletion (less common)
        messages.error(request, f"Could not delete entry: {e}")
        print(f"Error deleting WorkoutLog ID {log_id}: {e}")

    # Redirect back to the workout detail page for the session it belonged to
    return redirect('workouts:workout_detail', session_id=session_id)


@login_required
def profile_view(request):
    # Get the user's profile, creating if it somehow doesn't exist (though signal should handle it)
    profile, created = UserProfile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        form = UserProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, 'Your profile has been updated.')
            # Activate the new timezone immediately for this request if needed
            try:
                timezone.activate(pytz.timezone(profile.timezone))
            except pytz.UnknownTimeZoneError:
                messages.warning(request, "Selected timezone is invalid, using default.")
                timezone.deactivate()  # Revert to default

            return redirect('workouts:profile')  # Redirect back to profile page
        else:
            messages.error(request, 'Please correct the errors below.')
    else:  # GET request
        form = UserProfileForm(instance=profile)

    context = {
        'form': form,
        'profile': profile  # Pass profile for display if needed
    }
    return render(request, 'workouts/profile.html', context)


@login_required
def exercise_stats_view(request, exercise_id):
    exercise = get_object_or_404(Exercise, pk=exercise_id)

    # --- Fetch ALL logs for the user and this exercise ---
    # We need sets, reps, weight, and date to calculate volume per day
    all_logs = WorkoutLog.objects.filter(
        session__user=request.user,
        exercise=exercise,
        sets__isnull=False,  # Ensure all needed fields exist for volume calc
        reps__isnull=False,
        weight__isnull=False
    ).select_related('session').order_by('session__date')  # Get session data efficiently

    # --- Process data for charts (Weight and Volume) ---
    # Use dictionaries to aggregate data per date
    daily_max_weight = {}
    daily_volume = {}

    for log in all_logs:
        log_date = log.session.date
        log_date_str = log_date.strftime('%Y-%m-%d')  # Consistent date string

        # Calculate volume for this specific log entry
        try:
            volume = Decimal(log.sets) * Decimal(log.reps) * Decimal(log.weight)
        except (TypeError, ValueError):
            volume = Decimal('0.0')  # Ignore if data is invalid

        # Aggregate Max Weight per day
        current_max = daily_max_weight.get(log_date_str, Decimal('0.0'))
        if log.weight > current_max:
            daily_max_weight[log_date_str] = log.weight

        # Aggregate Total Volume per day
        current_volume = daily_volume.get(log_date_str, Decimal('0.0'))
        daily_volume[log_date_str] = current_volume + volume

    # Prepare data for Chart.js - Sort by date string keys
    chart_dates = sorted(daily_max_weight.keys())  # Use dates from max weight dict (or volume)
    chart_weights = [float(daily_max_weight[dt]) for dt in chart_dates]
    chart_volumes = [float(daily_volume.get(dt, 0.0)) for dt in chart_dates]  # Get volume for sorted dates

    has_data = bool(chart_dates)  # Check if we have any dates to plot

    # --- Calculate Personal Record (PR) - Max Weight (Keep as before) ---
    personal_record = None
    pr_query = WorkoutLog.objects.filter(
        session__user=request.user,
        exercise=exercise,
        weight__isnull=False
    ).aggregate(max_overall_weight=Max('weight'))
    if pr_query and pr_query['max_overall_weight'] is not None:
        personal_record = pr_query['max_overall_weight']
    # -------------------------------------

    context = {
        'exercise': exercise,
        'dates_json': json.dumps(chart_dates),  # Dates for both charts
        'weights_json': json.dumps(chart_weights),  # Max Weight data
        'volumes_json': json.dumps(chart_volumes),  # Volume data
        'has_data': has_data,
        'personal_record': personal_record,
    }
    return render(request, 'workouts/exercise_stats.html', context)
