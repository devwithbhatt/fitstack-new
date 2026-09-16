"""
Quick test script to send a due_payment_follow_up_date WhatsApp message
to 6387343245 for verification.

Run from: c:\Bhatt-projects\GYM-project\GYM\
Command:   python test_followup_whatsapp.py
"""

import os
import sys
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'GYM.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from apps.whatsapp.services import WhatsAppService
from datetime import date, timedelta

# ── Test configuration ──────────────────────────────────────────────────
TEST_PHONE    = "6387343245"
TEST_NAME     = "Test Member"
TEST_FOLLOWUP = (date.today() + timedelta(days=3)).strftime('%d-%m-%Y')  # 3 days from now
TEST_DUE      = "1500"
TEST_GYM      = "FitStack Gym"
TEST_CONTACT  = "6387343245"
# ────────────────────────────────────────────────────────────────────────

print("=" * 60)
print("  WhatsApp Due Follow-Up Reminder — Test")
print("=" * 60)
print(f"  To         : {TEST_PHONE}")
print(f"  Name       : {TEST_NAME}")
print(f"  Follow-Up  : {TEST_FOLLOWUP}")
print(f"  Total Due  : ₹{TEST_DUE}")
print(f"  Gym        : {TEST_GYM}")
print("=" * 60)

service = WhatsAppService(gym_id=None)

result = service.send_due_follow_up_reminder(
    request=None,
    to_number=TEST_PHONE,
    name=TEST_NAME,
    follow_up_date=TEST_FOLLOWUP,
    total_due=TEST_DUE,
    gym_name=TEST_GYM,
    gym_contact_number=TEST_CONTACT,
    gym_logo_url=None
)

print()
if result.get('success'):
    print(f"✅ Message sent successfully!")
    print(f"   Message SID : {result.get('message_id')}")
    print(f"   Status      : {result.get('status')}")
else:
    print(f"❌ Failed to send message.")
    print(f"   Error       : {result.get('error')}")
    if result.get('code'):
        print(f"   Twilio Code : {result.get('code')}")

print("=" * 60)
