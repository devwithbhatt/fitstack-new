from .models import Gym
from .notifications import get_unread_notifications_count, get_recent_notifications

def gym_details(request):
    gym = getattr(request, 'gym', None)
    context = {'gym': gym}
    if hasattr(request, 'user') and request.user.is_authenticated:
        try:
            context['unread_notifications_count'] = get_unread_notifications_count(request.user)
            context['recent_notifications'] = get_recent_notifications(request.user, limit=5)
        except Exception:
            context['unread_notifications_count'] = 0
            context['recent_notifications'] = []
    else:
        context['unread_notifications_count'] = 0
        context['recent_notifications'] = []
    return context