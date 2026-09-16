from django.db import models
from apps.superadmin.models import Gym

class WhatsAppConfig(models.Model):
    gym = models.OneToOneField(Gym, on_delete=models.CASCADE, related_name='whatsapp_config')
    whatsapp_business_account_id = models.CharField(max_length=255, blank=True, null=True)
    phone_number_id = models.CharField(max_length=255, blank=True, null=True)
    access_token = models.CharField(max_length=255, blank=True, null=True)
    api_version = models.CharField(max_length=10, default='v19.0')

    def __str__(self):
        return f"WhatsApp Config for {self.gym.name}"