
import logging
from datetime import date, timedelta
from django.core.management.base import BaseCommand
from django.db.models import F
from apps.members.models import MembershipHistory
from apps.whatsapp.services import WhatsAppService

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = "Sends membership expiry reminders to members."

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simulate sending reminders without actually sending them or updating the database.',
        )

    def handle(self, *args, **options):
        today = date.today()
        dry_run = options['dry_run']
        if dry_run:
            self.stdout.write(self.style.WARNING(f"Running in --dry-run mode for: {today}"))
        else:
            self.stdout.write(f"Running membership expiry reminders for: {today}")

        active_memberships = MembershipHistory.objects.filter(
            status='active',
            is_deleted=False
        ).select_related('member', 'gym', 'plan')

        if not active_memberships.exists():
            self.stdout.write("No active memberships to process.")
            return

        total_sent = 0
        service = WhatsAppService()

        for membership in active_memberships:
            member = membership.member
            gym = membership.gym
            end_date = membership.get_end_date()
            days_until_expiry = (end_date - today).days

            if not member.mobile_number:
                self.stderr.write(f"Skipping member {member.name} due to missing mobile number.")
                continue

            # Check if gym has WhatsApp messaging enabled
            if not gym.whatsapp_enabled:
                self.stdout.write(f"Skipping member {member.name}: WhatsApp disabled for gym '{gym.name}'.")
                continue

            try:
                # 4-day reminder
                if days_until_expiry == 4 and not membership.reminder_4_days_sent:
                    if dry_run:
                        self.stdout.write(f"(Dry-run) Would send 4-day reminder to {member.name}")
                        total_sent += 1
                    else:
                        result = service.send_membership_expiring_soon(
                            request=None, to_number=member.mobile_number, name=member.name,
                            plan_name=membership.plan.title, expiry_date=end_date.strftime('%d/%m/%Y'),
                            gym_name=gym.name, gym_contact_number=gym.phone, gym_logo_url=gym.logo.url if gym.logo else None
                        )
                        if result.get("success"):
                            total_sent += 1
                            membership.reminder_4_days_sent = True
                            self.stdout.write(self.style.SUCCESS(f"Successfully sent 4-day reminder to {member.name}"))
                        else:
                            self.stderr.write(f"Failed to send 4-day reminder to {member.name}: {result.get('error')}")

                # 2-day reminder
                elif days_until_expiry == 2 and not membership.reminder_2_days_sent:
                    if dry_run:
                        self.stdout.write(f"(Dry-run) Would send 2-day reminder to {member.name}")
                        total_sent += 1
                    else:
                        result = service.send_membership_expiring_soon(
                            request=None, to_number=member.mobile_number, name=member.name,
                            plan_name=membership.plan.title, expiry_date=end_date.strftime('%d/%m/%Y'),
                            gym_name=gym.name, gym_contact_number=gym.phone, gym_logo_url=gym.logo.url if gym.logo else None
                        )
                        if result.get("success"):
                            total_sent += 1
                            membership.reminder_2_days_sent = True
                            self.stdout.write(self.style.SUCCESS(f"Successfully sent 2-day reminder to {member.name}"))
                        else:
                            self.stderr.write(f"Failed to send 2-day reminder to {member.name}: {result.get('error')}")

                # Expiry notification
                elif days_until_expiry <= 0 and not membership.expiry_notification_sent:
                    if dry_run:
                        self.stdout.write(f"(Dry-run) Would send expiry notification to {member.name}")
                        total_sent += 1
                    else:
                        result = service.send_membership_expired(
                            request=None, to_number=member.mobile_number, name=member.name,
                            plan_name=membership.plan.title, expiry_date=end_date.strftime('%d/%m/%Y'),
                            gym_name=gym.name, gym_contact_number=gym.phone, gym_logo_url=gym.logo.url if gym.logo else None
                        )
                        if result.get("success"):
                            total_sent += 1
                            membership.expiry_notification_sent = True
                            self.stdout.write(self.style.SUCCESS(f"Successfully sent expiry notification to {member.name}"))
                        else:
                            self.stderr.write(f"Failed to send expiry notification to {member.name}: {result.get('error')}")
                
                if not dry_run:
                    membership.save()

            except Exception as e:
                self.stderr.write(f"An error occurred while processing membership {membership.id}: {e}")

        self.stdout.write(f"Finished sending reminders. Total sent: {total_sent}")