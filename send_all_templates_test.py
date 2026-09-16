import os
import sys
import django
from datetime import date, timedelta

# --- Django Setup ---
# Ensures the script can find and use the Django project settings.
# This is crucial for accessing the database and other Django components.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'GYM.settings')
# Add the project's root directory to Python's path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()
# --- End Django Setup ---

from apps.whatsapp.services import WhatsAppService

def run_whatsapp_test_suite(to_number):
    """
    Executes a comprehensive test of all major WhatsApp notification templates
    by calling the high-level functions in WhatsAppService.

    This approach is better than calling the Twilio API directly because it
    tests the actual code paths used by the application, ensuring that any
    logic inside the service functions (like URL formatting or error handling)
    is also validated.

    Args:
        to_number (str): The international format phone number to send test messages to.
                         Example: '91xxxxxxxxxx'
    """
    print("=" * 60)
    print(f"🚀 INITIATING WHATSAPP TEMPLATE TEST SUITE FOR: {to_number}")
    print("=" * 60)

    # Initialize the service, which contains all our sending logic
    service = WhatsAppService()
    
    # --- Common Test Data ---
    # This data is used across multiple template tests.
    test_data = {
        "name": "Aman",
        "gym_name": "FitStack Gym",
        "plan_name": "Gold Membership",
        "expiry_date": (date.today() + timedelta(days=30)).strftime('%d-%m-%Y'),
        "today_date": date.today().strftime('%d-%m-%Y'),
        "gym_contact": "6387343245",
        "logo_url": "https://fitstack.nextgenapplication.com/media/gym_logos/grok-image-aff2193b-48bc-42b3-8649-3cbe2762307f.jpg"
    }
    print(f"🧪 Using test data: {test_data['name']}, {test_data['gym_name']}")
    print("-" * 30)

    # --- Template Test Definitions ---
    # Each dictionary defines a test case:
    # - 'name': A descriptive name for the test.
    # - 'func': The actual WhatsAppService function to call.
    # - 'args': The arguments to pass to the function, sourced from our test_data.
    
    test_suite = [
        {
            "name": "🎂 Birthday Wishes",
            "func": service.send_birthday_wishes,
            "args": {
                "to_number": to_number,
                "name": test_data["name"],
                "gym_name": test_data["gym_name"]
            }
        },
        {
            "name": "⏳ Membership Expiring Soon",
            "func": service.send_membership_expiring_soon,
            "args": {
                "to_number": to_number,
                "name": test_data["name"],
                "plan_name": test_data["plan_name"],
                "expiry_date": test_data["expiry_date"],
                "gym_name": test_data["gym_name"],
                "gym_contact_number": test_data["gym_contact"],
                "gym_logo_url": test_data["logo_url"]
            }
        },
        {
            "name": "📅 Due Payment Follow-Up",
            "func": service.send_due_follow_up_reminder,
            "args": {
                "to_number": to_number,
                "name": test_data["name"],
                "plan_name": test_data["plan_name"],
                "total_amount": "2000",
                "last_payment_date": test_data["today_date"],
                "pending_due": "500",
                "gym_name": test_data["gym_name"],
                "gym_contact_number": test_data["gym_contact"],
                "gym_logo_url": test_data["logo_url"]
            }
        },
        {
            "name": "❌ Membership Expired",
            "func": service.send_membership_expired,
            "args": {
                "to_number": to_number,
                "name": test_data["name"],
                "plan_name": test_data["plan_name"],
                "expiry_date": test_data["today_date"],
                "gym_name": test_data["gym_name"],
                "gym_contact_number": test_data["gym_contact"],
                "gym_logo_url": test_data["logo_url"]
            }
        },
        {
            "name": "👋 Enquiry Confirmation",
            "func": service.send_enquiry_confirmation,
            "args": {
                "to_number": to_number,
                "name": test_data["name"],
                "gym_name": test_data["gym_name"],
                "gym_contact_number": test_data["gym_contact"],
                "gym_logo_url": test_data["logo_url"]
            }
        },
        {
            "name": "➕ New Membership Plan",
            "func": service.send_membership_plan_details,
            "args": {
                "to_number": to_number,
                "name": test_data["name"],
                "gym_name": test_data["gym_name"],
                "plan_name": test_data["plan_name"],
                "amount_paid": "1500",
                "balance": "500",
                "expiry_date": test_data["expiry_date"],
                "gym_contact_number": test_data["gym_contact"],
                "gym_logo_url": test_data["logo_url"]
            }
        },
        {
            "name": "💳 Due Payment Received",
            "func": service.send_due_payment_received,
            "args": {
                "to_number": to_number,
                "name": test_data["name"],
                "plan_name": test_data["plan_name"],
                "amount_received": "1000",
                "payment_date": test_data["today_date"],
                "due_balance": "0",
                "gym_name": test_data["gym_name"],
                "gym_contact_number": test_data["gym_contact"],
                "gym_logo_url": test_data["logo_url"]
            }
        }
    ]

    # --- Execute Test Suite ---
    # Loop through each test case and execute the function with its arguments.
    for test in test_suite:
        print(f"📤 Sending: {test['name']}...")
        
        # The 'request' argument is not needed for this test script, so we pass None.
        test['args']['request'] = None
        
        # Dynamically call the function
        result = test['func'](**test['args'])
        
        # Report the result
        if result.get('success'):
            print(f"✅ Success! Message SID: {result.get('message_id')}")
        else:
            print(f"❌ Failed! Reason: {result.get('error')}")
        print("-" * 30)

    print("=" * 60)
    print("🎉 WHATSAPP TEST SUITE COMPLETE 🎉")
    print("=" * 60)

if __name__ == "__main__":
    # IMPORTANT: Replace with the phone number you want to send the test messages to.
    # The number must be in international format, e.g., '91xxxxxxxxxx' for India.
    target_number = "6387343245"
    run_whatsapp_test_suite(target_number)