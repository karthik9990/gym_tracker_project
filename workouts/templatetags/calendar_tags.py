# workouts/templatetags/calendar_tags.py

from django import template

register = template.Library()

@register.filter(name='get_item')
def get_item(dictionary, key):
    """
    Allows accessing dictionary value using a variable key in templates.
    Usage: {{ my_dictionary|get_item:my_key_variable }}
    Returns None if key doesn't exist.
    """
    if hasattr(dictionary, 'get'): # Check if it's dictionary-like
        return dictionary.get(key)
    return None