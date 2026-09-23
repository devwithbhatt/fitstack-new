from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Value, F
from django.db.models.functions import Concat
from apps.members.models import Member
from .models import MemberAttendance, TrainerAttendance, TrainerLeave, MemberLeave
from apps.trainers.models import Trainer
from apps.superadmin.models import Gym
from datetime import datetime, timedelta
from django.conf import settings
from django.core.serializers import serialize
import qrcode
from io import BytesIO
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
import random
import string
from django.contrib.auth.decorators import login_required
from apps.login.decorators import custom_permission_required


@login_required
@custom_permission_required('view_trainerattendance')
def trainer_attendance(request):
    gym = getattr(request, 'gym', None)
    today = timezone.now().date()

    if request.method == 'POST':
        action = request.POST.get('action')
        trainer_id = request.POST.get('trainer_id')
        quick_checkin_id = request.POST.get('quick_checkin_id')

        if quick_checkin_id:
            try:
                trainer = Trainer.objects.get(trainer_id=quick_checkin_id, is_active=True, gym=gym)
                TrainerAttendance.objects.create(trainer=trainer, check_in_time=timezone.now(), gym=gym)
                messages.success(request, f'{trainer.name} checked in successfully.')
            except Trainer.DoesNotExist:
                messages.error(request, 'Invalid or inactive Trainer ID.')
            return redirect('attendance:trainer_attendance')

        if trainer_id and action:
            trainer = get_object_or_404(Trainer, id=trainer_id, gym=gym)
            if action == 'checkin':
                TrainerAttendance.objects.create(trainer=trainer, check_in_time=timezone.now(), gym=gym)
                messages.success(request, f'{trainer.name} checked in successfully.')
            elif action == 'checkout':
                attendance_record = TrainerAttendance.objects.filter(trainer=trainer, check_in_time__date=today, check_out_time__isnull=True, gym=gym).first()
                if attendance_record:
                    attendance_record.check_out_time = timezone.now()
                    attendance_record.status = 'outside'
                    attendance_record.save()
                    messages.success(request, f'{trainer.name} checked out successfully.')
                else:
                    messages.error(request, 'Trainer is not checked in.')
            return redirect('attendance:trainer_attendance')

    # Stats
    checked_in_today = TrainerAttendance.objects.filter(check_in_time__date=today, gym=gym).values('trainer').distinct().count()
    currently_inside = TrainerAttendance.objects.filter(status='inside', check_in_time__date=today, gym=gym).count()
    total_trainers = Trainer.objects.filter(gym=gym).count()

    # Get all active trainers
    query = request.GET.get('q')
    if query:
        trainers_list = Trainer.objects.filter(
            (Q(name__icontains=query) |
            Q(phone__icontains=query)),
            gym=gym
        ).order_by('name')
    else:
        trainers_list = Trainer.objects.filter(gym=gym).order_by('name')

    paginator = Paginator(trainers_list, settings.ITEMS_PER_PAGE)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Get today's attendance records for the current page of trainers
    trainer_ids_on_page = [trainer.id for trainer in page_obj]
    attendance_today = TrainerAttendance.objects.filter(
        trainer_id__in=trainer_ids_on_page, 
        check_in_time__date=today,
        gym=gym
    ).order_by('-check_in_time')

    # Create a dictionary for quick lookup
    attendance_dict = {}
    for record in attendance_today:
        if record.trainer_id not in attendance_dict:
            attendance_dict[record.trainer_id] = []
        attendance_dict[record.trainer_id].append(record)

    # Combine trainer data with attendance status
    trainer_data = []
    for trainer in page_obj:
        records = attendance_dict.get(trainer.id, [])
        latest_record = records[0] if records else None
        trainer_data.append({
            'trainer': trainer,
            'records': sorted(records, key=lambda x: x.check_in_time, reverse=True) if records else [],
            'is_checked_in': latest_record and latest_record.status == 'inside'
        })

    context = {
        'today': today,
        'trainer_data': trainer_data,
        'page_obj': page_obj,
        'checked_in_today': checked_in_today,
        'currently_inside': currently_inside,
        'total_trainers': total_trainers,
    }
    return render(request, 'attendance/trainer_attendance.html', context)


def scan_attendance(request, gym_id):
    gym = get_object_or_404(Gym, gym_id=gym_id)

    if request.method == 'POST':
        reg_number = request.POST.get('reg_number', '').strip()
        attendance_code = request.POST.get('attendance_code', '').strip()

        if gym.attendance_code_required:
            if not all([reg_number, attendance_code]):
                messages.error(request, 'All fields are required.')
                return render(request, 'attendance/scan_attendance.html', {'gym': gym, 'gym_name': gym.name, 'form_data': request.POST})

            if gym.attendance_code != attendance_code:
                messages.error(request, 'Invalid attendance code.')
                return render(request, 'attendance/scan_attendance.html', {'gym': gym, 'gym_name': gym.name, 'form_data': request.POST})

            if gym.attendance_code_expiry and gym.attendance_code_expiry < timezone.now():
                messages.error(request, 'Attendance code has expired. Please scan the new code.')
                return render(request, 'attendance/scan_attendance.html', {'gym': gym, 'gym_name': gym.name, 'form_data': request.POST})
        else:
            if not reg_number:
                messages.error(request, 'Registered ID or Phone is required.')
                return render(request, 'attendance/scan_attendance.html', {'gym': gym, 'gym_name': gym.name, 'form_data': request.POST})

        member_id = request.POST.get('member_id')
        if member_id:
            try:
                member = Member.objects.get(id=member_id, gym=gym)
                handle_member_attendance(request, member, gym)
                return redirect('attendance:scan_attendance', gym_id=gym.gym_id)
            except Member.DoesNotExist:
                messages.error(request, 'Selected member not found.')
                return redirect('attendance:scan_attendance', gym_id=gym.gym_id)

        try:
            members = Member.objects.filter(
                Q(member_id__iexact=reg_number) | Q(mobile_number__iexact=reg_number),
                gym=gym
            )
            if members.count() == 1:
                member = members.first()
                handle_member_attendance(request, member, gym)
                return redirect('attendance:scan_attendance', gym_id=gym.gym_id)
            elif members.count() > 1:
                return render(request, 'attendance/scan_attendance.html', {
                    'gym': gym,
                    'gym_name': gym.name,
                    'members': members,
                    'reg_number': reg_number,
                    'attendance_code': attendance_code
                })

            # If no members found, try to find a trainer
            try:
                trainer = Trainer.objects.get(
                    Q(trainer_id__iexact=reg_number) | Q(phone__iexact=reg_number),
                    gym=gym
                )
                handle_trainer_attendance(request, trainer, gym)
                return redirect('attendance:scan_attendance', gym_id=gym.gym_id)
            except Trainer.DoesNotExist:
                messages.error(request, 'Member or Trainer not found with the provided details.')

        except Member.DoesNotExist:
             messages.error(request, 'Member or Trainer not found with the provided details.')

        return render(request, 'attendance/scan_attendance.html', {'gym': gym, 'gym_name': gym.name, 'form_data': request.POST})

    context = {
        'gym_name': gym.name,
        'gym': gym
    }
    return render(request, 'attendance/scan_attendance.html', context)


def handle_member_attendance(request, member, gym):
    today = timezone.now().date()
    existing_attendance = MemberAttendance.objects.filter(member=member, check_in_time__date=today, check_out_time__isnull=True).first()

    if existing_attendance:
        messages.warning(request, f'{member.name} is already checked in.')
    else:
        MemberAttendance.objects.create(member=member, check_in_time=timezone.now(), gym=gym)
        messages.success(request, f'Welcome, {member.name}! You have been successfully checked in.')


def handle_trainer_attendance(request, trainer, gym):
    today = timezone.now().date()
    thirty_minutes_ago = timezone.now() - timedelta(minutes=30)
    
    existing_attendance = TrainerAttendance.objects.filter(trainer=trainer, check_in_time__date=today, check_out_time__isnull=True).first()

    if existing_attendance:
        if existing_attendance.check_in_time > thirty_minutes_ago:
            messages.warning(request, f'{trainer.name} is already checked in. You can check out after 30 minutes.')
        else:
            existing_attendance.check_out_time = timezone.now()
            existing_attendance.status = 'outside'
            existing_attendance.save()
            messages.success(request, f'{trainer.name} checked out successfully.')
    else:
        TrainerAttendance.objects.create(trainer=trainer, check_in_time=timezone.now(), gym=gym)
        messages.success(request, f'Welcome, {trainer.name}! You have been successfully checked in.')


@login_required
@custom_permission_required('view_memberattendance')
def qr_code_view(request):
    gym = getattr(request, 'gym', None)
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'reset_code':
            if gym:
                # Generate a new 4-digit code
                new_code = ''.join(random.choices(string.digits, k=4))
                gym.attendance_code = new_code
                gym.attendance_code_expiry = timezone.now() + timedelta(minutes=5)
                gym.save(update_fields=['attendance_code', 'attendance_code_expiry'])
                messages.success(request, 'A new QR code has been generated.')
            return redirect('attendance:qr_code')
        
        elif action == 'mark_own_attendance':
            if request.user.is_authenticated and request.session.get('role') == 'trainer':
                try:
                    trainer = Trainer.objects.get(admin=request.user)
                    today = timezone.now().date()
                    
                    # Check if already checked in today
                    if not TrainerAttendance.objects.filter(trainer=trainer, check_in_time__date=today).exists():
                        TrainerAttendance.objects.create(trainer=trainer, gym=gym)
                        messages.success(request, 'Your attendance has been marked successfully.')
                    else:
                        messages.info(request, 'You have already marked your attendance today.')
                        
                except Trainer.DoesNotExist:
                    messages.error(request, 'Could not find a trainer profile linked to your account.')
            else:
                messages.error(request, 'You are not authorized to perform this action.')
            return redirect('attendance:qr_code')

    if gym:
        # Generate or reset attendance code and QR code if needed
        if not gym.attendance_code or not gym.qr_code or (gym.attendance_code_expiry and gym.attendance_code_expiry < timezone.now()):
            # Generate a new 4-digit code
            new_code = ''.join(random.choices(string.digits, k=4))
            gym.attendance_code = new_code
            gym.attendance_code_expiry = timezone.now() + timedelta(minutes=5)

            # Generate QR code
            qr_url = request.build_absolute_uri(reverse('attendance:scan_attendance', kwargs={'gym_id': gym.gym_id}))
            qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=4)
            qr.add_data(qr_url)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            
            buffer = BytesIO()
            img.save(buffer, format="PNG")
            file_name = f'gym_{gym.gym_id}_qr.png'
            
            # Delete old QR code if it exists
            if gym.qr_code and default_storage.exists(gym.qr_code.name):
                default_storage.delete(gym.qr_code.name)

            gym.qr_code.save(file_name, ContentFile(buffer.getvalue()), save=False)
            gym.save()

    context = {
        'gym': gym,
    }
    return render(request, 'attendance/qr_code.html', context)


@login_required
@custom_permission_required('view_memberattendance')
def member_attendance(request):
    gym = getattr(request, 'gym', None)
    today = timezone.now().date()

    # Generate or reset attendance code and QR code
    if gym:
        # Auto-checkout logic
        two_hours_ago = timezone.now() - timedelta(hours=2)
        MemberAttendance.objects.filter(
            gym=gym,
            check_out_time__isnull=True,
            check_in_time__lte=two_hours_ago
        ).update(
            check_out_time=F('check_in_time') + timedelta(hours=2),
            status='outside'
        )

        if not gym.attendance_code or (gym.attendance_code_expiry and gym.attendance_code_expiry < timezone.now()):
            # Generate a new 4-digit code
            new_code = ''.join(random.choices(string.digits, k=4))
            gym.attendance_code = new_code
            gym.attendance_code_expiry = timezone.now() + timedelta(minutes=5)

            # Generate QR code
            qr_url = request.build_absolute_uri(reverse('attendance:scan_attendance', kwargs={'gym_id': gym.gym_id}))
            qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=4)
            qr.add_data(qr_url)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            
            buffer = BytesIO()
            img.save(buffer, format="PNG")
            file_name = f'gym_{gym.gym_id}_qr.png'
            
            # Delete old QR code if it exists
            if gym.qr_code:
                if default_storage.exists(gym.qr_code.name):
                    default_storage.delete(gym.qr_code.name)

            gym.qr_code.save(file_name, ContentFile(buffer.getvalue()), save=False)
            gym.save()

    if request.method == 'POST':
        action = request.POST.get('action')
        member_id = request.POST.get('member_id')
        quick_checkin_id = request.POST.get('quick_checkin_id')

        if action == 'reset_code':
            if gym:
                # Generate a new 4-digit code
                new_code = ''.join(random.choices(string.digits, k=4))
                gym.attendance_code = new_code
                gym.attendance_code_expiry = timezone.now() + timedelta(minutes=5)
                gym.save()
                messages.success(request, 'Attendance code has been reset.')
            return redirect('attendance:member_attendance')


        if quick_checkin_id and action:
            member = Member.objects.filter(member_id=quick_checkin_id, gym=gym).first()
            if not member:
                messages.error(request, f'No member found with ID "{quick_checkin_id}". Please check the Membership ID and try again.')
            elif not member.is_active:
                messages.error(request, 'This member is not active and cannot be checked in.')
            elif action == 'checkin':
                if MemberAttendance.objects.filter(member=member, check_in_time__date=today, check_out_time__isnull=True, gym=gym).exists():
                    messages.warning(request, f'{member.name} is already checked in.')
                else:
                    MemberAttendance.objects.create(member=member, check_in_time=timezone.now(), gym=gym)
                    messages.success(request, f'{member.name} checked in successfully.')
            elif action == 'checkout':
                attendance_record = MemberAttendance.objects.filter(member=member, check_in_time__date=today, check_out_time__isnull=True, gym=gym).first()
                if attendance_record:
                    attendance_record.check_out_time = timezone.now()
                    attendance_record.status = 'outside'
                    attendance_record.save()
                    messages.success(request, f'{member.name} checked out successfully.')
                else:
                    messages.error(request, f'{member.name} is not currently checked in.')
            return redirect('attendance:member_attendance')

        if member_id and action:
            member = Member.objects.filter(id=member_id, gym=gym).first()
            if not member:
                messages.error(request, 'Member not found. Please refresh and try again.')
            elif action == 'checkin':
                MemberAttendance.objects.create(member=member, check_in_time=timezone.now(), gym=gym)
                messages.success(request, f'{member.name} checked in successfully.')
            elif action == 'checkout':
                attendance_record = MemberAttendance.objects.filter(member=member, check_in_time__date=today, check_out_time__isnull=True, gym=gym).first()
                if attendance_record:
                    attendance_record.check_out_time = timezone.now()
                    attendance_record.status = 'outside'
                    attendance_record.save()
                    messages.success(request, f'{member.name} checked out successfully.')
                else:
                    messages.error(request, f'{member.name} is not currently checked in.')
            return redirect('attendance:member_attendance')

    # Stats
    checked_in_today = MemberAttendance.objects.filter(check_in_time__date=today, gym=gym).values('member').distinct().count()
    currently_inside = MemberAttendance.objects.filter(status='inside', check_in_time__date=today, gym=gym).count()
    total_members = Member.objects.filter(gym=gym).count()

    # Get all active members
    query = request.GET.get('q')
    if query:
        members_list = Member.objects.annotate(full_name=Concat('first_name', Value(' '), 'last_name')).filter(
            (Q(full_name__icontains=query) |
            Q(mobile_number__icontains=query) |
            Q(member_id__icontains=query)),
            gym=gym
        ).order_by('first_name', 'last_name')
    else:
        members_list = Member.objects.filter(gym=gym).order_by('first_name', 'last_name')

    paginator = Paginator(members_list, settings.ITEMS_PER_PAGE)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Get today's attendance records for the current page of members
    member_ids_on_page = [member.id for member in page_obj]
    attendance_today = MemberAttendance.objects.filter(
        member_id__in=member_ids_on_page, 
        check_in_time__date=today,
        gym=gym
    ).order_by('-check_in_time')

    # Create a dictionary for quick lookup
    attendance_dict = {}
    for record in attendance_today:
        if record.member_id not in attendance_dict:
            attendance_dict[record.member_id] = []
        attendance_dict[record.member_id].append(record)

    # Combine member data with attendance status
    member_data = []
    for member in page_obj:
        records = attendance_dict.get(member.id, [])
        latest_record = records[0] if records else None
        member_data.append({
            'member': member,
            'records': sorted(records, key=lambda x: x.check_in_time, reverse=True) if records else [],
            'is_checked_in': latest_record and latest_record.status == 'inside'
        })

    context = {
        'today': today,
        'member_data': member_data,
        'page_obj': page_obj,
        'checked_in_today': checked_in_today,
        'currently_inside': currently_inside,
        'total_members': total_members,
        'gym': gym,
    }
    return render(request, 'attendance/member_attendance.html', context)


@login_required
@custom_permission_required('view_memberattendance')
def attendance_report(request):
    gym = getattr(request, 'gym', None)
    user_type = request.GET.get('user_type', 'member')
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')
    user_id = request.GET.get('user_id')

    # Default to today if no dates are provided
    today = timezone.now().date()
    start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date() if start_date_str else today
    end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date() if end_date_str else today
    
    records = None
    if user_type == 'member':
        records = MemberAttendance.objects.filter(
            check_in_time__date__range=[start_date, end_date],
            gym=gym
        ).select_related('member').order_by('-check_in_time')
        if user_id:
            records = records.filter(member__id=user_id)
    else: # trainer
        records = TrainerAttendance.objects.filter(
            check_in_time__date__range=[start_date, end_date],
            gym=gym
        ).select_related('trainer').order_by('-check_in_time')
        if user_id:
            records = records.filter(trainer__id=user_id)

    all_members = Member.objects.filter(gym=gym)
    all_trainers = Trainer.objects.filter(gym=gym)

    paginator = Paginator(records, settings.ITEMS_PER_PAGE) # 15 records per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'records': page_obj,
        'page_obj': page_obj,
        'user_type': user_type,
        'start_date': start_date,
        'end_date': end_date,
        'members': serialize('json', all_members),
        'trainers': serialize('json', all_trainers),
        'selected_user_id': int(user_id) if user_id else None,
    }
    return render(request, 'attendance/attendance_report.html', context)


# Leave Management Views
@login_required
@custom_permission_required('view_memberleave')
def leave_management(request):
    gym = getattr(request, 'gym', None)
    
    # Filter parameters
    status_filter = request.GET.get('status', 'all')
    type_filter = request.GET.get('type', 'all')
    search_query = request.GET.get('q', '')
    
    # Get all leave records
    trainer_leaves = TrainerLeave.objects.filter(gym=gym)
    member_leaves = MemberLeave.objects.filter(gym=gym)
    
    # Apply filters
    if status_filter != 'all':
        trainer_leaves = trainer_leaves.filter(status=status_filter)
        member_leaves = member_leaves.filter(status=status_filter)
    
    if type_filter != 'all':
        trainer_leaves = trainer_leaves.filter(leave_type=type_filter)
        member_leaves = member_leaves.filter(leave_type=type_filter)
    
    if search_query:
        trainer_leaves = trainer_leaves.filter(
            Q(trainer__name__icontains=search_query) |
            Q(reason__icontains=search_query)
        )
        member_leaves = member_leaves.annotate(
            member_full_name=Concat('member__first_name', Value(' '), 'member__last_name')
        ).filter(
            Q(member_full_name__icontains=search_query) |
            Q(member__first_name__icontains=search_query) |
            Q(member__last_name__icontains=search_query) |
            Q(reason__icontains=search_query)
        )
    
    # Order by created date descending
    trainer_leaves = trainer_leaves.order_by('-created_at')
    member_leaves = member_leaves.order_by('-created_at')
    
    # Statistics
    total_pending = (trainer_leaves.filter(status='pending').count() + 
                    member_leaves.filter(status='pending').count())
    total_approved = (trainer_leaves.filter(status='approved').count() + 
                     member_leaves.filter(status='approved').count())
    total_rejected = (trainer_leaves.filter(status='rejected').count() + 
                     member_leaves.filter(status='rejected').count())
    total_leaves = total_pending + total_approved + total_rejected
    
    # Combine and format all leaves for template
    all_leaves = []
    
    # Add trainer leaves
    for leave in trainer_leaves:
        all_leaves.append({
            'id': leave.id,
            'type': 'trainer',
            'person_name': leave.trainer.name,
            'person_type': 'Trainer',
            'start_date': leave.start_date,
            'end_date': leave.end_date,
            'duration_days': leave.duration_days,
            'reason': leave.reason,
            'status': leave.status,
            'leave_type': leave.get_leave_type_display(),
            'created_at': leave.created_at,
            'updated_at': leave.updated_at
        })
    
    # Add member leaves
    for leave in member_leaves:
        all_leaves.append({
            'id': leave.id,
            'type': 'member',
            'person_name': f"{leave.member.first_name} {leave.member.last_name}",
            'person_type': 'Member',
            'start_date': leave.start_date,
            'end_date': leave.end_date,
            'duration_days': leave.duration_days,
            'reason': leave.reason,
            'status': leave.status,
            'leave_type': leave.get_leave_type_display(),
            'created_at': leave.created_at,
            'updated_at': leave.updated_at
        })
    
    # Sort all leaves by created date descending
    all_leaves.sort(key=lambda x: x['created_at'], reverse=True)
    
    # Pagination
    paginator = Paginator(all_leaves, settings.ITEMS_PER_PAGE)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'total_pending': total_pending,
        'total_approved': total_approved,
        'total_rejected': total_rejected,
        'total_leaves': total_leaves,
        'status_filter': status_filter,
        'type_filter': type_filter,
        'search_query': search_query,
    }
    
    return render(request, 'attendance/leave_management.html', context)


@login_required
@custom_permission_required(['add_trainerleave', 'add_memberleave'])
def add_trainer_leave(request):
    gym = getattr(request, 'gym', None)
    
    if request.method == 'POST':
        trainer_id = request.POST.get('trainer_id')
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        leave_type = request.POST.get('leave_type')
        reason = request.POST.get('reason', '')
        
        try:
            trainer = Trainer.objects.get(id=trainer_id, gym=gym)
            TrainerLeave.objects.create(
                gym=gym,
                trainer=trainer,
                start_date=start_date,
                end_date=end_date,
                leave_type=leave_type,
                reason=reason
            )
            messages.success(request, 'Trainer leave added successfully!')
            return redirect('attendance:leave_management')
        except Trainer.DoesNotExist:
            messages.error(request, 'Trainer not found!')
    
    # Get all active trainers for the form
    trainers = Trainer.objects.filter(gym=gym, is_active=True).order_by('name')
    context = {
        'trainers': trainers,
        'leave_types': [
            ('sick', 'Sick Leave'),
            ('casual', 'Casual Leave'),
            ('earned', 'Earned Leave'),
            ('maternity', 'Maternity Leave'),
            ('paternity', 'Paternity Leave'),
            ('unpaid', 'Unpaid Leave'),
            ('other', 'Other')
        ]
    }
    return render(request, 'attendance/add_trainer_leave.html', context)


@login_required
@custom_permission_required(['add_memberleave', 'add_trainerleave'])
def add_member_leave(request):
    gym = getattr(request, 'gym', None)
    
    if request.method == 'POST':
        member_id = request.POST.get('member_id')
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        leave_type = request.POST.get('leave_type')
        reason = request.POST.get('reason', '')
        
        try:
            member = Member.objects.get(id=member_id, gym=gym)
            MemberLeave.objects.create(
                gym=gym,
                member=member,
                start_date=start_date,
                end_date=end_date,
                leave_type=leave_type,
                reason=reason
            )
            messages.success(request, 'Member leave added successfully!')
            return redirect('attendance:leave_management')
        except Member.DoesNotExist:
            messages.error(request, 'Member not found!')
    
    # Get all active members for the form
    members = Member.objects.filter(gym=gym, is_deleted=False).order_by('first_name', 'last_name')
    context = {
        'members': members,
        'leave_types': [
            ('sick', 'Sick Leave'),
            ('casual', 'Casual Leave'),
            ('medical', 'Medical Leave'),
            ('personal', 'Personal Leave'),
            ('other', 'Other')
        ]
    }
    return render(request, 'attendance/add_member_leave.html', context)


@login_required
@custom_permission_required(['change_memberleave', 'change_trainerleave'])
def update_leave_status(request, leave_type, leave_id, status):
    gym = getattr(request, 'gym', None)
    
    if status not in ['approved', 'rejected']:
        messages.error(request, 'Invalid status!')
        return redirect('attendance:leave_management')
    
    try:
        if leave_type == 'trainer':
            leave = get_object_or_404(TrainerLeave, id=leave_id, gym=gym)
        elif leave_type == 'member':
            leave = get_object_or_404(MemberLeave, id=leave_id, gym=gym)
        else:
            messages.error(request, 'Invalid leave type!')
            return redirect('attendance:leave_management')
        
        leave.status = status
        leave.save()
        messages.success(request, f'Leave {status} successfully!')
    except Exception as e:
        messages.error(request, f'Error updating leave status: {str(e)}')
    
    return redirect('attendance:leave_management')


@login_required
@custom_permission_required(['delete_memberleave', 'delete_trainerleave'])
def delete_leave(request, leave_type, leave_id):
    gym = getattr(request, 'gym', None)
    
    try:
        if leave_type == 'trainer':
            leave = get_object_or_404(TrainerLeave, id=leave_id, gym=gym)
        elif leave_type == 'member':
            leave = get_object_or_404(MemberLeave, id=leave_id, gym=gym)
        else:
            messages.error(request, 'Invalid leave type!')
            return redirect('attendance:leave_management')
        
        leave.delete()
        messages.success(request, 'Leave deleted successfully!')
    except Exception as e:
        messages.error(request, f'Error deleting leave: {str(e)}')
    
    return redirect('attendance:leave_management')