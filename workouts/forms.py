# workouts/forms.py
from django import forms
from django.contrib.auth.forms import UserCreationForm, UsernameField
from django.contrib.auth.models import User
from django.forms.widgets import TextInput, EmailInput, PasswordInput
from .models import UserProfile, Exercise


class CustomUserCreationForm(UserCreationForm):
    # Override default fields to add placeholders
    username = forms.CharField(
        label="Username",
        widget=TextInput(attrs={'placeholder': 'Enter username', 'autocomplete': 'username'}),
        max_length=150,
        # This help text for username is generally safe to access and useful
        help_text=UserCreationForm.base_fields['username'].help_text
    )
    password = forms.CharField(
        label="Password",
        widget=PasswordInput(attrs={'placeholder': 'Enter password', 'autocomplete': 'new-password'}),
        strip=False
        # REMOVED help_text=... line here. Let validation errors handle requirements.
    )
    password2 = forms.CharField(
        label="Password confirmation",
        strip=False,
        widget=PasswordInput(attrs={'placeholder': 'Confirm password', 'autocomplete': 'new-password'}),
        help_text="Enter the same password as before, for verification.",  # This specific text is fine
    )

    # Add/Modify custom fields with placeholders
    first_name = forms.CharField(
        label="First name",
        max_length=150,
        widget=TextInput(attrs={'placeholder': 'Enter first name'})
    )
    last_name = forms.CharField(
        label="Last name",
        max_length=150,
        widget=TextInput(attrs={'placeholder': 'Enter last name'})
    )
    email = forms.EmailField(
        label="Email address",
        max_length=254,
        widget=EmailInput(attrs={'placeholder': 'Enter email address', 'autocomplete': 'email'})
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "first_name", "last_name", "email")

    # Keep the overridden save method exactly as before
    def save(self, commit=True):
        user = super().save(commit=False)
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
        return user


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ('timezone',)  # Only allow editing the timezone field for now
        # widgets = { # Optional: Use a better widget if desired
        #     'timezone': forms.Select(attrs={'class': 'form-select'})
        # }


# --- Form for Adding Custom Exercises ---
class CustomExerciseForm(forms.ModelForm):
    class Meta:
        model = Exercise
        # Only expose fields the user should fill
        fields = ['name', 'description']
        widgets = {  # Add placeholders and Bootstrap classes
            'name': forms.TextInput(attrs={'placeholder': 'Enter exercise name', 'class': 'form-control'}),
            'description': forms.Textarea(
                attrs={'placeholder': 'Optional: Describe the exercise or add notes', 'class': 'form-control',
                       'rows': 3}),
        }
        labels = {  # Customize labels if needed
            'name': 'Custom Exercise Name',
        }
