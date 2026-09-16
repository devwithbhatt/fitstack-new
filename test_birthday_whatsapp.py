import os
import django
import sys

# Setup Django environment
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'GYM.settings')
django.setup()

from apps.whatsapp.services import WhatsAppService
from apps.superadmin.models import Gym

def test_birthday_wish_msg(phone_number):
    print(f"🧪 Testing birthday wishes message for: {phone_number}")
    
    gym = Gym.objects.first()
    if not gym:
        print("❌ No Gym found in database.")
        return

    service = WhatsAppService()
    
    # Mapping: 1:name, 2:gym_name, 3:contact, 4:logo
    result = service.send_birthday_wishes(
        request=None,
        to_number=phone_number,
        name="Aman",
        gym_name=gym.name or "FitStack Gym",
        gym_contact_number=gym.phone or "6656565656",
        gym_logo_url=gym.logo.url if gym.logo else "https://fitstack.nextgenapplication.com/media/gym_logos/grok-image-aff2193b-48bc-42b3-8649-3cbe2762307f.jpg"
    )
    
    if result.get('success'):
        print(f"✅ Success! Message SID: {result.get('message_id')}")
    else:
        print(f"❌ Failed: {result.get('error')}")

if __name__ == "__main__":
    test_birthday_wish_msg("6387343245")
