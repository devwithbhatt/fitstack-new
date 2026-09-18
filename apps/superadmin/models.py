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


class PlatformNotification(models.Model):
    TYPE_CHOICES = [
        ('info', 'Information'),
        ('warning', 'Notice / Warning'),
        ('success', 'Update / Success'),
        ('danger', 'Urgent / Critical Alert'),
    ]

    TARGET_CHOICES = [
        ('all', 'All Users (Gyms, Staff & Members)'),
        ('all_gyms', 'All Gym Admins & Staff Only'),
        ('all_members', 'All Gym Members Across All Gyms'),
        ('specific_gym', 'Specific Gym (Admins, Staff & Members)'),
        ('specific_gym_staff', 'Specific Gym Admins & Staff Only'),
        ('specific_gym_members', 'Specific Gym Members Only'),
        ('specific_user', 'Specific User / Member'),
    ]

    title = models.CharField(max_length=255)
    message = models.TextField(help_text="Notification message body")
    notification_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='info')
    target_type = models.CharField(max_length=30, choices=TARGET_CHOICES, default='all')
    target_gym = models.ForeignKey(Gym, on_delete=models.CASCADE, null=True, blank=True, related_name='targeted_notifications')
    target_user = models.ForeignKey("auth.User", on_delete=models.CASCADE, null=True, blank=True, related_name='direct_notifications')

    # Image / Banner
    image = models.ImageField(upload_to="notification_images/", null=True, blank=True, help_text="Optional banner/graphic image")

    # Popup announcement options
    show_popup = models.BooleanField(default=False, help_text="Display as an instant interactive popup modal to recipients")
    is_dismissible = models.BooleanField(default=True, help_text="Can the user dismiss without action?")
    
    POPUP_FREQUENCY_CHOICES = [
        ('once', 'Once Only (Dismissed after first view)'),
        ('every_login', 'On Every Login (Once per session until expired)'),
        ('fixed_count', 'Impression Cap (Show up to set number of times)'),
        ('until_expired', 'Persistent (Show on every page visit until expired)'),
    ]
    popup_frequency = models.CharField(max_length=30, choices=POPUP_FREQUENCY_CHOICES, default='once', help_text="Frequency of showing popup to users")
    max_popup_views = models.PositiveIntegerField(default=1, help_text="Maximum times a user will see this popup (if fixed count is selected)")

    # Action button
    action_label = models.CharField(max_length=100, blank=True, null=True, help_text="e.g. 'View Details', 'Renew Now'")
    action_url = models.CharField(max_length=255, blank=True, null=True, help_text="URL or path for button")

    # Lifecycle & Audit
    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(null=True, blank=True, help_text="Optional auto-expiry datetime")
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey("auth.User", on_delete=models.SET_NULL, null=True, blank=True, related_name='authored_notifications')

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.get_notification_type_display()}] {self.title}"


class NotificationUserStatus(models.Model):
    notification = models.ForeignKey(PlatformNotification, on_delete=models.CASCADE, related_name='user_statuses')
    user = models.ForeignKey("auth.User", on_delete=models.CASCADE, related_name='notification_statuses')
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    popup_acknowledged = models.BooleanField(default=False)
    popup_acknowledged_at = models.DateTimeField(null=True, blank=True)
    popup_view_count = models.PositiveIntegerField(default=0)
    popup_last_shown_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('notification', 'user')
        indexes = [
            models.Index(fields=['user', 'is_read']),
            models.Index(fields=['user', 'popup_acknowledged']),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.notification.title} (Read: {self.is_read}, Views: {self.popup_view_count})"