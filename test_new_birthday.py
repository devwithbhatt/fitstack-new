
import os
import sys
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'GYM.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from apps.whatsapp.services import WhatsAppService

def test_new_birthday_template(to_number):
    print(f"🚀 Testing NEW birthday template for: {to_number}")
    service = WhatsAppService()
    
    # Sid: HX0311a3e1b155aa9f1781951a71ee1b98
    # Variables: 1:name, 2:gym_name
    result = service.send_birthday_wishes(
        request=None,
        to_number=to_number,
        name="Aman (New Template)",
        gym_name="FitStack Gym"
    )
    
    print()
    if result.get('success'):
        print(f"✅ Success! Message SID: {result.get('message_id')}")
    else:
        print(f"❌ Failed: {result.get('error')}")

if __name__ == "__main__":
    test_new_birthday_template("6387343245")
