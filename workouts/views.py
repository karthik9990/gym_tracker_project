# workouts/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Exercise, WorkoutSession, WorkoutLog
from django.utils import timezone
import datetime
from django.urls import reverse


# CART_SESSION_KEY = 'workout_cart' # Define a constant key

@login_required  # Ensures only logged-in users can access
def log_workout_view(request):
    available_exercises = Exercise.objects.all().order_by('name')
    today_str = timezone.now().strftime('%Y-%m-%d')  # Get today's date as string

    # --- Handle adding an item to the cart (POST request) ---
    if request.method == 'POST':
        try:
            exercise_id = request.POST.get('exercise')
            sets = request.POST.get('sets')
            reps = request.POST.get('reps')
            weight = request.POST.get('weight')
            # Add duration, notes later if needed

            if not exercise_id:
                raise ValueError("Exercise must be selected.")  # Basic validation

            exercise = get_object_or_404(Exercise, pk=exercise_id)

            # Get or initialize the cart from the session
            cart = request.session.get('workout_cart', {})
            if today_str not in cart:
                cart[today_str] = []  # Initialize list for today if not present

            # Prepare item data (store IDs and values)
            item_data = {
                'exercise_id': exercise.id,
                'exercise_name': exercise.name,  # Store name for easy display
                'sets': sets if sets else None,  # Store None if empty
                'reps': reps if reps else None,
                'weight': weight if weight else None,
                # Add duration, notes here
            }
            cart[today_str].append(item_data)

            # Save the updated cart back to the session
            request.session['workout_cart'] = cart
            request.session.modified = True  # Important: mark session as modified

            # Redirect back to the same page after POST to avoid resubmission
            return redirect('workouts:log_workout')

        except (ValueError, Exercise.DoesNotExist) as e:
            # Handle errors (e.g., show a message - using Django messages framework is ideal)
            print(f"Error adding item: {e}")  # Simple print for now
            # Fall through to render the page again (GET logic) with potential error message

    # --- Display the form and current cart (GET request or after failed POST) ---
    cart = request.session.get('workout_cart', {})
    cart_items_today = cart.get(today_str, [])  # Get items specifically for today

    context = {
        'available_exercises': available_exercises,
        'cart_items': cart_items_today,
        'view_date': timezone.now().date(),  # Pass today's date object
        'view_date_str': today_str,
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
    if request.method != 'POST':
        return redirect('workouts:dashboard')  # Redirect if not POST

    # --- Get the date to save from the hidden form input ---
    date_to_save_str = request.POST.get('date_to_save')

    if not date_to_save_str:
        # Handle case where date is missing from form
        print("Error: Date to save is missing from the form.")
        # Maybe redirect back with an error message?
        return redirect(request.META.get('HTTP_REFERER', 'workouts:dashboard'))  # Go back

    # --- Validate and parse the date ---
    try:
        session_date = datetime.datetime.strptime(date_to_save_str, '%Y-%m-%d').date()
    except ValueError:
        print(f"Error: Invalid date format received for saving: {date_to_save_str}")
        # Redirect back with error?
        return redirect(request.META.get('HTTP_REFERER', 'workouts:dashboard'))

    # --- Retrieve cart items for the specific date ---
    cart = request.session.get('workout_cart', {})
    cart_items_for_date = cart.get(date_to_save_str, [])  # Use date_to_save_str key

    if not cart_items_for_date:
        print(f"Cart is empty for {date_to_save_str}, nothing to save.")
        # Redirect back, maybe with a message
        return redirect('workouts:log_workout_date', date_str=date_to_save_str)

    try:
        # Get or create the WorkoutSession for the user and the SPECIFIC date
        workout_session, created = WorkoutSession.objects.get_or_create(
            user=request.user,
            date=session_date,  # Use the parsed session_date
            defaults={'notes': ''}  # Optional: provide default values if creating
        )

        # Loop through items in the cart for the specific date and create Logs
        for item in cart_items_for_date:
            try:
                exercise = Exercise.objects.get(pk=item['exercise_id'])
                WorkoutLog.objects.create(
                    session=workout_session,
                    exercise=exercise,
                    sets=item.get('sets'),
                    reps=item.get('reps'),
                    weight=item.get('weight'),
                )
            except Exercise.DoesNotExist:
                print(f"Skipping item - Exercise ID {item['exercise_id']} not found.")
                continue

        # --- Clear the specific date's items from the cart ---
        if date_to_save_str in request.session.get('workout_cart', {}):
            del request.session['workout_cart'][date_to_save_str]
            request.session.modified = True
        else:
            # This case shouldn't ideally happen if cart_items_for_date was found
            print(f"Warning: Tried to clear cart for {date_to_save_str}, but key wasn't found.")

        print(f"Workout for {date_to_save_str} saved successfully!")
        # Add success message later
        return redirect('workouts:dashboard')  # Redirect to dashboard after save

    except Exception as e:
        print(f"Error saving workout for {date_to_save_str}: {e}")
        # Add error message later
        # Redirect back to the specific date's log page on error
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
