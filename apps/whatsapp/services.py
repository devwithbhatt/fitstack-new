# apps/whatsapp/services.py
from django.conf import settings
import requests
import logging
import json

logger = logging.getLogger(__name__)

def is_media_url_valid(url, timeout=5):
    """
    Performs a quick check to see if a URL is accessible and returns a valid image.
    Enhanced with better error handling and logging.

    Args:
        url (str): The URL to check.
        timeout (int): How many seconds to wait for the server to respond.

    Returns:
        bool: True if the URL points to a valid image, False otherwise.
    """
    if not url:
        logger.info("No media URL provided. Skipping validation.")
        return False
    
    try:
        logger.info(f"Validating media URL: {url}")
        
        # Check if URL is HTTPS (Twilio requirement)
        if not url.lower().startswith('https://'):
            logger.warning(f"URL validation failed: URL must be HTTPS - {url}")
            return False
            
        response = requests.head(url, timeout=timeout, allow_redirects=True)
        response.raise_for_status()

        content_type = response.headers.get('Content-Type', '').lower()
        content_length = int(response.headers.get('Content-Length', 0))

        # Check if it's an image or supported media type
        supported_types = ['image/', 'video/', 'application/pdf', 'audio/']
        if not any(media_type in content_type for media_type in supported_types):
            logger.warning(f"URL validation failed: Content-Type '{content_type}' is not supported.")
            return False
        
        # Check file size (5MB for images, larger for other media)
        if 'image/' in content_type and content_length > 5 * 1024 * 1024:
            logger.warning(f"URL validation failed: Image size ({content_length} bytes) exceeds 5MB limit.")
            return False
        elif content_length > 100 * 1024 * 1024:  # 100MB limit for other media
            logger.warning(f"URL validation failed: File size ({content_length} bytes) exceeds 100MB limit.")
            return False

        logger.info(f"Media URL validation successful: {content_type}, {content_length} bytes")
        return True

    except requests.exceptions.Timeout:
        logger.error(f"URL validation failed: Request timed out for {url}.")
        return False
    except requests.exceptions.RequestException as e:
        logger.error(f"URL validation failed: Could not access {url}. Error: {e}")
        return False
    except Exception as e:
        logger.error(f"URL validation failed: Unexpected error for {url}: {e}")
        return False


from .twilio_service import TwilioWhatsAppService

class WhatsAppService:
    """
    A service for sending WhatsApp messages via the Twilio API.
    Refactored to replace the previous Meta API implementation.
    Updated with better media URL handling and template support.
    """
    
    def __init__(self, gym_id=None):
        """
        Initializes the service with Twilio settings.
        gym_id is provided for future multi-tenant support.
        """
        self.twilio = TwilioWhatsAppService(gym_id=gym_id)
        self.gym_id = gym_id
        logger.info(f"🔧 WhatsApp Service Initialized with Twilio backend for gym: {gym_id}")
    
    def _get_absolute_media_url(self, request, media_url):
        """
        Ensures the media URL is a public absolute URL that Twilio can reach.
        Prioritizes settings.BASE_URL over request.build_absolute_uri to avoid localhost issues.
        Also ensures URL is HTTPS (required by Twilio).

        Args:
            request: Django request object (optional)
            media_url (str): Relative or absolute URL

        Returns:
            str: Absolute HTTPS URL or None
        """
        if not media_url:
            return None
            
        # If it's already an absolute URL
        if media_url.startswith(('http://', 'https://')):
            # Check if it's localhost (development)
            if any(local in media_url for local in ['127.0.0.1', 'localhost', '0.0.0.0']):
                base_url = getattr(settings, 'BASE_URL', '').rstrip('/')
                if base_url:
                    # Ensure base_url is HTTPS
                    if not base_url.startswith('https://'):
                        base_url = base_url.replace('http://', 'https://')
                    
                    # Extract the path and rebuild with base_url
                    path_parts = media_url.split('/media/', 1)
                    if len(path_parts) > 1:
                        result = f"{base_url}/media/{path_parts[1]}"
                        logger.debug(f"🖼️ Converted localhost URL to production: {result}")
                        return result
                    else:
                        # Try to extract any path
                        from urllib.parse import urlparse
                        parsed = urlparse(media_url)
                        if parsed.path:
                            result = f"{base_url}{parsed.path}"
                            logger.debug(f"🖼️ Converted localhost URL to production: {result}")
                            return result
            
            # Ensure URL is HTTPS (Twilio requirement)
            if media_url.startswith('http://'):
                media_url = media_url.replace('http://', 'https://', 1)
                logger.debug(f"🖼️ Converted HTTP to HTTPS: {media_url}")
            
            return media_url

        # It's a relative path (e.g., /media/gym_logos/...)
        base_url = getattr(settings, 'BASE_URL', '').rstrip('/')
        if base_url:
            # Ensure base_url is HTTPS
            if not base_url.startswith('https://'):
                base_url = base_url.replace('http://', 'https://')
            result = f"{base_url}{media_url}"
            logger.debug(f"🖼️ Built absolute URL from base: {result}")
            return result
        
        # Fallback to request if available
        if request:
            absolute_uri = request.build_absolute_uri(media_url)
            # Ensure HTTPS
            if absolute_uri.startswith('http://'):
                absolute_uri = absolute_uri.replace('http://', 'https://', 1)
            logger.debug(f"🖼️ Built absolute URL from request: {absolute_uri}")
            return absolute_uri
            
        return media_url

    def _format_phone_number(self, phone_number):
        """Format phone number using Twilio service"""
        return self.twilio.format_phone_number(phone_number)
    
    def check_template_status(self, content_sid):
        """Check if a template is approved"""
        return self.twilio.check_template_status(content_sid)
    
    def send_template_message(self, to_number, template_name, lang_code='en', components=None):
        """
        Sends a template message via Twilio.
        Maps Meta-style component data to Twilio numbering if possible.
        
        Args:
            to_number (str): Recipient phone number
            template_name (str): Name of the template (used for logging)
            lang_code (str): Language code
            components (list): Meta-style components array
            
        Returns:
            dict: Response from Twilio
        """
        content_sid = getattr(settings, 'TWILIO_CONTENT_SID', None)
        
        if not content_sid:
            logger.error("❌ TWILIO_CONTENT_SID not configured in settings")
            return {'success': False, 'error': 'Template SID not configured'}
        
        variables = {}
        if components:
            idx = 1
            for component in components:
                for param in component.get('parameters', []):
                    variables[str(idx)] = param.get('text', '')
                    idx += 1
        
        logger.info(f"📨 Sending template '{template_name}' to {to_number}")
        
        return self.twilio.send_template_message(
            to_number=to_number,
            content_sid=content_sid,
            content_variables=variables if variables else None,
            lang_code=lang_code
        )

    def send_message(self, to_number, message):
        """
        Sends a plain text message.
        
        Args:
            to_number (str): Recipient phone number
            message (str): Text message to send
            
        Returns:
            dict: Response from Twilio
        """
        if not self.twilio.client:
            logger.error("❌ Twilio client not initialized")
            return {'success': False, 'error': 'Twilio client not initialized'}

        to_formatted = self.twilio.format_phone_number(to_number)
        try:
            msg = self.twilio.client.messages.create(
                from_=self.twilio.from_number,
                to=to_formatted,
                body=message
            )
            logger.info(f"✅ Direct message sent: {msg.sid}")
            return {'success': True, 'message_id': msg.sid}
        except Exception as e:
            logger.error(f"❌ Error sending direct message: {e}")
            return {'success': False, 'error': str(e)}

    def send_enquiry_confirmation(self, request, to_number, name, gym_name, gym_contact_number, gym_logo_url=None):
        """
        Twilio-optimized enquiry confirmation with logo support.
        
        Args:
            request: Django request object
            to_number (str): Recipient phone number
            name (str): Customer name
            gym_name (str): Gym name
            gym_contact_number (str): Gym contact number
            gym_logo_url (str): URL for gym logo (optional)
            
        Returns:
            dict: Response from Twilio
        """
        full_logo_url = self._get_absolute_media_url(request, gym_logo_url)
        if full_logo_url:
            logger.debug(f"🖼️ Using public logo URL for Twilio: {full_logo_url}")
            
        return self.twilio.send_enquiry_confirmation(
            to_number=to_number, 
            name=name,
            gym_name=gym_name,
            gym_contact_number=gym_contact_number,
            logo_url=full_logo_url
        )

    def send_membership_plan_details(self, request, to_number, name, gym_name, plan_name, amount_paid, balance, expiry_date, gym_contact_number, gym_logo_url=None):
        """
        Maps existing membership details call to Twilio with the new membership_assign template.
        
        Args:
            request: Django request object
            to_number (str): Recipient phone number
            name (str): Customer name
            gym_name (str): Gym name
            plan_name (str): Plan name
            amount_paid (str): Amount paid
            balance (str): Remaining balance
            expiry_date (str): Expiry date
            gym_contact_number (str): Gym contact number
            gym_logo_url (str): URL for gym logo (optional)
            
        Returns:
            dict: Response from Twilio
        """
        # Check if template SID is configured
        membership_sid = getattr(settings, 'TWILIO_MEMBERSHIP_ASSIGN_SID', None)
        
        if not membership_sid:
            logger.error("❌ TWILIO_MEMBERSHIP_ASSIGN_SID not configured in settings")
            return {'success': False, 'error': 'Membership template SID not configured'}
        
        full_logo_url = self._get_absolute_media_url(request, gym_logo_url)
        if full_logo_url:
            logger.debug(f"🖼️ Using public logo URL for Twilio: {full_logo_url}")

        # Variables mapped according to template SID: HXa12b082cd79a07c21cecf76fb1edf2d5
        # 1:name, 2:gym_name, 3:plan_name, 4:amount_paid, 5:due_balance, 6:expiry_date, 7:gym_number, 8:logo_url
        variables = {
            "1": name,
            "2": gym_name,
            "3": plan_name,
            "4": str(amount_paid),
            "5": str(balance),
            "6": str(expiry_date),
            "7": str(gym_contact_number),
            "8": full_logo_url or ""
        }
        
        logger.info(f"📨 Sending membership plan details to {to_number} for {name}")
        
        return self.twilio.send_template_message(
            to_number=to_number,
            content_sid=membership_sid,
            content_variables=variables,
            media_url=full_logo_url
        )

    def send_due_payment_received(self, request, to_number, name, amount_received, payment_date, due_balance, gym_name, plan_name="Plan", gym_contact_number=None, gym_logo_url=None):
        """
        Maps existing payment received call to Twilio with 8-variable structure.
        
        Args:
            request: Django request object
            to_number (str): Recipient phone number
            name (str): Customer name
            amount_received (str): Amount received
            payment_date (str): Payment date
            due_balance (str): Remaining due balance
            gym_name (str): Gym name
            plan_name (str): Plan/Trainer name
            gym_contact_number (str): Gym contact number
            gym_logo_url (str): URL for gym logo (optional)
            
        Returns:
            dict: Response from Twilio
        """
        payment_sid = getattr(settings, 'TWILIO_DUE_PAYMENT_SID', None)
        
        if not payment_sid:
            # Fallback to general content sid if specific one missing
            payment_sid = getattr(settings, 'TWILIO_CONTENT_SID', None)

        if not payment_sid:
            logger.error("❌ No payment template SID configured")
            return {'success': False, 'error': 'Payment template SID not configured'}

        full_logo_url = self._get_absolute_media_url(request, gym_logo_url)
        if full_logo_url:
            logger.debug(f"🖼️ Using public logo URL for Twilio: {full_logo_url}")

        # Variables for SID: HX2647f92add9b39226998795a977a5da6
        # 1:Name, 2:Plan, 3:Amount, 4:Date, 5:Balance, 6:Gym, 7:Contact, 8:Logo
        variables = {
            "1": name,
            "2": plan_name,
            "3": str(amount_received),
            "4": str(payment_date),
            "5": str(due_balance),
            "6": gym_name,
            "7": str(gym_contact_number) if gym_contact_number else "N/A",
            "8": full_logo_url or ""
        }
        
        logger.info(f"📨 Sending payment confirmation to {to_number} for {name}, amount: {amount_received}")
        
        return self.twilio.send_template_message(
            to_number=to_number,
            content_sid=payment_sid,
            content_variables=variables,
            media_url=full_logo_url
        )

    def send_test_message(self, phone_number, message):
        """Alias for send_message to maintain compatibility"""
        logger.info(f"🧪 Sending test message to {phone_number}")
        return self.send_message(phone_number, message)

    def send_membership_expired(self, request, to_number, name, plan_name, expiry_date, gym_name, gym_contact_number, gym_logo_url=None):
        """
        Sends a membership expiry notification via Twilio.
        """
        expiry_sid = getattr(settings, 'TWILIO_MEMBERSHIP_EXPIRED_SID', None)
        
        if not expiry_sid:
            logger.error("❌ TWILIO_MEMBERSHIP_EXPIRED_SID not configured in settings")
            return {'success': False, 'error': 'Expiry template SID not configured'}
        
        full_logo_url = self._get_absolute_media_url(request, gym_logo_url)
        
        variables = {
            "1": name,
            "2": plan_name,
            "3": str(expiry_date),
            "4": gym_name,
            "5": str(gym_contact_number),
            "6": full_logo_url or ""
        }
        
        logger.info(f"📨 Sending membership expiry notification to {to_number} for {name}")
        
        return self.twilio.send_template_message(
            to_number=to_number,
            content_sid=expiry_sid,
            content_variables=variables,
            media_url=full_logo_url
        )

    def send_membership_expiring_soon(self, request, to_number, name, plan_name, expiry_date, gym_name, gym_contact_number, gym_logo_url=None):
        """
        Sends a membership expiring soon notification via Twilio.
        
        Args:
            1:name, 2:plan, 3:expiry_date, 4:gym_name, 5:contact, 6:media
        """
        soon_sid = getattr(settings, 'TWILIO_MEMBERSHIP_EXPIRING_SOON_SID', None)
        
        if not soon_sid:
            logger.error("❌ TWILIO_MEMBERSHIP_EXPIRING_SOON_SID not configured in settings")
            return {'success': False, 'error': 'Expiring soon template SID not configured'}
        
        full_logo_url = self._get_absolute_media_url(request, gym_logo_url)
        
        variables = {
            "1": name,
            "2": plan_name,
            "3": str(expiry_date),
            "4": gym_name,
            "5": str(gym_contact_number),
            "6": full_logo_url or ""
        }
        
        logger.info(f"📨 Sending membership expiring soon notice to {to_number} for {name}")
        
        return self.twilio.send_template_message(
            to_number=to_number,
            content_sid=soon_sid,
            content_variables=variables,
            media_url=full_logo_url
        )

    def send_birthday_wishes(self, request, to_number, name, gym_name, gym_contact_number=None, gym_logo_url=None):
        """
        Sends birthday wishes notification via Twilio.
        
        New Template (SID: HX0311a3e1b155aa9f1781951a71ee1b98):
        1: name, 2: gym_name
        """
        birthday_sid = getattr(settings, 'TWILIO_BIRTHDAY_WISHES_SID', None)
        
        if not birthday_sid:
            logger.error("❌ TWILIO_BIRTHDAY_WISHES_SID not configured in settings")
            return {'success': False, 'error': 'Birthday wishes template SID not configured'}
        
        # Variables: 1:name, 2:gym_name
        variables = {
            "1": str(name),
            "2": str(gym_name)
        }
        
        logger.info(f"📨 Sending birthday wishes to {to_number} for {name}")
        
        return self.twilio.send_template_message(
            to_number=to_number,
            content_sid=birthday_sid,
            content_variables=variables
        )

    def send_due_follow_up_reminder(self, request, to_number, name, plan_name, total_amount, last_payment_date, pending_due, gym_name, gym_contact_number, gym_logo_url=None):
        """
        Sends a due follow-up date reminder WhatsApp message via Twilio.
        Template: due_payment_follow_up_date (HX9cee0a39eb4ffe3c08b638ae6ca972ff)

        Args:
            request: Django request object
            to_number (str): Recipient phone number
            name (str): Member name
            plan_name (str): Membership plan name
            total_amount (str): Total membership amount
            last_payment_date (str): Date of last payment or start date
            pending_due (str): Current pending amount
            gym_name (str): Gym name
            gym_contact_number (str): Gym contact number
            gym_logo_url (str): URL for gym logo (optional)

        Returns:
            dict: Response from Twilio
        """
        follow_up_sid = getattr(settings, 'TWILIO_DUE_FOLLOW_UP_SID', None)

        if not follow_up_sid:
            logger.error("❌ TWILIO_DUE_FOLLOW_UP_SID not configured in settings")
            return {'success': False, 'error': 'Due follow-up template SID not configured'}

        full_logo_url = self._get_absolute_media_url(request, gym_logo_url)
        if full_logo_url:
            logger.debug(f"🖼️ Using public logo URL for Twilio: {full_logo_url}")

        # Variables for due_payment_follow_up_date template (SID: HX9cee0a39eb4ffe3c08b638ae6ca972ff)
        # 1:name, 2:plan, 3:total_amount, 4:last_payment_date, 5:pending_due, 6:gym_name, 7:contact, 8:logo
        variables = {
            "1": str(name),
            "2": str(plan_name),
            "3": str(total_amount),
            "4": str(last_payment_date),
            "5": str(pending_due),
            "6": str(gym_name),
            "7": str(gym_contact_number) if gym_contact_number else "N/A",
            "8": full_logo_url or ""
        }

        logger.info(f"📨 Sending due follow-up reminder to {to_number} for {name}, pending: {pending_due}")

        return self.twilio.send_template_message(
            to_number=to_number,
            content_sid=follow_up_sid,
            content_variables=variables,
            media_url=full_logo_url
        )

