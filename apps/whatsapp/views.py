# apps/whatsapp/views.py
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
import json
import logging

# Import the singleton service instance
from .services import WhatsAppService

logger = logging.getLogger('apps.whatsapp')

@method_decorator(csrf_exempt, name='dispatch')
class TwilioWebhook(View):
    """
    Handles incoming webhook events from Twilio WhatsApp.
    """
    def post(self, request):
        # Twilio sends data as Form Data, not JSON
        data = request.POST
        from_number = data.get('From', '')
        body = data.get('Body', '')
        
        logger.info(f"📥 Twilio Message received from {from_number}: {body}")
        
        # Example auto-reply logic
        text = str(body).lower()
        if any(keyword in text for keyword in ['enquiry', 'interested', 'membership', 'hi', 'hello']):
            logger.info(f"Auto-replying to {from_number} (Twilio) based on keywords.")
            whatsapp_service = WhatsAppService()
            whatsapp_service.send_enquiry_confirmation(
                request=request,
                to_number=from_number,
                name="Valued Customer",
                gym_name="FitStack", # Fallback
                gym_contact_number=None
            )
            
        return HttpResponse('OK', status=200)

@method_decorator(csrf_exempt, name='dispatch')
class SendEnquiryConfirmationAPI(View):
    """
    An API endpoint to manually trigger the sending of an enquiry confirmation.
    Expects a JSON payload with 'phone_number' and optional 'name'.
    """
    
    def post(self, request):
        try:
            data = json.loads(request.body)
            phone_number = data.get('phone_number')
            name = data.get('name', 'Valued Customer')
            
            if not phone_number:
                return JsonResponse({'error': 'phone_number is required'}, status=400)
            
            whatsapp_service = WhatsAppService()
            result = whatsapp_service.send_enquiry_confirmation(
                request=request,
                to_number=phone_number,
                name=name,
                gym_name="FitStack",
                gym_contact_number=None
            )
            
            if result.get('success'):
                return JsonResponse(result)
            else:
                return JsonResponse(result, status=500)

        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            logger.error(f"API Error sending confirmation: {e}")
            return JsonResponse({'error': 'Internal server error'}, status=500)

@method_decorator(csrf_exempt, name='dispatch')
class SendTestMessage(View):
    """API endpoint to send test message"""
    
    def post(self, request):
        try:
            if not request.body:
                return JsonResponse({'error': 'Empty request body'}, status=400)
            
            data = json.loads(request.body)
            
            phone_number = data.get('phone_number')
            message = data.get('message', 'Test message from FitStack GYM')
            
            if not phone_number:
                return JsonResponse({'error': 'Phone number required'}, status=400)
            
            whatsapp_service = WhatsAppService()
            result = whatsapp_service.send_test_message(phone_number, message)
            
            if result.get('success'):
                return JsonResponse({
                    'success': True,
                    'message': 'Test message sent',
                    'message_id': result.get('message_id')
                })
            else:
                return JsonResponse({
                    'success': False,
                    'error': result.get('error')
                }, status=400)
                
        except Exception as e:
            logger.error(f"Error: {e}")
            return JsonResponse({'error': str(e)}, status=500)

class WhatsAppHealthCheck(View):
    """Simplified health check for Twilio"""
    
    def get(self, request):
        whatsapp_service = WhatsAppService()
        initialized = whatsapp_service.twilio.client is not None
        
        return JsonResponse({
            'status': 'healthy' if initialized else 'degraded',
            'backend': 'twilio',
            'connected': initialized
        })