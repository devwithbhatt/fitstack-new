import os
import json
import logging
import sys
import requests

# Add project root to path
sys.path.append('c:\\Bhatt-projects\\GYM-project\\GYM')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'GYM.settings')
import django
django.setup()

from django.conf import settings

def list_all_content():
    account_sid = settings.TWILIO_ACCOUNT_SID
    auth_token = settings.TWILIO_AUTH_TOKEN
    
    url = f"https://content.twilio.com/v1/Content"
    response = requests.get(url, auth=(account_sid, auth_token))
    
    if response.status_code == 200:
        data = response.json()
        print("\n--- All Templates in this Account ---")
        for item in data.get('contents', []):
            print(f"\nSID: {item['sid']}")
            print(f"Name: {item['friendly_name']}")
            print(f"Language: {item['language']}")
            
            # Show the template body to see variables
            types = item.get('types', {})
            for type_name, type_data in types.items():
                body = type_data.get('body', '')
                print(f"Body: {body}")
                # Try to count {{1}}, {{2}}, etc.
                import re
                vars = re.findall(r'\{\{(\d+)\}\}', body)
                if vars:
                    print(f"Variables: {', '.join(sorted(set(vars), key=int))}")
    else:
        print(f"Failed to list content: {response.status_code}")

if __name__ == "__main__":
    list_all_content()
