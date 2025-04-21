# workouts/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Exercise, WorkoutSession, WorkoutLog
from django.utils import timezone
from django.urls import reverse  # To generate URLs


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
def save_workout_view(request):
    if request.method != 'POST':
        # Only allow POST requests to save
        return redirect('workouts:log_workout')  # Or show an error

    today_str = timezone.now().strftime('%Y-%m-%d')
    cart = request.session.get('workout_cart', {})
    cart_items_today = cart.get(today_str, [])

    if not cart_items_today:
        # No items to save, maybe redirect back with a message
        print("Cart is empty, nothing to save.")
        return redirect('workouts:log_workout')

    try:
        # Get or create the WorkoutSession for the user and today's date
        session_date = timezone.now().date()
        workout_session, created = WorkoutSession.objects.get_or_create(
            user=request.user,
            date=session_date,
            # You could add defaults or update notes here if needed
            # defaults={'notes': 'Auto-created session'}
        )

        # Loop through items in the cart for today and create WorkoutLog entries
        for item in cart_items_today:
            try:
                exercise = Exercise.objects.get(pk=item['exercise_id'])
                WorkoutLog.objects.create(
                    session=workout_session,
                    exercise=exercise,
                    sets=item.get('sets'),  # Use .get() for safety if key might be missing
                    reps=item.get('reps'),
                    weight=item.get('weight'),
                    # Add duration, notes if they exist in item
                )
            except Exercise.DoesNotExist:
                print(f"Skipping item - Exercise with ID {item['exercise_id']} not found.")
                continue  # Skip this item if exercise doesn't exist

        # Clear today's items from the cart in the session
        del request.session['workout_cart'][today_str]
        request.session.modified = True

        # Redirect to a success page or dashboard (dashboard doesn't exist yet)
        print("Workout saved successfully!")
        # Add a success message using Django messages framework later
        return redirect('workouts:log_workout')  # Redirect back to log page for now

    except Exception as e:
        # Handle potential errors during save
        print(f"Error saving workout: {e}")
        # Add error message using Django messages framework later
        return redirect('workouts:log_workout')  # Redirect back

# Add dashboard_view later
