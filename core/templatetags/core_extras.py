from django import template

register = template.Library()


@register.filter(name="get_item")
def get_item(value, key):
    """Return a dict/list item by key safely in templates.

    Usage: {{ mydict|get_item:key }}
    """
    try:
        if value is None:
            return ""
        # dict-like
        if hasattr(value, "get"):
            return value.get(key, "")
        # list/sequence or mapping access
        return value[key]
    except Exception:
        return ""


@register.filter(name="exists")
def exists(value):
    """Return True if a queryset or iterable has any items.

    Usage: {% if some_queryset|exists %}
    """
    try:
        if value is None:
            return False
        if hasattr(value, "exists"):
            return value.exists()
        # fall back to bool/len check
        return bool(value)
    except Exception:
        return False


@register.filter(name="has_active_optimization")
def has_active_optimization(job):
    """Return True if the job has any active optimization runs."""
    try:
        return job.optimization_runs.filter(is_active=True).exists()
    except Exception:
        return False
