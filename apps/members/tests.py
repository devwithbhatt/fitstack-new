from datetime import date, timedelta
from decimal import Decimal
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from apps.superadmin.models import Gym, GymAdmin
from apps.members.models import Member, MembershipHistory, AssignDietPlan, AssignWorkoutPlan
from apps.management.models import MembershipPlan, DietPlan, WorkoutPlan

class MemberSecurityAndTenantIsolationTests(TestCase):
    def setUp(self):
        self.client1 = Client()
        self.client2 = Client()

        # Create two gyms
        self.gym1 = Gym.objects.create(
            name='Gym One',
            phone='9000000001',
            email='gym1@fitstack.com',
            gym_id_prefix='GYM1'
        )
        self.gym2 = Gym.objects.create(
            name='Gym Two',
            phone='9000000002',
            email='gym2@fitstack.com',
            gym_id_prefix='GYM2'
        )

        # Users and GymAdmins
        self.user1 = User.objects.create_user(username='admin_gym1', password='password123')
        self.gym_admin1 = GymAdmin.objects.create(user=self.user1, gym=self.gym1)

        self.user2 = User.objects.create_user(username='admin_gym2', password='password123')
        self.gym_admin2 = GymAdmin.objects.create(user=self.user2, gym=self.gym2)

        # Log both clients in
        self.client1.login(username='admin_gym1', password='password123')
        session1 = self.client1.session
        session1['gym_id'] = self.gym1.id
        session1.save()

        self.client2.login(username='admin_gym2', password='password123')
        session2 = self.client2.session
        session2['gym_id'] = self.gym2.id
        session2.save()

        # Members
        self.member1 = Member.objects.create(
            gym=self.gym1,
            first_name='Alice',
            last_name='Wonder',
            mobile_number='9876500001',
            email='alice@example.com',
            gender='Female',
            date_of_birth=date(1995, 1, 1),
        )

        self.member2 = Member.objects.create(
            gym=self.gym2,
            first_name='Bob',
            last_name='Builder',
            mobile_number='9876500002',
            email='bob@example.com',
            gender='Male',
            date_of_birth=date(1990, 5, 5),
        )

        # Membership Plans
        self.plan1 = MembershipPlan.objects.create(
            gym=self.gym1,
            title='Gold Plan Gym1',
            amount=Decimal('3000.00'),
            duration='1_month'
        )

        self.plan2 = MembershipPlan.objects.create(
            gym=self.gym2,
            title='Silver Plan Gym2',
            amount=Decimal('2000.00'),
            duration='1_month'
        )

        self.history2 = MembershipHistory.objects.create(
            gym=self.gym2,
            member=self.member2,
            plan=self.plan2,
            membership_start_date=date.today(),
            total_amount=Decimal('2000.00'),
            paid_amount=Decimal('2000.00'),
            status='active'
        )

    def test_tenant_isolation_member_profile(self):
        """Gym 1 admin cannot view Gym 2 member profile."""
        response = self.client1.get(
            reverse('member_profile', kwargs={'member_id': self.member2.id}),
            secure=True
        )
        # Should redirect to member_list with error message
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('member_list'), response.url)

    def test_tenant_isolation_freeze_membership(self):
        """Gym 1 admin cannot freeze membership belonging to Gym 2."""
        url = reverse('freeze_membership', kwargs={'membership_id': self.history2.id})
        response = self.client1.post(url, {'freeze_date': str(date.today()), 'reason': 'Malicious attempt'}, secure=True)
        # Should redirect to member_list because record is not found for Gym 1
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('member_list'), response.url)
        self.history2.refresh_from_db()
        self.assertEqual(self.history2.status, 'active')

    def test_member_delete_returns_valid_response(self):
        """Member deletion returns a valid JSON response with 200."""
        url = reverse('delete_member', kwargs={'member_id': self.member1.id})
        response = self.client1.post(url, secure=True)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get('status'), 'success')

    def test_tenant_isolation_password_reset(self):
        """Gym 1 admin cannot reset password of member in Gym 2."""
        url = reverse('reset_member_password', kwargs={'member_id': self.member2.id})
        response = self.client1.post(url, {'new_password': 'HackedPassword!'}, secure=True)
        self.assertEqual(response.status_code, 404)
