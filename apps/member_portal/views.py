from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse
from datetime import timedelta
from functools import wraps
from django.db.models import Sum, F

from apps.members.models import Member, MembershipHistory, PersonalTrainer, AssignDietPlan, AssignWorkoutPlan
from apps.attendance.models import MemberAttendance
from apps.billing.models import Payment
from apps.management.models import DietPlan, WorkoutPlan


def member_required(view_func):
    """
    Decorator ensuring only authenticated gym members can access the member portal.
    """
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if hasattr(request.user, 'member_profile') and request.user.member_profile.gym:
            request.member = request.user.member_profile
            request.gym = request.member.gym
            return view_func(request, *args, **kwargs)
        messages.error(request, 'Access restricted to Gym Members only.')
        return redirect('login')
    return _wrapped


@never_cache
@member_required
def member_dashboard(request):
    member = request.member
    gym = request.gym
    today = timezone.localdate()

    # 1. Membership Plan details
    latest_membership = member.latest_membership
    end_date = latest_membership.get_end_date() if latest_membership else None
    days_left = (end_date - today).days if end_date and end_date >= today else 0
    is_active = member.current_status == 'Active'

    # Auto-dispatch real-time in-app notification if plan is expiring or expired (with 24h deduplication)
    if latest_membership:
        if end_date and end_date < today:
            try:
                from apps.superadmin.notifications import notify_membership_expired
                notify_membership_expired(member=member, history=latest_membership)
            except Exception:
                pass
        elif 0 <= days_left <= 4:
            try:
                from apps.superadmin.notifications import notify_membership_expiring
                notify_membership_expiring(member=member, history=latest_membership, days_left=days_left)
            except Exception:
                pass

    # 2. Attendance & Workout Session Tracking
    active_attendance = MemberAttendance.objects.filter(
        member=member,
        check_out_time__isnull=True
    ).order_by('-check_in_time').first()

    today_records = MemberAttendance.objects.filter(
        member=member,
        check_in_time__date=today
    ).order_by('-check_in_time')

    latest_today_attendance = today_records.first()

    # Calculate cumulative workout time today
    today_seconds = 0
    for rec in today_records:
        if rec.check_out_time:
            today_seconds += int((rec.check_out_time - rec.check_in_time).total_seconds())
        else:
            today_seconds += int((timezone.now() - rec.check_in_time).total_seconds())

    today_hours = today_seconds // 3600
    today_minutes = (today_seconds % 3600) // 60
    today_duration_str = f"{today_hours}h {today_minutes}m" if today_seconds > 0 else "0m"

    current_month_checkins = MemberAttendance.objects.filter(
        member=member,
        check_in_time__year=today.year,
        check_in_time__month=today.month
    ).count()

    recent_checkins = MemberAttendance.objects.filter(
        member=member
    ).order_by('-check_in_time')[:5]

    # 3. Assigned Plans
    assigned_workout = AssignWorkoutPlan.objects.filter(
        member=member
    ).select_related('workout_plan').order_by('-id').first()

    assigned_diet = AssignDietPlan.objects.filter(
        member=member
    ).select_related('diet_plan').order_by('-id').first()

    # 4. Personal Trainer
    pt_assignment = PersonalTrainer.objects.filter(
        member=member, status='active'
    ).select_related('trainer').first()

    pt_end_date = pt_assignment.get_end_date() if pt_assignment else None
    pt_days_left = (pt_end_date - today).days if pt_end_date and pt_end_date >= today else 0

    # 5. Financial Dues & Latest Payments
    due_amount = MembershipHistory.objects.filter(
        member=member, status='active'
    ).aggregate(total_due=Sum(F('total_amount') - F('paid_amount')))['total_due'] or 0

    recent_payments = Payment.objects.filter(
        member=member
    ).order_by('-payment_date')[:5]

    context = {
        'member': member,
        'gym': gym,
        'latest_membership': latest_membership,
        'end_date': end_date,
        'days_left': days_left,
        'is_active': is_active,
        'active_attendance': active_attendance,
        'is_checked_in': active_attendance is not None,
        'today_records': today_records,
        'today_duration_str': today_duration_str,
        'current_month_checkins': current_month_checkins,
        'today_attendance': latest_today_attendance,
        'recent_checkins': recent_checkins,
        'assigned_workout': assigned_workout,
        'assigned_diet': assigned_diet,
        'pt_assignment': pt_assignment,
        'pt_end_date': pt_end_date,
        'pt_days_left': pt_days_left,
        'due_amount': due_amount,
        'recent_payments': recent_payments,
    }
    return render(request, 'portal/member/dashboard.html', context)


@never_cache
@member_required
def member_attendance_action(request):
    """
    Dedicated action view for member self-attendance (Gym Check In & Check Out).
    Supports standard POST and AJAX JSON calls.
    """
    if request.method != 'POST':
        return redirect('member_portal:dashboard')

    member = request.member
    gym = request.gym
    action = request.POST.get('action', '').strip().lower()
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.POST.get('format') == 'json'
    today = timezone.localdate()

    # Automatically close any dangling unclosed check-ins from previous days
    stale_records = MemberAttendance.objects.filter(
        member=member,
        check_out_time__isnull=True,
        check_in_time__date__lt=today
    )
    for stale in stale_records:
        stale.check_out_time = stale.check_in_time + timedelta(hours=2)
        stale.status = 'outside'
        stale.save()

    active_record = MemberAttendance.objects.filter(
        member=member,
        check_out_time__isnull=True
    ).order_by('-check_in_time').first()

    if action == 'checkin':
        # Verify active membership
        if member.current_status != 'Active':
            msg = f"Cannot check in: Your membership is currently {member.current_status}. Please visit the front desk to renew."
            if is_ajax:
                return JsonResponse({'status': 'error', 'message': msg})
            messages.error(request, msg)
            return redirect('member_portal:dashboard')

        if active_record:
            time_str = timezone.localtime(active_record.check_in_time).strftime('%I:%M %p')
            msg = f"You are already checked in since {time_str}."
            if is_ajax:
                return JsonResponse({'status': 'error', 'message': msg})
            messages.warning(request, msg)
            return redirect('member_portal:dashboard')

        record = MemberAttendance.objects.create(
            member=member,
            gym=gym,
            check_in_time=timezone.now(),
            status='inside'
        )
        time_str = timezone.localtime(record.check_in_time).strftime('%I:%M %p')
        msg = f"Gym check-in successful at {time_str}! Have a great workout."
        if is_ajax:
            return JsonResponse({
                'status': 'success',
                'message': msg,
                'check_in_time': time_str,
                'is_checked_in': True
            })
        messages.success(request, msg)
        return redirect('member_portal:dashboard')

    elif action == 'checkout':
        if not active_record:
            msg = "No active check-in found to check out from."
            if is_ajax:
                return JsonResponse({'status': 'error', 'message': msg})
            messages.warning(request, msg)
            return redirect('member_portal:dashboard')

        active_record.check_out_time = timezone.now()
        active_record.status = 'outside'
        active_record.save()

        duration_str = active_record.duration or '0m'
        time_str = timezone.localtime(active_record.check_out_time).strftime('%I:%M %p')
        msg = f"Checked out successfully at {time_str}. Workout completed: {duration_str}."
        if is_ajax:
            return JsonResponse({
                'status': 'success',
                'message': msg,
                'check_out_time': time_str,
                'duration': duration_str,
                'is_checked_in': False
            })
        messages.success(request, msg)
        return redirect('member_portal:dashboard')

    else:
        msg = "Invalid attendance action requested."
        if is_ajax:
            return JsonResponse({'status': 'error', 'message': msg})
        messages.error(request, msg)
        return redirect('member_portal:dashboard')


@never_cache
@member_required
def member_attendance_view(request):
    member = request.member
    gym = request.gym
    today = timezone.localdate()

    all_attendance = MemberAttendance.objects.filter(
        member=member
    ).order_by('-check_in_time')

    total_days = all_attendance.count()
    this_month_count = all_attendance.filter(
        check_in_time__year=today.year,
        check_in_time__month=today.month
    ).count()

    active_attendance = MemberAttendance.objects.filter(
        member=member,
        check_out_time__isnull=True
    ).order_by('-check_in_time').first()

    context = {
        'member': member,
        'gym': gym,
        'all_attendance': all_attendance,
        'attendance_logs': all_attendance,
        'active_attendance': active_attendance,
        'is_checked_in': active_attendance is not None,
        'total_days': total_days,
        'this_month_count': this_month_count,
    }
    return render(request, 'portal/member/attendance.html', context)


@never_cache
@member_required
def member_workout_view(request):
    member = request.member
    gym = request.gym

    assigned_workout = AssignWorkoutPlan.objects.filter(
        member=member
    ).select_related('workout_plan').order_by('-id').first()

    workout_plan = assigned_workout.workout_plan if assigned_workout else None

    context = {
        'member': member,
        'gym': gym,
        'assigned_workout': assigned_workout,
        'workout_plan': workout_plan,
    }
    return render(request, 'portal/member/workout.html', context)


@never_cache
@member_required
def member_diet_view(request):
    member = request.member
    gym = request.gym

    assigned_diet = AssignDietPlan.objects.filter(
        member=member
    ).select_related('diet_plan').order_by('-id').first()

    diet_plan = assigned_diet.diet_plan if assigned_diet else None

    context = {
        'member': member,
        'gym': gym,
        'assigned_diet': assigned_diet,
        'diet_plan': diet_plan,
    }
    return render(request, 'portal/member/diet.html', context)


@never_cache
@member_required
def member_billing_view(request):
    member = request.member
    gym = request.gym

    payments = Payment.objects.filter(
        member=member
    ).order_by('-payment_date')

    histories = MembershipHistory.objects.filter(
        member=member
    ).select_related('plan').order_by('-membership_start_date')

    due_amount = histories.filter(status='active').aggregate(
        total_due=Sum(F('total_amount') - F('paid_amount'))
    )['total_due'] or 0

    context = {
        'member': member,
        'gym': gym,
        'payments': payments,
        'histories': histories,
        'due_amount': due_amount,
    }
    return render(request, 'portal/member/billing.html', context)


@never_cache
@member_required
def member_profile_view(request):
    member = request.member
    gym = request.gym

    if request.method == 'POST' and 'change_password' in request.POST:
        new_pwd = request.POST.get('new_password', '').strip()
        confirm_pwd = request.POST.get('confirm_password', '').strip()
        if len(new_pwd) < 6:
            messages.error(request, 'Password must be at least 6 characters long.')
        elif new_pwd != confirm_pwd:
            messages.error(request, 'Passwords do not match.')
        else:
            request.user.set_password(new_pwd)
            request.user.save()
            from django.contrib.auth import update_session_auth_hash
            update_session_auth_hash(request, request.user)
            messages.success(request, 'Password updated successfully!')
            return redirect('member_portal:profile')

    context = {
        'member': member,
        'gym': gym,
    }
    return render(request, 'portal/member/profile.html', context)


@never_cache
@member_required
def member_pt_view(request):
    member = request.member
    gym = request.gym
    today = timezone.localdate()

    # All PT history
    all_pt = PersonalTrainer.objects.filter(
        member=member, is_deleted=False
    ).select_related('trainer').order_by('-pt_start_date')

    active_pt = None
    pt_records = []
    for pt in all_pt:
        end_date = pt.get_end_date()
        is_current = (pt.status == 'active' and end_date >= today)
        days_left = (end_date - today).days if end_date >= today else 0
        total_days = (end_date - pt.pt_start_date).days or 1
        elapsed_days = (today - pt.pt_start_date).days if today >= pt.pt_start_date else 0
        progress_pct = min(100, max(0, int((elapsed_days / total_days) * 100)))

        item = {
            'record': pt,
            'trainer': pt.trainer,
            'end_date': end_date,
            'is_current': is_current,
            'days_left': days_left,
            'progress_pct': progress_pct,
            'due_amount': pt.due_amount,
        }
        pt_records.append(item)
        if is_current and not active_pt:
            active_pt = item

    total_pt_spent = all_pt.aggregate(total=Sum('paid_amount'))['total'] or 0
    total_pt_due = all_pt.filter(status='active').aggregate(total=Sum(F('total_amount') - F('paid_amount')))['total'] or 0
    total_pt_months = all_pt.aggregate(total=Sum('months'))['total'] or 0

    context = {
        'member': member,
        'gym': gym,
        'active_pt': active_pt,
        'pt_records': pt_records,
        'total_pt_spent': total_pt_spent,
        'total_pt_due': total_pt_due,
        'total_pt_months': total_pt_months,
    }
    return render(request, 'portal/member/personal_training.html', context)

