# workouts/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Exercise, WorkoutSession, WorkoutLog
from django.utils import timezone
import datetime
from django.urls import reverse
from django.contrib import messages


# CART_SESSION_KEY = 'workout_cart' # Define a constant key

@login_required
def log_workout_view(request, date_str):
    available_exercises = Exercise.objects.all().order_by('name')
    today = timezone.now().date()  # Get today's date

    try:
        view_date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
        # --- !!! SERVER-SIDE VALIDATION !!! ---
        if view_date > today:
            messages.error(request, "You cannot log workouts for future dates.")
            return redirect('workouts:log_workout_today')  # Redirect to today
        # --- End Validation ---
    except ValueError:
        messages.error(request, "Invalid date format provided.")
        return redirect('workouts:log_workout_today')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'add_item':
            # --- Add item logic (check view_date > today again just in case?) ---
            # Although technically covered by the initial check, belt-and-suspenders doesn't hurt
            if view_date > today:
                messages.error(request, "Cannot add items for a future date.")
                return redirect('workouts:log_workout_today')

            # ... (rest of add item logic as before) ...
            try:
                # ... (inside try block) ...
                return redirect('workouts:log_workout_date', date_str=date_str)
            except (ValueError, Exercise.DoesNotExist) as e:
                messages.error(request, f"Error adding item: {e}")
                # Fall through to render the page again (GET logic)

        elif action == 'change_date':
            new_date_str = request.POST.get('selected_date')
            if new_date_str:
                try:
                    new_date = datetime.datetime.strptime(new_date_str, '%Y-%m-%d').date()
                    # --- !!! VALIDATE NEW DATE BEFORE REDIRECT !!! ---
                    if new_date > today:
                        messages.error(request, "You cannot select a future date.")
                        # Redirect back to the *current* valid date page
                        return redirect('workouts:log_workout_date', date_str=date_str)
                    # --- End Validation ---
                    # Redirect to the log page for the newly selected valid date
                    return redirect('workouts:log_workout_date', date_str=new_date_str)
                except ValueError:
                    messages.error(request, f"Invalid date selected: {new_date_str}")
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
    }
    return render(request, 'workouts/log_workout.html', context)


@login_required
def log_workout_today_redirect_view(request):
    """Redirects to the log view for today's date."""
    today_str = timezone.now().strftime('%Y-%m-%d')
    # Use reverse to build the URL dynamically based on the URL name
    return redirect(reverse('workouts:log_workout_date', kwargs={'date_str': today_str}))


# --- Update log_workout_view ---
@login_required
def log_workout_view(request, date_str):  # Now accepts date_str
    """Handles logging workouts for a specific date."""
    available_exercises = Exercise.objects.all().order_by('name')

    # --- Validate and parse the date string ---
    try:
        # Convert the date string from the URL into a date object
        view_date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        # Handle invalid date format in URL - redirect to today's log perhaps?
        print(f"Invalid date format in URL: {date_str}")
        return redirect('workouts:log_workout_today')  # Redirect to today's log

    # --- Handle adding an item to the cart (POST request) ---
    if request.method == 'POST' and request.POST.get('action') == 'add_item':
        try:
            # Ensure the item is added to the correct date's cart
            post_date_str = request.POST.get('date')  # Get date from hidden input
            if post_date_str != date_str:
                # If hidden date doesn't match URL date, something is wrong
                print("Warning: Form date mismatch with URL date.")
                # Decide how to handle: error, use URL date, use form date?
                # For simplicity, we'll trust the URL date for cart key
                # but this indicates a potential form issue.

            exercise_id = request.POST.get('exercise')
            # ... (rest of the field retrieval: sets, reps, weight) ...
            sets = request.POST.get('sets')
            reps = request.POST.get('reps')
            weight = request.POST.get('weight')

            if not exercise_id:
                raise ValueError("Exercise must be selected.")

            exercise = get_object_or_404(Exercise, pk=exercise_id)
            cart = request.session.get('workout_cart', {})

            # Use the date_str from the URL as the key in the cart
            if date_str not in cart:
                cart[date_str] = []

            item_data = {
                'exercise_id': exercise.id,
                'exercise_name': exercise.name,
                'sets': sets if sets else None,
                'reps': reps if reps else None,
                'weight': weight if weight else None,
            }
            cart[date_str].append(item_data)

            request.session['workout_cart'] = cart
            request.session.modified = True

            # Redirect back to the same date-specific URL
            return redirect('workouts:log_workout_date', date_str=date_str)

        except (ValueError, Exercise.DoesNotExist) as e:
            print(f"Error adding item: {e}")
            # Fall through to render the page again (GET logic)

    # --- Handle changing the date via the date input (POST request) ---
    elif request.method == 'POST' and request.POST.get('action') == 'change_date':
        new_date_str = request.POST.get('selected_date')
        if new_date_str:
            # Validate the new date string format if desired
            try:
                datetime.datetime.strptime(new_date_str, '%Y-%m-%d')
                # Redirect to the log page for the newly selected date
                return redirect('workouts:log_workout_date', date_str=new_date_str)
            except ValueError:
                print(f"Invalid date selected: {new_date_str}")
                # Optionally add Django message error
        # If date is invalid or missing, just reload the current page
        return redirect('workouts:log_workout_date', date_str=date_str)

    # --- Display the form and current cart (GET request or after failed POST) ---
    cart = request.session.get('workout_cart', {})
    # Get items specifically for the date from the URL
    cart_items_for_date = cart.get(date_str, [])

    context = {
        'available_exercises': available_exercises,
        'cart_items': cart_items_for_date,
        'view_date': view_date,  # Pass the date object
        'view_date_str': date_str,  # Pass the date string
    }
    return render(request, 'workouts/log_workout.html', context)


@login_required
def save_workout_view(request):
    # ... (initial POST check) ...
    date_to_save_str = request.POST.get('date_to_save')
    today = timezone.now().date()  # Get today's date

    if not date_to_save_str:
        messages.error(request, "Date missing from save request.")
        return redirect(request.META.get('HTTP_REFERER', 'workouts:dashboard'))

    try:
        session_date = datetime.datetime.strptime(date_to_save_str, '%Y-%m-%d').date()
        # --- !!! SERVER-SIDE VALIDATION BEFORE SAVING !!! ---
        if session_date > today:
            messages.error(request, "Cannot save workout sessions for future dates.")
            # Redirect back to the log page for that date (which should also fail/redirect)
            # Or redirect to dashboard
            return redirect('workouts:log_workout_date', date_str=date_to_save_str)
        # --- End Validation ---
    except ValueError:
        messages.error(request, f"Invalid date format received for saving: {date_to_save_str}")
        return redirect(request.META.get('HTTP_REFERER', 'workouts:dashboard'))

    # ... (rest of the save logic: retrieve cart, get_or_create session, create logs, clear cart) ...
    cart = request.session.get('workout_cart', {})
    cart_items_for_date = cart.get(date_to_save_str, [])

    if not cart_items_for_date:
        messages.warning(request, f"Workout for {date_to_save_str} was empty, nothing saved.")
        return redirect('workouts:log_workout_date', date_str=date_to_save_str)

    try:
        # ... (get_or_create WorkoutSession using validated session_date) ...
        workout_session, created = WorkoutSession.objects.get_or_create(
            user=request.user,
            date=session_date,
            defaults={'notes': ''}
        )
        # ... (loop through items and create WorkoutLog) ...
        for item in cart_items_for_date:
            # ... (create log logic) ...
            pass  # Replace pass with actual creation logic

        # ... (clear specific date's items from cart) ...
        if date_to_save_str in request.session.get('workout_cart', {}):
            del request.session['workout_cart'][date_to_save_str]
            request.session.modified = True

        messages.success(request, f"Workout for {session_date.strftime('%B %d, %Y')} saved successfully!")
        return redirect('workouts:dashboard')

    except Exception as e:
        messages.error(request, f"Error saving workout for {date_to_save_str}: {e}")
        return redirect('workouts:log_workout_date', date_str=date_to_save_str)


@login_required
def dashboard_view(request):
    # Fetch all workout sessions for the currently logged-in user
    # Order them by date, most recent first (defined in model's Meta)
    user_sessions = WorkoutSession.objects.filter(user=request.user)

    context = {
        'workout_sessions': user_sessions,
    }
    return render(request, 'workouts/dashboard.html', context)


@login_required
def workout_detail_view(request, session_id):
    # Fetch the specific WorkoutSession by its ID
    # Also ensure the session belongs to the current user for security
    workout_session = get_object_or_404(WorkoutSession, pk=session_id, user=request.user)

    # Fetch the related WorkoutLog entries using the related_name='logs'
    # defined in the WorkoutLog model's ForeignKey.
    # They are automatically ordered if specified in WorkoutLog's Meta,
    # otherwise, you can add .order_by('id') or similar here.
    session_logs = workout_session.logs.all()

    context = {
        'session': workout_session,
        'logs': session_logs,
    }
    return render(request, 'workouts/workout_detail.html', context)


def home_view(request):
    # If user is logged in, redirect them to their dashboard
    if request.user.is_authenticated:
        return redirect('workouts:dashboard')
    # Otherwise, show a simple welcome/login page
    return render(request, 'workouts/home.html')  # Or 'home.html' if you create a root template dir
# We'll add workout_detail_view later
