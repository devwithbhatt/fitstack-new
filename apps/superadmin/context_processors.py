from .models import Gym

def gym_details(request):
    gym = getattr(request, 'gym', None)
    return {'gym': gym}