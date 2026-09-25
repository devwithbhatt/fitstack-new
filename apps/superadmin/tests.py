from datetime import date, timedelta
from decimal import Decimal
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from apps.superadmin.models import Gym, SubscriptionPlan, GymSubscription
from apps.billing.models import Payment

class SuperadminSecurityAndBillingTests(TestCase):
    def setUp(self):
        self.client = Client()
        
        # Superadmin user
        self.admin_user = User.objects.create_superuser(
            username='superadmin_test',
            email='admin@fitstack.com',
            password='testpassword123'
        )
        
        # Regular user
        self.regular_user = User.objects.create_user(
            username='regular_test',
            email='user@fitstack.com',
            password='userpassword123'
        )
        
        # Create a test Gym
        self.gym = Gym.objects.create(
            name='Test Alpha Gym',
            phone='9876543210',
            email='alpha@gym.com',
            gym_id_prefix='ALPHA'
        )
        
        # Plan
        self.plan = SubscriptionPlan.objects.create(
            name='Standard Annual Plan',
            price=Decimal('10000.00'),
            duration_months=12,
            features='All Features'
        )
        
        # Subscription with 5000 due
        self.sub = GymSubscription.objects.create(
            gym=self.gym,
            subscription=self.plan,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=365),
            total_amount=Decimal('10000.00'),
            paid_amount=Decimal('5000.00'),
            payment_mode='cash'
        )

    def test_unauthenticated_access_blocked(self):
        """Unauthenticated requests to superadmin endpoints must redirect to login."""
        endpoints = [
            reverse('superadmin:dashboard'),
            reverse('superadmin:submit_due'),
            reverse('superadmin:invoice', kwargs={'subscription_id': self.sub.id}),
        ]
        for url in endpoints:
            response = self.client.get(url, secure=True)
            self.assertEqual(response.status_code, 302, f"Failed for {url}")
            self.assertIn('/login/', response.url)

    def test_regular_user_forbidden_from_superadmin(self):
        """Regular non-superadmin users must be redirected away from superadmin."""
        self.client.login(username='regular_test', password='userpassword123')
        session = self.client.session
        session['role'] = 'member'
        session.save()
        
        response = self.client.get(reverse('superadmin:dashboard'), secure=True)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)

    def test_submit_due_pays_in_full_without_none_type_error(self):
        """
        Regression Test: When a payment pays off the remaining due in full,
        submit_due must NOT crash with 'NoneType' object has no attribute 'id',
        must update paid_amount, create Payment, and store open_invoice_id in session.
        """
        self.client.login(username='superadmin_test', password='testpassword123')
        session = self.client.session
        session['role'] = 'superadmin'
        session.save()
        
        post_data = {
            'gym': self.gym.id,
            'amount_to_pay': '5000.00',
            'payment_method': 'upi',
            'notes': 'Paid in full via UPI'
        }
        
        # Submit the full remaining due
        response = self.client.post(reverse('superadmin:submit_due'), post_data, secure=True)
        
        # Should redirect successfully without throwing 500 AttributeError
        self.assertEqual(response.status_code, 302)
        
        # Verify database state
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.paid_amount, Decimal('10000.00'))
        self.assertEqual(self.sub.due_amount, Decimal('0.00'))
        
        # Payment record created
        payment = Payment.objects.filter(gym=self.gym, amount=Decimal('5000.00')).first()
        self.assertIsNotNone(payment)
        self.assertEqual(payment.payment_mode, 'upi')
        
        # Invoice session set safely
        self.assertEqual(self.client.session.get('open_invoice_id'), self.sub.id)

    def test_submit_due_rejects_overpayment(self):
        """Payments greater than total due must be rejected."""
        self.client.login(username='superadmin_test', password='testpassword123')
        session = self.client.session
        session['role'] = 'superadmin'
        session.save()
        
        post_data = {
            'gym': self.gym.id,
            'amount_to_pay': '6000.00',  # Due is only 5000.00
            'payment_method': 'cash',
            'notes': 'Overpayment attempt'
        }
        
        response = self.client.post(reverse('superadmin:submit_due'), post_data, secure=True)
        self.assertEqual(response.status_code, 302)
        
        # Subscription due unchanged
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.paid_amount, Decimal('5000.00'))
        self.assertEqual(self.sub.due_amount, Decimal('5000.00'))
