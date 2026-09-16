import os
import django
import sys

# Setup Django environment
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'GYM.settings')
django.setup()

from apps.whatsapp.services import WhatsAppService
from apps.superadmin.models import Gym
from django.conf import settings

def test_expiry_msg(phone_number):
    print(f"🧪 Testing expiry message for: {phone_number}")
    
    # Get the first gym to use its details for the test
    gym = Gym.objects.first()
    if not gym:
        print("❌ No Gym found in database to pull details from.")
        return

    service = WhatsAppService()
    
    # Sample data based on your request
    result = service.send_membership_expired(
        request=None,
        to_number=phone_number,
        name="Test User",
        plan_name="1 Month Pro Plan",
        expiry_date="25/02/2026",
        gym_name=gym.name or "FitStack Gym",
        gym_contact_number=gym.phone or "6365587874",
        gym_logo_url=gym.logo.url if gym.logo else "https://fitstack.nextgenapplication.com/media/gym_logos/grok-image-aff2193b-48bc-42b3-8649-3cbe2762307f.jpg"
    )
    
    if result.get('success'):
        print(f"✅ Success! Message SID: {result.get('message_id')}")
    else:
        print(f"❌ Failed: {result.get('error')}")

if __name__ == "__main__":
    test_expiry_msg("6387343245")
