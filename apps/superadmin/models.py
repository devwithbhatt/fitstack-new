import uuid
from django.db.models.signals import pre_save
from django.dispatch import receiver
# apps/tenants/models.py
from django.db import models
from .image_processing import process_image

class Gym(models.Model):
    gym_id = models.CharField(max_length=100, unique=True, editable=False)
    gym_id_prefix = models.CharField(max_length=10, unique=True, null=True)  # Allow null temporarily
    name = models.CharField(max_length=200)
    slogan = models.CharField(max_length=255, blank=True, null=True)
    logo = models.ImageField(upload_to="gym_logos/", null=True, blank=True)
    address = models.CharField(max_length=255, blank=True)
    pincode = models.CharField(max_length=100, blank=True)
    area = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    landline = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    website = models.URLField(blank=True)
    gst_number = models.CharField(max_length=15, blank=True, null=True)
    gst_enabled = models.BooleanField(default=False)
    gst_rate = models.PositiveIntegerField(default=0, blank=True, null=True)
    note = models.TextField(blank=True, null=True)
    is_frozen = models.BooleanField(default=False)
    password_reset_required = models.BooleanField(default=False)
    #aattendance code fields
    attendance_code = models.CharField(max_length=4, blank=True, null=True)
    attendance_code_expiry = models.DateTimeField(blank=True, null=True)
    attendance_code_required = models.BooleanField(default=True)
    qr_code = models.ImageField(upload_to='qrcodes/', blank=True, null=True)
    whatsapp_enabled = models.BooleanField(default=True, help_text="Enable or disable WhatsApp messaging for this gym")
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        # Check if the logo has been changed
        if self.pk:
            try:
                old_instance = Gym.objects.get(pk=self.pk)
                if old_instance.logo != self.logo:
                    process_image(self.logo)
            except Gym.DoesNotExist:
                # This happens when creating a new object
                if self.logo:
                    process_image(self.logo)
        elif self.logo:
            # This is for a new object
            process_image(self.logo)
            
        super().save(*args, **kwargs)

@receiver(pre_save, sender=Gym)
def create_gym_id(sender, instance, **kwargs):
    if not instance.gym_id:
        instance.gym_id = f"GYM-{uuid.uuid4().hex[:8].upper()}"

class GymAdmin(models.Model):
    user = models.OneToOneField("auth.User", on_delete=models.CASCADE)
    gym = models.ForeignKey(Gym, on_delete=models.CASCADE)
    name = models.CharField(max_length=150, blank=True, null=True)
    Phone_number = models.CharField(max_length=15, blank=True, null=True)
    photo = models.ImageField(upload_to="gym_admin_photos/", null=True, blank=True)
    Department = models.CharField(max_length=100, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)

    def __str__(self):
        return f'{self.user.username} - {self.gym.name}'

class SubscriptionPlan(models.Model):
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    duration_months = models.IntegerField(help_text="Duration in months", default=1)
    features = models.TextField()

    def __str__(self):
        return self.name

class GymSubscription(models.Model):
    PAYMENT_MODE_CHOICES = [
        ('cash', 'Cash'),
        ('upi', 'UPI'),
        ('credit_card', 'Credit Card'),
        ('debit_card', 'Debit Card'),
        ('net_banking', 'Net Banking'),
        ('other', 'Other'),
    ]
    gym = models.ForeignKey(Gym, on_delete=models.CASCADE)
    subscription = models.ForeignKey(SubscriptionPlan, on_delete=models.CASCADE)
    start_date = models.DateField()
    end_date = models.DateField()
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    paid_amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_mode = models.CharField(max_length=50, choices=PAYMENT_MODE_CHOICES, default='cash') 
    transaction_id = models.CharField(max_length=100, blank=True, null=True)
    remark = models.TextField(blank=True, null=True)
    is_deleted = models.BooleanField(default=False)


    @property
    def is_subscription(self):
        return True

    @property
    def due_amount(self):
        return self.total_amount - self.paid_amount