from django.utils import timezone
from django.db.models import Q
from django.contrib.auth.models import User
from .models import PlatformNotification, NotificationUserStatus, Gym, GymAdmin
from apps.login.models import SubAdmin
from apps.members.models import Member
from apps.trainers.models import Trainer


def get_user_context(user):
    """
    Resolves the gym and role for any user in the system.
    Returns dict: {'role': str, 'gym': Gym or None}
    """
    if not user or not user.is_authenticated:
        return {'role': 'anonymous', 'gym': None}

    if user.is_superuser:
        return {'role': 'superadmin', 'gym': None}

    # 1. Gym Admin
    ga = GymAdmin.objects.filter(user=user).select_related('gym').first()
    if ga:
        return {'role': 'gym_admin', 'gym': ga.gym}

    # 2. Sub Admin / Staff
    sa = SubAdmin.objects.filter(user=user).select_related('gym').first()
    if sa:
        return {'role': 'staff', 'gym': sa.gym}

    # 3. Trainer
    trainer = getattr(user, 'trainer_profile', None)
    if trainer and trainer.gym:
        return {'role': 'trainer', 'gym': trainer.gym}

    # 4. Member
    member = getattr(user, 'member_profile', None)
    if member and member.gym:
        return {'role': 'member', 'gym': member.gym}

    return {'role': 'user', 'gym': None}


def get_user_applicable_notifications_qs(user):
    """
    Returns the QuerySet of active, unexpired notifications targeted to the given user.
    """
    if not user or not user.is_authenticated:
        return PlatformNotification.objects.none()

    now = timezone.now()
    base_qs = PlatformNotification.objects.filter(
        is_active=True
    ).filter(
        Q(expires_at__isnull=True) | Q(expires_at__gt=now)
    )

    # Superadmin sees all notifications authored or targeted to system
    if user.is_superuser:
        return base_qs

    ctx = get_user_context(user)
    role = ctx['role']
    gym = ctx['gym']

    # Build Q filters based on audience matching
    q_filter = Q(target_type='all') | Q(target_type='specific_user', target_user=user)

    is_gym_staff = role in ('gym_admin', 'staff')
    is_member = role == 'member'

    # Broad categories
    if is_gym_staff:
        q_filter |= Q(target_type='all_gyms')
    if is_member:
        q_filter |= Q(target_type='all_members')

    # Gym-specific categories
    if gym:
        q_filter |= Q(target_type='specific_gym', target_gym=gym)
        if is_gym_staff:
            q_filter |= Q(target_type='specific_gym_staff', target_gym=gym)
        if is_member:
            q_filter |= Q(target_type='specific_gym_members', target_gym=gym)

    return base_qs.filter(q_filter).distinct()


def get_unread_notifications_count(user):
    """
    Returns the number of unread notifications for the user.
    """
    if not user or not user.is_authenticated:
        return 0

    qs = get_user_applicable_notifications_qs(user)
    # Exclude those marked read
    read_ids = NotificationUserStatus.objects.filter(
        user=user,
        is_read=True
    ).values_list('notification_id', flat=True)

    return qs.exclude(id__in=read_ids).count()


def get_recent_notifications(user, limit=5):
    """
    Returns list of recent notifications annotated with user read state.
    """
    if not user or not user.is_authenticated:
        return []

    qs = list(get_user_applicable_notifications_qs(user)[:limit])
    if not qs:
        return []

    statuses = {
        s.notification_id: s
        for s in NotificationUserStatus.objects.filter(user=user, notification__in=qs)
    }

    result = []
    for n in qs:
        status = statuses.get(n.id)
        is_read = status.is_read if status else False
        result.append({
            'id': n.id,
            'title': n.title,
            'message': n.message,
            'notification_type': n.notification_type,
            'image_url': n.image.url if n.image else None,
            'action_label': n.action_label,
            'action_url': n.action_url,
            'show_popup': n.show_popup,
            'created_at': n.created_at,
            'is_read': is_read,
        })
    return result


def get_active_popup_for_user(user, session=None):
    """
    Returns the active popup announcement that the user is eligible to see based on frequency settings:
    - 'once': Shown once until dismissed.
    - 'every_login': Shown once per login/session until expired.
    - 'fixed_count': Shown up to max_popup_views times until expired.
    - 'until_expired': Shown on every login session until expired.
    """
    if not user or not user.is_authenticated:
        return None

    qs = get_user_applicable_notifications_qs(user).filter(show_popup=True)
    if not qs.exists():
        return None

    seen_session_ids = set()
    if session is not None:
        seen_session_ids = set(session.get('seen_popup_ids', []))

    user_statuses = {
        s.notification_id: s
        for s in NotificationUserStatus.objects.filter(user=user, notification__in=qs)
    }

    eligible_popup = None
    for popup in qs:
        status = user_statuses.get(popup.id)
        view_count = status.popup_view_count if status else 0
        acknowledged = status.popup_acknowledged if status else False

        # Session check to avoid annoying user on every second page reload in same session
        if popup.id in seen_session_ids:
            continue

        freq = popup.popup_frequency or 'once'

        if freq == 'once':
            if not acknowledged:
                eligible_popup = popup
                break

        elif freq == 'every_login' or freq == 'until_expired':
            # Display once per login session until expired (qs already checks not expired)
            eligible_popup = popup
            break

        elif freq == 'fixed_count':
            max_views = popup.max_popup_views or 1
            if view_count < max_views:
                eligible_popup = popup
                break

    if not eligible_popup:
        return None

    # Track in session so it doesn't pop up again on immediate page refresh in the same session
    if session is not None:
        current_seen = list(session.get('seen_popup_ids', []))
        if eligible_popup.id not in current_seen:
            current_seen.append(eligible_popup.id)
            session['seen_popup_ids'] = current_seen
            if hasattr(session, 'modified'):
                session.modified = True

    return {
        'id': eligible_popup.id,
        'title': eligible_popup.title,
        'message': eligible_popup.message,
        'notification_type': eligible_popup.notification_type,
        'image_url': eligible_popup.image.url if eligible_popup.image else None,
        'popup_frequency': eligible_popup.popup_frequency,
        'is_dismissible': eligible_popup.is_dismissible,
        'action_label': eligible_popup.action_label,
        'action_url': eligible_popup.action_url,
        'created_at': eligible_popup.created_at.strftime('%d %b %Y, %I:%M %p'),
    }


def acknowledge_popup(user, notification_id, session=None):
    """
    Records popup view / dismissal and updates frequency counters.
    """
    if not user or not user.is_authenticated:
        return False

    now = timezone.now()
    notification = PlatformNotification.objects.filter(id=notification_id).first()
    if not notification:
        return False

    status, created = NotificationUserStatus.objects.get_or_create(
        user=user,
        notification=notification,
        defaults={
            'popup_acknowledged': False,
            'popup_view_count': 1,
            'popup_last_shown_at': now,
            'is_read': True,
            'read_at': now,
        }
    )

    if not created:
        status.popup_view_count = (status.popup_view_count or 0) + 1
        status.popup_last_shown_at = now
        status.is_read = True
        if not status.read_at:
            status.read_at = now

    freq = notification.popup_frequency or 'once'
    if freq == 'once':
        status.popup_acknowledged = True
        status.popup_acknowledged_at = now
    elif freq == 'fixed_count':
        max_views = notification.max_popup_views or 1
        if status.popup_view_count >= max_views:
            status.popup_acknowledged = True
            status.popup_acknowledged_at = now

    status.save()

    if session is not None:
        current_seen = list(session.get('seen_popup_ids', []))
        if notification_id not in current_seen:
            current_seen.append(notification_id)
            session['seen_popup_ids'] = current_seen
            if hasattr(session, 'modified'):
                session.modified = True

    return True


def mark_notification_as_read(user, notification_id):
    """
    Marks a notification as read by the user.
    """
    if not user or not user.is_authenticated:
        return False

    now = timezone.now()
    status, created = NotificationUserStatus.objects.get_or_create(
        user=user,
        notification_id=notification_id,
        defaults={'is_read': True, 'read_at': now}
    )
    if not created and not status.is_read:
        status.is_read = True
        status.read_at = now
        status.save(update_fields=['is_read', 'read_at', 'updated_at'])

    return True


def mark_all_notifications_as_read(user):
    """
    Marks all currently applicable notifications as read.
    """
    if not user or not user.is_authenticated:
        return 0

    qs = get_user_applicable_notifications_qs(user)
    now = timezone.now()
    updated_count = 0

    for n in qs:
        status, created = NotificationUserStatus.objects.get_or_create(
            user=user,
            notification=n,
            defaults={'is_read': True, 'read_at': now}
        )
        if not created and not status.is_read:
            status.is_read = True
            status.read_at = now
            status.save(update_fields=['is_read', 'read_at', 'updated_at'])
            updated_count += 1
        elif created:
            updated_count += 1

    return updated_count


def estimate_audience(target_type, target_gym_id=None, target_user_id=None):
    """
    Computes an estimated recipient count breakdown for previewing in the compose UI.
    """
    result = {
        'total': 0,
        'admins': 0,
        'staff': 0,
        'members': 0,
        'trainers': 0,
        'description': '',
    }

    if target_type == 'specific_user':
        if target_user_id:
            try:
                u = User.objects.get(id=target_user_id)
                result['total'] = 1
                result['description'] = f"1 individual user ({u.username})"
            except User.DoesNotExist:
                result['description'] = "User not found"
        else:
            result['description'] = "Select an individual recipient"
        return result

    gym = None
    if target_gym_id:
        gym = Gym.objects.filter(id=target_gym_id).first()

    if target_type == 'all':
        admin_count = GymAdmin.objects.count()
        staff_count = SubAdmin.objects.count()
        member_count = Member.objects.filter(is_deleted=False).count()
        trainer_count = Trainer.objects.filter(is_active=True).count()
        total = admin_count + staff_count + member_count + trainer_count
        result.update({
            'total': total,
            'admins': admin_count,
            'staff': staff_count,
            'members': member_count,
            'trainers': trainer_count,
            'description': f"All platform users across all gyms (~{total} recipients)",
        })

    elif target_type == 'all_gyms':
        admin_count = GymAdmin.objects.count()
        staff_count = SubAdmin.objects.count()
        total = admin_count + staff_count
        result.update({
            'total': total,
            'admins': admin_count,
            'staff': staff_count,
            'description': f"All gym owners, administrators and staff (~{total} recipients)",
        })

    elif target_type == 'all_members':
        member_count = Member.objects.filter(is_deleted=False).count()
        result.update({
            'total': member_count,
            'members': member_count,
            'description': f"All gym members across the entire platform (~{member_count} recipients)",
        })

    elif target_type in ('specific_gym', 'specific_gym_staff', 'specific_gym_members'):
        if not gym:
            result['description'] = "Select a specific gym"
            return result

        admin_count = GymAdmin.objects.filter(gym=gym).count()
        staff_count = SubAdmin.objects.filter(gym=gym).count()
        member_count = Member.objects.filter(gym=gym, is_deleted=False).count()
        trainer_count = Trainer.objects.filter(gym=gym, is_active=True).count()

        if target_type == 'specific_gym':
            total = admin_count + staff_count + member_count + trainer_count
            result.update({
                'total': total,
                'admins': admin_count,
                'staff': staff_count,
                'members': member_count,
                'trainers': trainer_count,
                'description': f"Everyone at {gym.name} (~{total} recipients)",
            })
        elif target_type == 'specific_gym_staff':
            total = admin_count + staff_count
            result.update({
                'total': total,
                'admins': admin_count,
                'staff': staff_count,
                'description': f"Admins and staff of {gym.name} (~{total} recipients)",
            })
        elif target_type == 'specific_gym_members':
            result.update({
                'total': member_count,
                'members': member_count,
                'description': f"Members of {gym.name} (~{member_count} recipients)",
            })

    return result
