# workouts/views.py

# Standard Python imports
import calendar
import datetime
import json
import pytz
import traceback
from collections import defaultdict
from decimal import Decimal

# Django imports
from django.contrib import messages
from django.contrib.auth import login # Note: login is imported but not used in current views
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm # For the simple signup view
from django.db.models import Count, Max
from django.db.models.functions import TruncDate
from django.http import HttpResponseNotAllowed, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

# Local app imports (Ensure these paths are correct)
# If using the simple signup, CustomUserCreationForm might not be needed here
# from .forms import CustomUserCreationForm
from .forms import UserProfileForm
from .models import Exercise, WorkoutSession, WorkoutLog, UserProfile


# --- Homepage View ---
def home_view(request):
    """Displays the homepage, redirecting logged-in users to the dashboard."""
    if request.user.is_authenticated:
        return redirect('workouts:dashboard')
    # Assumes 'workouts/home.html' exists in your templates
    return render(request, 'workouts/home.html')


# --- Dashboard Calendar View ---
@login_required
def dashboard_view(request):
    """Displays the user's workout calendar for a given month."""
    try:
        # Determine target month/year from GET params or default to current
        year = int(request.GET.get('year', timezone.now().year))
        month = int(request.GET.get('month', timezone.now().month))
        if not (1 <= month <= 12):
            month = timezone.now().month
        # Validate year range (optional but good practice)
        current_year = timezone.now().year
        if not (current_year - 10 <= year <= current_year + 1):
             raise ValueError("Year out of reasonable range")
        current_month_date = datetime.date(year, month, 1)
    except ValueError:
        # Handle invalid parameters or construction errors
        messages.warning(request, "Invalid date parameters, showing current month.")
        current_month_date = timezone.now().date().replace(day=1)
        year = current_month_date.year
        month = current_month_date.month

    # Fetch sessions for the month that actually have logs
    user_sessions = WorkoutSession.objects.filter(
        user=request.user,
        date__year=year,
        date__month=month
    ).annotate(
        log_count=Count('logs')
    ).filter(
        log_count__gt=0
    )
    # Create a map for easy lookup in the template
    sessions_map = {session.date: session for session in user_sessions}

    # Prepare calendar data
    cal = calendar.Calendar(firstweekday=6) # Sunday start
    month_calendar_weeks = cal.monthdatescalendar(year, month)

    # Calculate previous/next month for navigation links
    first_day_current_month = datetime.date(year, month, 1)
    last_day_prev_month = first_day_current_month - datetime.timedelta(days=1)
    prev_month_date = last_day_prev_month # Use the actual date for linking year/month

    if month == 12:
        first_day_next_month = datetime.date(year + 1, 1, 1)
    else:
        first_day_next_month = datetime.date(year, month + 1, 1)
    next_month_date = first_day_next_month # Use the actual date for linking year/month

    context = {
        'calendar_weeks': month_calendar_weeks,
        'sessions_map': sessions_map,
        'current_month_date': current_month_date,
        'prev_month_date': prev_month_date,
        'next_month_date': next_month_date,
        'todays_date_str': timezone.now().strftime('%Y-%m-%d'), # For max date attribute
    }
    return render(request, 'workouts/dashboard.html', context)


# --- Redirect View for Logging Today ---
@login_required
def log_workout_today_redirect_view(request):
    """Redirects to the log view for today's date."""
    today_str = timezone.now().strftime('%Y-%m-%d')
    # Use reverse for robust URL generation
    return redirect(reverse('workouts:log_workout_date', kwargs={'date_str': today_str}))


# --- Workout Logging View (Handles GET, POST, AJAX POST) ---
@login_required
def log_workout_view(request, date_str):
    """
    Displays the workout logging form for a specific date (GET)
    and processes form submissions for changing dates or adding items
    to the session cart (POST), supporting both AJAX and regular submissions
    for adding items.
    """
    today = timezone.now().date()

    # --- Validate and parse the target date from URL ---
    try:
        view_date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
        if view_date > today:
            messages.error(request, "You cannot log workouts for future dates.")
            return redirect('workouts:log_workout_today')
    except ValueError:
        messages.error(request, "Invalid date format provided.")
        return redirect('workouts:log_workout_today')

    available_exercises = Exercise.objects.all().order_by('name')

    # --- Handle POST Requests ---
    if request.method == 'POST':
        action = request.POST.get('action')
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

        # --- Action: Add Exercise Item to Cart ---
        if action == 'add_item':
            form_valid = False
            error_message = "An unknown error occurred adding the item." # Default error
            item_data = {} # Initialize for scope in non-AJAX message

            try:
                # Re-validate date just in case
                if view_date > today:
                    raise ValueError("Cannot add items for a future date.")

                # Get data from POST
                exercise_id = request.POST.get('exercise')
                sets = request.POST.get('sets')
                reps = request.POST.get('reps')
                weight = request.POST.get('weight')

                # Basic Validation
                if not exercise_id:
                    raise ValueError("Exercise must be selected.")

                exercise = get_object_or_404(Exercise, pk=exercise_id)

                # Prepare item data for session storage
                item_data = {
                    'exercise_id': exercise.id,
                    'exercise_name': exercise.name,
                    'sets': sets if sets else None,
                    'reps': reps if reps else None,
                    'weight': weight if weight else None,
                    # Add other fields like duration/notes here if needed
                }

                # Update session cart
                cart = request.session.get('workout_cart', {})
                if date_str not in cart:
                    cart[date_str] = []
                cart[date_str].append(item_data)
                request.session['workout_cart'] = cart
                request.session.modified = True
                form_valid = True # Mark as successful

            except (ValueError, Exercise.DoesNotExist, KeyError) as e:
                error_message = f"{e}" # Use the specific exception message
                print(f"Error adding item to cart for date {date_str}: {error_message}") # Log error
                form_valid = False
            except Exception as e:
                # Catch any other unexpected errors during item add process
                error_message = "An unexpected server error occurred while adding the item."
                print(f"Unexpected error adding item for date {date_str}: {e}")
                traceback.print_exc() # Print full traceback
                form_valid = False

            # --- Respond: AJAX or Full Reload ---
            if is_ajax:
                if form_valid:
                    # Get updated cart items for the partial template
                    current_cart = request.session.get('workout_cart', {})
                    cart_items = current_cart.get(date_str, [])
                    context_for_partial = {'cart_items': cart_items}
                    try:
                        # Render ONLY the partial template
                        html_fragment = render_to_string(
                            'workouts/partials/cart_items_list.html',
                            context_for_partial
                        )
                        return JsonResponse({'success': True, 'cart_html': html_fragment})
                    except Exception as e:
                         # Catch potential template rendering errors for AJAX
                         print(f"Error rendering partial template for AJAX: {e}")
                         traceback.print_exc()
                         return JsonResponse({'success': False, 'error': 'Error updating cart display.'}, status=500)
                else:
                    # Return JSON error for AJAX request
                    return JsonResponse({'success': False, 'error': error_message}, status=400) # Bad Request
            else: # Regular (non-AJAX) form submission
                if form_valid:
                    messages.success(request, f"{item_data.get('exercise_name', 'Item')} added to workout.")
                else:
                    messages.error(request, error_message)
                # Always redirect after a non-AJAX POST
                return redirect('workouts:log_workout_date', date_str=date_str)

        # --- Action: Change Date ---
        elif action == 'change_date':
            new_date_str = request.POST.get('selected_date')
            if new_date_str:
                try:
                    new_date = datetime.datetime.strptime(new_date_str, '%Y-%m-%d').date()
                    if new_date > today: # Use 'today' defined earlier
                        messages.error(request, "You cannot select a future date.")
                        return redirect('workouts:log_workout_date', date_str=date_str) # Stay on current page
                    # Redirect to the new valid date's log page
                    return redirect('workouts:log_workout_date', date_str=new_date_str)
                except ValueError:
                    messages.error(request, f"Invalid date format selected: {new_date_str}")
            # If invalid date or no date provided, redirect back to the current page
            return redirect('workouts:log_workout_date', date_str=date_str)

        # Handle other POST actions if needed, or redirect if action is unknown
        else:
            messages.warning(request, "Unknown form action submitted.")
            return redirect('workouts:log_workout_date', date_str=date_str)

    # --- Handle GET Request (Initial page load) ---
    else:
        cart = request.session.get('workout_cart', {})
        cart_items_for_date = cart.get(date_str, [])

        context = {
            'available_exercises': available_exercises,
            'cart_items': cart_items_for_date, # Items for the initial render
            'view_date': view_date,
            'view_date_str': date_str,
            'today_date_str': today.strftime('%Y-%m-%d'), # For date input max attribute
        }
        return render(request, 'workouts/log_workout.html', context)


# --- Save Workout View ---
@login_required
def save_workout_view(request):
    """Saves the items from the session cart for a specific date to the database."""
    if request.method != 'POST':
        messages.error(request, "Invalid request method for saving.")
        return redirect('workouts:dashboard')

    date_to_save_str = request.POST.get('date_to_save')
    today = timezone.now().date()

    # Validate date presence
    if not date_to_save_str:
        messages.error(request, "Date missing from save request.")
        referer = request.META.get('HTTP_REFERER', reverse('workouts:dashboard')) # Safer fallback
        return redirect(referer)

    # Validate date format and ensure it's not in the future
    try:
        session_date = datetime.datetime.strptime(date_to_save_str, '%Y-%m-%d').date()
        if session_date > today:
            messages.error(request, "Cannot save workout sessions for future dates.")
            return redirect('workouts:log_workout_date', date_str=date_to_save_str)
    except ValueError:
        messages.error(request, f"Invalid date format received for saving: {date_to_save_str}")
        referer = request.META.get('HTTP_REFERER', reverse('workouts:dashboard'))
        return redirect(referer)

    # Retrieve cart items for the date
    cart = request.session.get('workout_cart', {})
    cart_items_for_date = cart.get(date_to_save_str, [])

    # Check if there's anything to save
    if not cart_items_for_date:
        messages.warning(request, f"Workout for {date_to_save_str} was empty, nothing saved.")
        return redirect('workouts:log_workout_date', date_str=date_to_save_str)

    # --- Save to Database ---
    try:
        # Use a transaction potentially? from django.db import transaction; with transaction.atomic():
        workout_session, created = WorkoutSession.objects.get_or_create(
            user=request.user,
            date=session_date,
            defaults={'notes': request.POST.get('session_notes', '')} # Save session notes if provided
        )
        if not created and request.POST.get('session_notes'): # If session existed, update notes if new ones provided
            workout_session.notes = request.POST.get('session_notes', '')
            workout_session.save()

        log_count = 0
        errors_during_log_creation = False
        for item in cart_items_for_date:
            try:
                if 'exercise_id' not in item or not item['exercise_id']: continue # Skip if no ID

                exercise = Exercise.objects.get(pk=item['exercise_id']) # Use get not get_or_404 inside loop

                # Prepare data, handling potential type errors during conversion
                try:
                    sets_val = int(item.get('sets')) if item.get('sets') else None
                    reps_val = int(item.get('reps')) if item.get('reps') else None
                    weight_val = float(item.get('weight')) if item.get('weight') else None
                except (ValueError, TypeError):
                    print(f"Warning: Invalid data type for sets/reps/weight in item {item}. Skipping calculation.")
                    sets_val, reps_val, weight_val = None, None, None # Or handle as needed

                WorkoutLog.objects.create(
                    session=workout_session,
                    exercise=exercise,
                    sets=sets_val,
                    reps=reps_val,
                    weight=weight_val,
                    # notes=item.get('notes') # If you add notes per item
                )
                log_count += 1

            except Exercise.DoesNotExist:
                messages.warning(request, f"Exercise ID {item.get('exercise_id')} in cart not found, skipped.")
                errors_during_log_creation = True
                continue
            except (KeyError, Exception) as e: # Catch other potential errors per item
                messages.error(request, f"Error saving log for {item.get('exercise_name', 'Unknown')}: {e}")
                print(f"Error processing log item {item}: {e}")
                errors_during_log_creation = True
                continue

        # --- Clean up session cart ---
        if date_to_save_str in request.session.get('workout_cart', {}):
            del request.session['workout_cart'][date_to_save_str]
            request.session.modified = True

        # --- Final Feedback Message ---
        if log_count > 0 and not errors_during_log_creation:
            messages.success(request, f"Workout for {session_date.strftime('%B %d, %Y')} saved successfully!")
        elif log_count > 0 and errors_during_log_creation:
             messages.warning(request, f"Workout for {session_date.strftime('%B %d, %Y')} saved, but some items had errors.")
        else: # log_count == 0
            messages.error(request, f"Workout for {session_date.strftime('%B %d, %Y')} could not be saved due to errors with all items.")
        return redirect('workouts:dashboard')

    except Exception as e:
        # Handle unexpected errors during session creation or the overall save process
        print(f"Unexpected error during save_workout_view for date '{date_to_save_str}': {e}")
        traceback.print_exc()
        messages.error(request, f"An unexpected error occurred while saving the workout. Please try again.")
        # Redirect back to the log page where the save was attempted
        return redirect('workouts:log_workout_date', date_str=date_to_save_str)


# --- Workout Detail View ---
@login_required
def workout_detail_view(request, session_id):
    """Displays the details of a specific saved workout session."""
    workout_session = get_object_or_404(WorkoutSession, pk=session_id, user=request.user)
    session_logs = workout_session.logs.all().select_related('exercise').order_by('id') # Efficiently get logs and exercise

    # Calculate number of logs
    log_count = session_logs.count()

    # Find heaviest lift in this session
    heaviest_lift_weight = None
    heaviest_lift_exercise_name = None
    if log_count > 0:
        max_weight_aggregate = session_logs.filter(weight__isnull=False).aggregate(max_w=Max('weight'))
        if max_weight_aggregate and max_weight_aggregate['max_w'] is not None:
            heaviest_lift_weight = max_weight_aggregate['max_w']
            # Find one exercise name associated with this max weight
            first_log_with_max = session_logs.filter(weight=heaviest_lift_weight).first()
            if first_log_with_max: # Check if found (might have weight but no logs match exactly if Decimal issue)
                heaviest_lift_exercise_name = first_log_with_max.exercise.name

    context = {
        'session': workout_session,
        'logs': session_logs,
        'log_count': log_count,
        'heaviest_lift_weight': heaviest_lift_weight,
        'heaviest_lift_exercise_name': heaviest_lift_exercise_name,
    }
    return render(request, 'workouts/workout_detail.html', context)


# --- Signup View (Using Standard Django Form) ---
def signup_view(request):
    """Handles user registration."""
    if request.user.is_authenticated:
        return redirect('workouts:dashboard')

    if request.method == 'POST':
        form = UserCreationForm(request.POST) # Standard form
        if form.is_valid():
            form.save()
            messages.success(request, "Registration successful! Please log in.")
            return redirect('login') # Redirect to login page
        else:
            messages.error(request, "Please correct the errors shown below.")
    else:
        form = UserCreationForm()

    context = {'form': form}
    return render(request, 'registration/signup.html', context)


# --- Delete Workout Log View ---
@login_required
def delete_workout_log_view(request, log_id):
    """Deletes a specific WorkoutLog entry via POST request."""
    if request.method != 'POST':
        messages.error(request, "Invalid method for deleting log entry.")
        return HttpResponseNotAllowed(['POST'])

    log_entry = get_object_or_404(WorkoutLog, pk=log_id, session__user=request.user)
    session_id = log_entry.session.id # Get session ID before deleting

    try:
        entry_name = log_entry.exercise.name # Get name for message
        log_entry.delete()
        messages.success(request, f"Workout entry '{entry_name}' deleted successfully.")
    except Exception as e:
        messages.error(request, f"Could not delete entry: {e}")
        print(f"Error deleting WorkoutLog ID {log_id}: {e}")

    # Redirect back to the detail page of the session it belonged to
    return redirect('workouts:workout_detail', session_id=session_id)


# --- User Profile View ---
@login_required
def profile_view(request):
    """Displays and handles updates to the user's profile (e.g., timezone)."""
    # Use get_or_create for robustness, though signal should handle creation
    profile, created = UserProfile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        form = UserProfileForm(request.POST, instance=profile)
        if form.is_valid():
            saved_profile = form.save()
            messages.success(request, 'Your profile has been updated.')
            # Activate the new timezone immediately for this request session
            try:
                timezone.activate(pytz.timezone(saved_profile.timezone))
            except pytz.UnknownTimeZoneError:
                messages.warning(request, "Selected timezone is invalid, using default.")
                timezone.deactivate() # Revert to default if selected one fails

            return redirect('workouts:profile') # Redirect back to profile page
        else:
            messages.error(request, 'Please correct the errors below.')
    else: # GET request
        form = UserProfileForm(instance=profile)

    context = {
        'form': form,
        'profile': profile
    }
    return render(request, 'workouts/profile.html', context)


# --- Exercise Stats View ---
@login_required
def exercise_stats_view(request, exercise_id):
    """Displays progress charts and PR for a specific exercise."""
    exercise = get_object_or_404(Exercise, pk=exercise_id)

    # Fetch logs with necessary data for charts and PR
    all_logs = WorkoutLog.objects.filter(
        session__user=request.user,
        exercise=exercise,
        weight__isnull=False # Need weight for both PR and charts here
        # Could relax this if charting something else like reps only
    ).select_related('session').order_by('session__date')

    # Process data for charts
    daily_max_weight = {}
    daily_volume = defaultdict(Decimal) # Use defaultdict for easier aggregation

    for log in all_logs:
        # Ensure data needed for calculations is present for this log
        if log.sets is not None and log.reps is not None and log.weight is not None:
            log_date = log.session.date
            log_date_str = log_date.strftime('%Y-%m-%d')

            # Aggregate Max Weight
            current_max = daily_max_weight.get(log_date_str, Decimal('-1')) # Use -1 to handle 0 weight
            if log.weight > current_max:
                daily_max_weight[log_date_str] = log.weight

            # Aggregate Volume
            try:
                volume = Decimal(log.sets) * Decimal(log.reps) * Decimal(log.weight)
                daily_volume[log_date_str] += volume
            except (TypeError, ValueError):
                pass # Ignore volume calculation for this log if data invalid

    # Prepare data for Chart.js
    # Use dates from max weight dict keys, ensuring consistency
    chart_dates = sorted(daily_max_weight.keys())
    chart_weights = [float(daily_max_weight[dt]) for dt in chart_dates]
    # Get volume for the same sorted dates, defaulting to 0 if no volume was calculated
    chart_volumes = [float(daily_volume.get(dt, Decimal('0.0'))) for dt in chart_dates]

    has_data = bool(chart_dates)

    # Calculate Personal Record (Max Weight)
    personal_record = None
    # Use the already filtered all_logs QuerySet if it contains all needed entries,
    # otherwise, perform a separate aggregate query for clarity/correctness
    pr_query = WorkoutLog.objects.filter(
            session__user=request.user,
            exercise=exercise,
            weight__isnull=False
        ).aggregate(max_overall_weight=Max('weight'))

    if pr_query and pr_query['max_overall_weight'] is not None:
         personal_record = pr_query['max_overall_weight']

    context = {
        'exercise': exercise,
        'dates_json': json.dumps(chart_dates),
        'weights_json': json.dumps(chart_weights),
        'volumes_json': json.dumps(chart_volumes),
        'has_data': has_data,
        'personal_record': personal_record,
    }
    return render(request, 'workouts/exercise_stats.html', context)


# --- Monthly Report View ---
@login_required
def monthly_report_view(request, year=None, month=None):
    """Generates and displays a detailed daily breakdown report for a month."""

    # --- Determine Target Year and Month ---
    if year is None or month is None:
        year_str = request.GET.get('year')
        month_str = request.GET.get('month')
        if year_str and month_str:
            try:
                year = int(year_str)
                month = int(month_str)
                if not (1 <= month <= 12): raise ValueError("Invalid Month")
                current_yr = timezone.now().year
                if not (current_yr - 10 <= year <= current_yr + 1): raise ValueError("Invalid Year")
                # Redirect to the cleaner URL
                return redirect('workouts:monthly_report_specific', year=year, month=month)
            except ValueError:
                messages.error(request, "Invalid date selection. Showing current month.")
                today = timezone.now().date()
                year = today.year
                month = today.month
        else:
            today = timezone.now().date()
            year = today.year
            month = today.month
    else: # Year/Month provided in URL, validate them
        try:
            if not (1 <= month <= 12): raise ValueError("Invalid Month")
            current_year = timezone.now().year
            if not (current_year - 10 <= year <= current_year + 1): raise ValueError("Invalid Year")
            datetime.date(year, month, 1) # Validate date construction
        except ValueError as e:
            messages.error(request, f"Invalid date specified: {e}. Showing current month.")
            today = timezone.now().date()
            year = today.year
            month = today.month

    # --- Assign target_date and date range AFTER validation ---
    try:
        target_date = datetime.date(year, month, 1)
        start_date = target_date
        if month == 12: end_date = datetime.date(year + 1, 1, 1)
        else: end_date = datetime.date(year, month + 1, 1)
    except ValueError: # Fallback if date construction failed unexpectedly
        messages.error(request, "Failed to construct date range. Showing current month.")
        today = timezone.now().date()
        year, month = today.year, today.month
        target_date = datetime.date(year, month, 1)
        start_date, end_date = target_date, (datetime.date(year + 1, 1, 1) if month == 12 else datetime.date(year, month + 1, 1))


    # --- Fetch Data ---
    try:
        sessions_in_month = WorkoutSession.objects.filter(
            user=request.user,
            date__gte=start_date,
            date__lt=end_date
        ).prefetch_related( # Use prefetch_related for efficiency
            'logs', 'logs__exercise'
        ).order_by('date')
        total_workout_days = sessions_in_month.count() # Get count efficiently
    except Exception as e:
        messages.error(request, f"Error fetching report data: {e}")
        sessions_in_month = WorkoutSession.objects.none()
        total_workout_days = 0

    # --- Prepare Context ---
    current_year = timezone.now().year
    available_years = range(current_year, current_year - 6, -1) # Last 5 years + current
    available_months = []
    # Ensure month range is valid if year is far in past/future
    try:
        available_months = [(m, datetime.date(year, m, 1).strftime('%B')) for m in range(1, 13)]
    except ValueError: # Handle case where 'year' might be invalid for creating dates
         available_months = [(m, datetime.date(current_year, m, 1).strftime('%B')) for m in range(1, 13)]


    context = {
        'report_year': year,
        'report_month': month,
        'report_month_name': target_date.strftime('%B'),
        'total_workout_days': total_workout_days,
        'sessions': sessions_in_month, # Pass the queryset with prefetched data
        'available_years': available_years,
        'available_months': available_months,
    }
    return render(request, 'workouts/monthly_report.html', context)


# --- Health Tools View ---
@login_required
def health_tools_view(request):
    """Displays various health calculation tools and information."""
    # This data is static for now, could be moved to models if needed
    ideal_weight_guide = [
        {'h_cm': 152, 'kg_low': 46, 'kg_high': 59}, {'h_cm': 155, 'kg_low': 48, 'kg_high': 61},
        {'h_cm': 157, 'kg_low': 49, 'kg_high': 63}, {'h_cm': 160, 'kg_low': 51, 'kg_high': 66},
        {'h_cm': 163, 'kg_low': 53, 'kg_high': 68}, {'h_cm': 165, 'kg_low': 54, 'kg_high': 70},
        {'h_cm': 168, 'kg_low': 56, 'kg_high': 73}, {'h_cm': 170, 'kg_low': 58, 'kg_high': 75},
        {'h_cm': 173, 'kg_low': 60, 'kg_high': 77}, {'h_cm': 175, 'kg_low': 61, 'kg_high': 80},
        {'h_cm': 178, 'kg_low': 63, 'kg_high': 82}, {'h_cm': 180, 'kg_low': 65, 'kg_high': 85},
        {'h_cm': 183, 'kg_low': 67, 'kg_high': 88}, {'h_cm': 185, 'kg_low': 69, 'kg_high': 90},
        {'h_cm': 188, 'kg_low': 71, 'kg_high': 93}, {'h_cm': 191, 'kg_low': 73, 'kg_high': 96},
    ]
    context = {'ideal_weight_guide': ideal_weight_guide}
    return render(request, 'workouts/health_tools.html', context)