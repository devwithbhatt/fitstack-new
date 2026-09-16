from dateutil.relativedelta import relativedelta
from django.db import models
from datetime import timedelta
from django.utils import timezone
from django.contrib.auth.models import User
from apps.trainers.models import Trainer
from apps.superadmin.models import Gym
from apps.management.models import DietPlan, WorkoutPlan



class Member(models.Model):
    IDENTITY_TYPE_CHOICES = [
        ('Aadhar Card', 'Aadhar Card'),
        ('PAN Card', 'PAN Card'),
        ('Driving License', 'Driving License'),
        ('Passport', 'Passport'),
        ('Other', 'Other'),
    ]
    user = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='member_profile')
    gym = models.ForeignKey(Gym, on_delete=models.CASCADE, null=True)
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    mobile_number = models.CharField(max_length=10)
    RELATION_CHOICES = [
        ('Myself', 'Myself'),
        ('Spouse', 'Spouse'),
        ('Child', 'Child'),
        ('Parent', 'Parent'),
        ('Sibling', 'Sibling'),
        ('Other', 'Other'),
    ]
    relation = models.CharField(max_length=50, choices=RELATION_CHOICES, default='Myself', null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    age = models.PositiveIntegerField(null=True, blank=True )
    gender = models.CharField(max_length=10, choices=[('Male', 'Male'), ('Female', 'Female'), ('Other', 'Other')],
                              null=True, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    profile_picture = models.ImageField(upload_to='profile_pics/', blank=True, null=True)
    address = models.CharField(max_length=255, null=True, blank=True)
    state = models.CharField(max_length=100, null=True, blank=True)
    city = models.CharField(max_length=100, null=True, blank=True)
    pincode = models.CharField(max_length=10, null=True, blank=True)
    profession = models.CharField(max_length=100, null=True, blank=True)
    sign = models.ImageField(upload_to='signs/', blank=True, null=True)
    identity_type = models.CharField(max_length=50, choices=IDENTITY_TYPE_CHOICES, null=True, blank=True)
    identity_no = models.CharField(max_length=50, null=True, blank=True)
    identity_document_image = models.ImageField(upload_to='identity_docs/', blank=True, null=True)
    is_deleted = models.BooleanField(default=False)
    last_birthday_wish_sent_year = models.IntegerField(null=True, blank=True)

    class Meta:
        unique_together = [['gym', 'mobile_number', 'relation'], ['gym', 'email']]

    # Keep unique=True 
    member_id = models.CharField(max_length=100, unique=True, editable=False)

    def save(self, *args, **kwargs):
        """
        Auto-generate Member ID:
        Format: GYM-PREFIX-MEM-YY-000001
        Example: BGT-MEM-25-000001
        """
        if not self.member_id:
            year = timezone.now().strftime("%y")
            prefix = f"{self.gym.gym_id_prefix}-MEM-{year}-"

            # Find the latest member_id for this gym and year
            latest_member = Member.objects.filter(
                gym=self.gym,
                member_id__startswith=prefix
            ).order_by('-member_id').first()

            if latest_member:
                # Extract the numeric part and increment it
                last_id = int(latest_member.member_id.split('-')[-1])
                new_id = last_id + 1
            else:
                # First member of the year
                new_id = 1
            
            # 6-digit sequence number
            counter = str(new_id).zfill(6)
            self.member_id = f"{prefix}{counter}"

        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.first_name} {self.last_name}'

    def create_or_update_user_account(self, raw_password=None):
        """
        Creates or updates a Django User account linked to this Member.
        Returns (user, raw_password).
        """
        from django.contrib.auth.models import User
        if not raw_password:
            phone_suffix = self.mobile_number[-4:] if self.mobile_number and len(self.mobile_number) >= 4 else '1234'
            raw_password = f"Fit@{phone_suffix}"

        username = self.member_id
        if not self.user:
            user = User.objects.filter(username=username).first()
            if not user:
                user = User(username=username)
            user.first_name = self.first_name or ''
            user.last_name = self.last_name or ''
            user.email = self.email or ''
            user.set_password(raw_password)
            user.save()
            self.user = user
            self.save(update_fields=['user'])
        else:
            if raw_password:
                self.user.set_password(raw_password)
            self.user.first_name = self.first_name or ''
            self.user.last_name = self.last_name or ''
            if self.email:
                self.user.email = self.email
            self.user.save()

        return self.user, raw_password

    @property
    def name(self):
      first = (self.first_name or '').strip().title()
      last = (self.last_name or '').strip().title()
      return f"{first} {last}".strip()


    @property
    def latest_membership(self):
        # Use prefetched data if available to avoid N+1 queries
        if 'membership_history' in getattr(self, '_prefetched_objects_cache', {}):
            histories = list(self.membership_history.all())
            if histories:
                return sorted(histories, key=lambda h: h.membership_start_date, reverse=True)[0]
            return None
        return self.membership_history.order_by('-membership_start_date').first()

    @property
    def current_status(self):
        latest = self.latest_membership
        if not latest:
            return "No Membership"

        if latest.is_frozen:
            return "Freezed"
        
        if latest.get_end_date() < timezone.localdate():
            return "Expired"

        return "Active"

    @property
    def is_active(self):
        latest = self.latest_membership
        if not latest:
            return False
        return latest.get_end_date() >= timezone.localdate()


class MedicalHistory(models.Model):
    gym = models.ForeignKey(Gym, on_delete=models.CASCADE, null=True)
    member = models.ForeignKey(Member, related_name='medical_history', on_delete=models.CASCADE)
    condition = models.CharField(max_length=100)
    type = models.CharField(max_length=100)
    since = models.DateField()

    def __str__(self):
        return f'{self.member} - {self.condition}'


class EmergencyContact(models.Model):
    gym = models.ForeignKey(Gym, on_delete=models.CASCADE, null=True)
    member = models.OneToOneField(Member, related_name='emergency_contact', on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    mobile = models.CharField(max_length=15)
    relation = models.CharField(max_length=50)

    def __str__(self):
        return f'{self.member} - {self.name}'


class MembershipHistory(models.Model):
    gym = models.ForeignKey(Gym, on_delete=models.CASCADE, null=True)
    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name='membership_history')
    plan = models.ForeignKey('management.MembershipPlan', on_delete=models.CASCADE)
    registration_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    membership_start_date = models.DateField()
    payment_date = models.DateField(default=timezone.localdate)
    add_on_days = models.IntegerField(default=0)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    sgst = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    cgst = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    gst_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    paid_amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_mode = models.CharField(max_length=50,
         choices=[('cash', 'Cash'), ('upi', 'UPI'),
                 ('credit_card', 'Credit Card'),
                 ('debit_card', 'Debit Card'), 
                 ('net_banking', 'Net Banking'),
                 ('other', 'Other')], default='cash')
    transaction_id = models.CharField(max_length=100, blank=True, null=True)
    comment = models.TextField(blank=True, null=True)
    follow_up_date = models.DateField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=10, choices=[('active', 'Active'), ('inactive', 'Inactive'), ('frozen', 'Frozen')],
                              default='active')
    is_deleted = models.BooleanField(default=False)
    expiry_notification_sent = models.BooleanField(default=False)
    reminder_4_days_sent = models.BooleanField(default=False)
    reminder_2_days_sent = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.member} - {self.plan}"

    @property
    def is_frozen(self):
        # Use prefetched data if available to avoid N+1 queries
        if 'freezes' in getattr(self, '_prefetched_objects_cache', {}):
            return any(f.unfreeze_date is None for f in self.freezes.all())
        return self.freezes.filter(unfreeze_date__isnull=True).exists()

    @property
    def due_amount(self):
        return self.total_amount - self.paid_amount

    @property
    def total_add_on_days(self):
        return self.add_on_days + self.plan.add_on_days

    def get_end_date(self):
        duration_parts = self.plan.duration.split('_')
        duration_value = int(duration_parts[0])
        duration_unit = duration_parts[1]

        total_add_on_days = self.total_add_on_days

        if duration_unit in ['day', 'days']:
            base_end_date = self.membership_start_date + timedelta(days=duration_value + total_add_on_days)
        elif duration_unit in ['week', 'weeks']:
            base_end_date = self.membership_start_date + timedelta(weeks=duration_value) + timedelta(days=total_add_on_days)
        elif duration_unit in ['month', 'months']:
            base_end_date = self.membership_start_date + relativedelta(months=duration_value) + timedelta(days=total_add_on_days)
        elif duration_unit in ['year', 'years']:
            base_end_date = self.membership_start_date + relativedelta(years=duration_value) + timedelta(days=total_add_on_days)
        else:
            return None

        # Use prefetched freezes if available to avoid N+1 queries
        freezes = self.freezes.all()  # Will use prefetch cache if available
        total_freeze_duration = sum(freeze.duration for freeze in freezes)
        return base_end_date + timedelta(days=total_freeze_duration)


class PersonalTrainer(models.Model):
    gym = models.ForeignKey(Gym, on_delete=models.CASCADE, null=True)
    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name='personal_trainer')
    trainer = models.ForeignKey(Trainer, on_delete=models.CASCADE)
    months = models.PositiveIntegerField()
    trainer_fee = models.DecimalField(max_digits=10, decimal_places=2)
    gym_charges = models.DecimalField(max_digits=10, decimal_places=2)
    pt_start_date = models.DateField()
    payment_date = models.DateField(default=timezone.localdate)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    paid_amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_mode = models.CharField(max_length=50,
                                    choices=[('cash', 'Cash'), ('upi', 'UPI'), ('credit_card', 'Credit Card'),
                                             ('debit_card', 'Debit Card'), ('net_banking', 'Net Banking'),
                                             ('other', 'Other')], default='cash')
    transaction_id = models.CharField(max_length=100, blank=True, null=True)
    comment = models.TextField(blank=True, null=True)
    follow_up_date = models.DateField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=10, choices=[('active', 'Active'), ('inactive', 'Inactive')], default='active')
    created_at = models.DateTimeField(auto_now_add=True)
    is_deleted = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.member.first_name} {self.member.last_name} - {self.trainer.name}"

    def get_end_date(self):
        return self.pt_start_date + timedelta(days=30 * self.months)

    @property
    def due_amount(self):
        return self.total_amount - self.paid_amount


class MembershipFreeze(models.Model):
    membership = models.ForeignKey(MembershipHistory, on_delete=models.CASCADE, related_name='freezes')
    freeze_date = models.DateField()
    unfreeze_date = models.DateField(null=True, blank=True)
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.membership.member.name} - Freeze from {self.freeze_date}"

    @property
    def duration(self):
        if self.unfreeze_date:
            return (self.unfreeze_date - self.freeze_date).days
        return (timezone.localdate() - self.freeze_date).days


class AssignDietPlan(models.Model):
    gym = models.ForeignKey(Gym, on_delete=models.CASCADE, null=True)
    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name='assigned_diet_plans')
    diet_plan = models.ForeignKey(DietPlan, on_delete=models.CASCADE, null=True)
    assigned_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.member.name} - {self.diet_plan.name}'


class AssignWorkoutPlan(models.Model):
    gym = models.ForeignKey(Gym, on_delete=models.CASCADE, null=True)
    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name='assigned_workout_plans')
    workout_plan = models.ForeignKey(WorkoutPlan, on_delete=models.CASCADE, null=True)
    assigned_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.member.first_name} {self.member.last_name} - {self.workout_plan.title}"
        return f'{self.member.name} - {self.workout_plan.name}'