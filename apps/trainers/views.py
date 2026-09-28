from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Q, Sum
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone

from .models import Trainer
from .forms import TrainerForm
from apps.members.models import PersonalTrainer
from apps.attendance.models import TrainerAttendance, TrainerLeave

from django.contrib.auth.decorators import login_required
from apps.login.decorators import custom_permission_required
from django.views.decorators.cache import never_cache
from django.db import IntegrityError



@never_cache
@login_required(login_url='login')
@custom_permission_required('view_trainer')
def trainer_list(request):
    gym = getattr(request, 'gym', None)
    trainers_list = Trainer.objects.filter(gym=gym).order_by('-id')

    query = request.GET.get('q')
    if query:
        trainers_list = trainers_list.filter(
            Q(name__icontains=query) |
            Q(email__icontains=query) |
            Q(phone__icontains=query) |
            Q(specialization__icontains=query)
        ).distinct()

    trainers_list = trainers_list.order_by('-id')
    paginator = Paginator(trainers_list, 10)  # Show 10 trainers per page
    page = request.GET.get('page')

    try:
        trainers = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        trainers = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        trainers = paginator.page(paginator.num_pages)

    return render(request, 'trainers/trainer_list.html', {'trainers': trainers})
    
@never_cache
@login_required(login_url='login')
@custom_permission_required('add_trainer')
def add_trainer(request):
    gym = getattr(request, 'gym', None)
    if request.method == 'POST':
        form = TrainerForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                trainer = form.save(commit=False)
                trainer.gym = gym
                trainer.save()

                # Provision Trainer User Account
                user, raw_password = trainer.create_or_update_user_account()
                request.session['registration_credentials'] = {
                    'account_type': 'Trainer',
                    'title': 'Trainer Registered Successfully!',
                    'name': trainer.name.strip(),
                    'id': trainer.trainer_id,
                    'username': trainer.trainer_id,
                    'mobile': trainer.phone or '',
                    'email': trainer.email or '',
                    'password': raw_password,
                    'gym_name': gym.name if gym else 'FitStack Gym',
                    'login_url': request.build_absolute_uri('/login/'),
                }

                messages.success(request, 'Trainer added successfully!')
                return redirect('trainer_list')
            except IntegrityError:
                form.add_error('email', 'A trainer with this email already exists.')
    else:
        form = TrainerForm()
    return render(request, 'trainers/add_trainer.html', {'form': form})

@never_cache
@login_required(login_url='login')
@custom_permission_required('view_trainer')
def trainer_profile(request, trainer_id):
    gym = getattr(request, 'gym', None)
    trainer = Trainer.objects.filter(id=trainer_id, gym=gym).first()
    if not trainer:
        messages.error(request, 'Trainer not found or has been removed.')
        return redirect('trainer_list')

    # Personal Training (PT) Clients
    pt_clients = PersonalTrainer.objects.select_related('member').filter(
        trainer=trainer, gym=gym, is_deleted=False
    ).order_by('-id')

    active_pt_clients = pt_clients.filter(status='active')
    expired_pt_clients = pt_clients.exclude(status='active')

    total_clients_count = pt_clients.count()
    active_clients_count = active_pt_clients.count()

    # Financial aggregations on PT clients
    total_pt_revenue = pt_clients.aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
    total_pt_paid = pt_clients.aggregate(paid=Sum('paid_amount'))['paid'] or Decimal('0.00')
    total_pt_due = total_pt_revenue - total_pt_paid

    # Monthly active PT client revenue estimate
    active_pt_monthly_earnings = sum(
        (client.trainer_fee / client.months) if client.months and client.trainer_fee else Decimal('0.00')
        for client in active_pt_clients
    )
    total_estimated_monthly_income = (trainer.salary or Decimal('0.00')) + active_pt_monthly_earnings

    # Attendance Records & Analytics
    attendance_records = TrainerAttendance.objects.filter(
        trainer=trainer, gym=gym
    ).order_by('-check_in_time')[:30]

    now = timezone.now()
    current_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_attendance = TrainerAttendance.objects.filter(
        trainer=trainer, gym=gym, check_in_time__gte=current_month_start
    )
    month_present_days = month_attendance.values('check_in_time__date').distinct().count()

    total_seconds = 0
    for rec in month_attendance:
        if rec.check_in_time and rec.check_out_time:
            total_seconds += int((rec.check_out_time - rec.check_in_time).total_seconds())
    month_total_hours = round(total_seconds / 3600, 1)

    latest_attendance = attendance_records.first()

    # Leave Records
    leave_records = TrainerLeave.objects.filter(
        trainer=trainer, gym=gym
    ).order_by('-start_date')
    approved_leaves = leave_records.filter(status='approved').count()
    pending_leaves = leave_records.filter(status='pending').count()
    rejected_leaves = leave_records.filter(status='rejected').count()

    # Tenure Calculation
    tenure_str = "Recently Joined"
    if trainer.joining_date:
        days_joined = (timezone.localdate() - trainer.joining_date).days
        years = days_joined // 365
        months = (days_joined % 365) // 30
        if years > 0 and months > 0:
            tenure_str = f"{years} yr {months} mos"
        elif years > 0:
            tenure_str = f"{years} yr{'s' if years > 1 else ''}"
        elif months > 0:
            tenure_str = f"{months} mo{'s' if months > 1 else ''}"
        elif days_joined > 0:
            tenure_str = f"{days_joined} days"
        else:
            tenure_str = "Joined Today"

    context = {
        'trainer': trainer,
        'pt_clients': pt_clients,
        'active_pt_clients': active_pt_clients,
        'expired_pt_clients': expired_pt_clients,
        'total_clients_count': total_clients_count,
        'active_clients_count': active_clients_count,
        'total_pt_revenue': total_pt_revenue,
        'total_pt_paid': total_pt_paid,
        'total_pt_due': total_pt_due,
        'active_pt_monthly_earnings': active_pt_monthly_earnings,
        'total_estimated_monthly_income': total_estimated_monthly_income,
        'attendance_records': attendance_records,
        'month_present_days': month_present_days,
        'month_total_hours': month_total_hours,
        'latest_attendance': latest_attendance,
        'leave_records': leave_records,
        'approved_leaves': approved_leaves,
        'pending_leaves': pending_leaves,
        'rejected_leaves': rejected_leaves,
        'tenure_str': tenure_str,
    }
    return render(request, 'trainers/trainer_profile.html', context)


@never_cache
@login_required(login_url='login')
@custom_permission_required('change_trainer')
def edit_trainer(request, trainer_id):
    gym = getattr(request, 'gym', None)
    trainer = Trainer.objects.filter(id=trainer_id, gym=gym).first()
    if not trainer:
        messages.error(request, 'Trainer not found.')
        return redirect('trainer_list')
    if request.method == 'POST':
        form = TrainerForm(request.POST, request.FILES, instance=trainer)
        if form.is_valid():
            form.save()
            if trainer.user:
                names = (trainer.name or '').strip().split(' ', 1)
                trainer.user.first_name = names[0]
                trainer.user.last_name = names[1] if len(names) > 1 else ''
                if trainer.email:
                    trainer.user.email = trainer.email
                trainer.user.save()
            messages.success(request, 'Trainer updated successfully!')
            return redirect('trainer_profile', trainer_id=trainer.id)
    else:
        form = TrainerForm(instance=trainer)
    return render(request, 'trainers/edit_trainer.html', {'form': form, 'trainer': trainer})

@never_cache
@login_required(login_url='login')
@require_POST
@custom_permission_required('delete_trainer')
def delete_trainer(request, trainer_id):
    gym = getattr(request, 'gym', None)
    trainer = Trainer.objects.filter(id=trainer_id, gym=gym).first()
    if not trainer:
        return JsonResponse({'status': 'error', 'message': 'Trainer not found.'}, status=404)
    try:
        trainer.delete()
        messages.success(request, 'Trainer has been deleted successfully.')
        return JsonResponse({'status': 'success', 'message': 'Trainer deleted successfully.'})
    except Exception as e:
        messages.error(request, f'An error occurred: {e}')
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@never_cache
@login_required(login_url='login')
@custom_permission_required('change_trainer')
def toggle_trainer_status(request, trainer_id):
    gym = getattr(request, 'gym', None)
    trainer = Trainer.objects.filter(id=trainer_id, gym=gym).first()
    if not trainer:
        messages.error(request, 'Trainer not found.')
        return redirect('trainer_list')
    trainer.is_active = not trainer.is_active
    trainer.save()
    messages.success(request, f"Trainer {trainer.name} has been marked as {'Active' if trainer.is_active else 'Inactive'}.")
    referer = request.META.get('HTTP_REFERER', '')
    if 'profile' in referer:
        return redirect('trainer_profile', trainer_id=trainer.id)
    return redirect('trainer_list')


@never_cache
@login_required(login_url='login')
@custom_permission_required('change_trainer')
@require_POST
def reset_trainer_password(request, trainer_id):
    gym = getattr(request, 'gym', None)
    trainer = Trainer.objects.filter(id=trainer_id, gym=gym).first()
    if not trainer:
        return JsonResponse({'status': 'error', 'message': 'Trainer not found.'}, status=404)
    
    custom_pwd = request.POST.get('new_password', '').strip()
    if not custom_pwd:
        import random
        phone_suffix = trainer.phone[-4:] if trainer.phone and len(trainer.phone) >= 4 else str(random.randint(1000, 9999))
        custom_pwd = f"Fit@{phone_suffix}"
        
    user, raw_pwd = trainer.create_or_update_user_account(raw_password=custom_pwd)
    
    login_url = request.build_absolute_uri('/login/')
    share_text = f"*FitStack Gym Password Reset*\n\nHi {trainer.name},\nYour trainer account password has been reset successfully.\n\n• *Username / ID:* {trainer.trainer_id}\n• *Mobile:* {trainer.phone or 'N/A'}\n• *New Password:* {raw_pwd}\n• *Login URL:* {login_url}\n\nYou can log in using your Mobile Number or Username."
    
    return JsonResponse({
        'status': 'success',
        'message': f'Password for {trainer.name} has been reset successfully!',
        'name': trainer.name,
        'trainer_id': trainer.trainer_id,
        'username': user.username,
        'mobile': trainer.phone,
        'new_password': raw_pwd,
        'share_text': share_text,
    })
