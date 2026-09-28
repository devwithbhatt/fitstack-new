from decimal import Decimal
from datetime import date, timedelta
from django.test import TestCase, Client, override_settings
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

from apps.superadmin.models import Gym, GymAdmin
from apps.trainers.models import Trainer
from apps.members.models import Member, PersonalTrainer
from apps.attendance.models import TrainerAttendance, TrainerLeave


@override_settings(SECURE_SSL_REDIRECT=False)
class TrainerModuleTests(TestCase):
    def setUp(self):
        self.client1 = Client()
        self.client2 = Client()

        # Create two gyms for multi-tenant isolation testing
        self.gym1 = Gym.objects.create(
            name='Iron Paradise Gym',
            phone='9876543210',
            email='iron@gym.com',
            gym_id_prefix='IRON'
        )
        self.gym2 = Gym.objects.create(
            name='Titan Fitness Gym',
            phone='9876543211',
            email='titan@gym.com',
            gym_id_prefix='TITAN'
        )

        # Users & GymAdmins
        self.user1 = User.objects.create_user(username='iron_admin', password='password123')
        self.gym_admin1 = GymAdmin.objects.create(user=self.user1, gym=self.gym1)

        self.user2 = User.objects.create_user(username='titan_admin', password='password123')
        self.gym_admin2 = GymAdmin.objects.create(user=self.user2, gym=self.gym2)

        # Log in client1 (Gym 1)
        self.client1.login(username='iron_admin', password='password123')
        session1 = self.client1.session
        session1['gym_id'] = self.gym1.id
        session1.save()

        # Log in client2 (Gym 2)
        self.client2.login(username='titan_admin', password='password123')
        session2 = self.client2.session
        session2['gym_id'] = self.gym2.id
        session2.save()

        # Create sample trainer in Gym 1
        self.trainer1 = Trainer.objects.create(
            gym=self.gym1,
            name='Vikram Sharma',
            email='vikram@coach.com',
            phone='9876500001',
            address='123 Fitness Street, South Block',
            joining_date=date.today() - timedelta(days=200),
            salary=Decimal('35000.00'),
            personal_training_monthly_amount=Decimal('4500.00'),
            specialization='PT',
            time_slot='Morning 6:00 AM - 12:00 PM',
            is_active=True
        )
        # Provision User account for trainer
        self.trainer1.create_or_update_user_account(raw_password='Fit@0001')

    def test_trainer_list_renders_and_contains_profile_links(self):
        """Trainer list page displays trainers with profile links and action buttons."""
        url = reverse('trainer_list')
        response = self.client1.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Vikram Sharma')
        self.assertContains(response, self.trainer1.trainer_id)
        # Profile link present
        profile_url = reverse('trainer_profile', args=[self.trainer1.id])
        self.assertContains(response, profile_url)

    def test_trainer_profile_view_and_overview_details(self):
        """Trainer profile displays complete personal, professional, and credential information."""
        url = reverse('trainer_profile', args=[self.trainer1.id])
        response = self.client1.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Trainer Profile')
        self.assertContains(response, 'Vikram Sharma')
        self.assertContains(response, self.trainer1.trainer_id)
        self.assertContains(response, '35000.00')
        self.assertContains(response, 'Personal Trainer')
        self.assertContains(response, 'Morning 6:00 AM - 12:00 PM')
        self.assertEqual(response.context['trainer'], self.trainer1)

    def test_trainer_profile_with_pt_clients_and_revenue(self):
        """Trainer profile aggregates assigned PT clients, calculates revenue, and displays active clients."""
        # Create a member in Gym 1
        member = Member.objects.create(
            gym=self.gym1,
            first_name='Rahul',
            last_name='Verma',
            mobile_number='9876599999',
            email='rahul@member.com',
            gender='male'
        )

        # Assign member to trainer1 for Personal Training
        pt = PersonalTrainer.objects.create(
            gym=self.gym1,
            member=member,
            trainer=self.trainer1,
            months=3,
            trainer_fee=Decimal('12000.00'),
            gym_charges=Decimal('3000.00'),
            pt_start_date=date.today() - timedelta(days=15),
            total_amount=Decimal('15000.00'),
            paid_amount=Decimal('10000.00'),
            status='active'
        )

        url = reverse('trainer_profile', args=[self.trainer1.id])
        response = self.client1.get(url)
        self.assertEqual(response.status_code, 200)

        # Context aggregations
        self.assertEqual(response.context['total_clients_count'], 1)
        self.assertEqual(response.context['active_clients_count'], 1)
        self.assertEqual(response.context['total_pt_revenue'], Decimal('15000.00'))
        self.assertEqual(response.context['total_pt_paid'], Decimal('10000.00'))
        self.assertEqual(response.context['total_pt_due'], Decimal('5000.00'))

        # Check member appears in HTML
        self.assertContains(response, 'Rahul Verma')
        self.assertContains(response, '10000.00')
        self.assertContains(response, '5000.00')

    def test_trainer_profile_attendance_and_leaves(self):
        """Attendance logs and leave records are accurately counted and rendered in tabs."""
        now = timezone.now()
        # Create attendance record
        TrainerAttendance.objects.create(
            gym=self.gym1,
            trainer=self.trainer1,
            check_in_time=now - timedelta(hours=4),
            check_out_time=now,
            status='outside'
        )

        # Create leave record
        TrainerLeave.objects.create(
            gym=self.gym1,
            trainer=self.trainer1,
            start_date=date.today() + timedelta(days=5),
            end_date=date.today() + timedelta(days=6),
            reason='Family event',
            status='approved',
            leave_type='casual'
        )

        url = reverse('trainer_profile', args=[self.trainer1.id])
        response = self.client1.get(url)
        self.assertEqual(response.status_code, 200)

        self.assertEqual(response.context['month_present_days'], 1)
        self.assertEqual(response.context['approved_leaves'], 1)
        self.assertContains(response, 'Casual Leave')
        self.assertContains(response, 'Family event')

    def test_multi_tenant_isolation(self):
        """Gym 2 cannot view, edit, toggle, or delete Gym 1's trainer profile."""
        profile_url = reverse('trainer_profile', args=[self.trainer1.id])
        res_profile = self.client2.get(profile_url)
        # Should redirect to trainer list because trainer is not found in Gym 2
        self.assertEqual(res_profile.status_code, 302)

        toggle_url = reverse('toggle_trainer_status', args=[self.trainer1.id])
        res_toggle = self.client2.get(toggle_url)
        self.assertEqual(res_toggle.status_code, 302)

        del_url = reverse('delete_trainer', args=[self.trainer1.id])
        res_del = self.client2.post(del_url)
        self.assertEqual(res_del.status_code, 404)

        # Verify trainer1 was NOT deleted
        self.trainer1.refresh_from_db()
        self.assertEqual(self.trainer1.name, 'Vikram Sharma')

    def test_toggle_trainer_status_and_redirect(self):
        """Toggling status switches is_active and redirects back to profile if requested from profile."""
        url = reverse('toggle_trainer_status', args=[self.trainer1.id])
        profile_url = reverse('trainer_profile', args=[self.trainer1.id])

        # Toggle from profile page
        response = self.client1.get(url, HTTP_REFERER=profile_url)
        self.assertRedirects(response, profile_url)

        self.trainer1.refresh_from_db()
        self.assertFalse(self.trainer1.is_active)

        # Toggle back
        response2 = self.client1.get(url, HTTP_REFERER=profile_url)
        self.assertRedirects(response2, profile_url)
        self.trainer1.refresh_from_db()
        self.assertTrue(self.trainer1.is_active)

    def test_reset_trainer_password(self):
        """Resetting trainer password returns JSON credentials for SweetAlert & WhatsApp share."""
        url = reverse('reset_trainer_password', args=[self.trainer1.id])
        response = self.client1.post(url, {'new_password': 'CustomTrainer@99'})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['new_password'], 'CustomTrainer@99')

        # Verify password in DB
        self.trainer1.user.refresh_from_db()
        self.assertTrue(self.trainer1.user.check_password('CustomTrainer@99'))

    def test_edit_trainer_updates_and_redirects_to_profile(self):
        """Editing trainer persists changes and redirects to their profile."""
        url = reverse('edit_trainer', args=[self.trainer1.id])
        post_data = {
            'name': 'Vikram Sharma Senior',
            'email': 'vikram_senior@coach.com',
            'phone': '9876500001',
            'address': 'New Gym Heights, Floor 2',
            'joining_date': str(self.trainer1.joining_date),
            'salary': '42000.00',
            'personal_training_monthly_amount': '5000.00',
            'specialization': 'PT',
            'time_slot': 'Evening 4:00 PM - 10:00 PM'
        }
        response = self.client1.post(url, post_data)
        self.assertRedirects(response, reverse('trainer_profile', args=[self.trainer1.id]))

        self.trainer1.refresh_from_db()
        self.assertEqual(self.trainer1.name, 'Vikram Sharma Senior')
        self.assertEqual(self.trainer1.salary, Decimal('42000.00'))
        self.assertEqual(self.trainer1.time_slot, 'Evening 4:00 PM - 10:00 PM')
