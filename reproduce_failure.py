import os
import json
import logging
import sys

# Add project root to path
sys.path.append('c:\\Bhatt-projects\\GYM-project\\GYM')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'GYM.settings')
import django
django.setup()

from apps.whatsapp.twilio_service import TwilioWhatsAppService

logging.basicConfig(level=logging.DEBUG)

def test_service():
    service = TwilioWhatsAppService(gym_id=1)
    
    # Using the EXACT strings from the user's failure log
    to_number = '6387343245'
    name = 'Aman Katiyar'
    gym_name = 'Aman Fitness'
    gym_contact = '6387343245'
    logo_url = 'https://fitstack.nextgenapplication.com/media/gym_logos/grok-image-aff2193b-48bc-42b3-8649-3cbe2762307f.jpg'
    
    print("\n--- Reproducing User Failure via Script ---")
    result = service.send_enquiry_confirmation(
        to_number=to_number,
        name=name,
        gym_name=gym_name,
        gym_contact_number=gym_contact,
        logo_url=logo_url
    )
    
    print(f"\nResult: {json.dumps(result, indent=2)}")

if __name__ == "__main__":
    test_service()
