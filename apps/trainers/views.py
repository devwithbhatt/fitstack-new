from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Q
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from .models import Trainer
from .forms import TrainerForm

from django.contrib.auth.decorators import login_required
from apps.login.decorators import custom_permission_required
from django.views.decorators.cache import never_cache
from django.db import IntegrityError



@never_cache
@login_required(login_url='login')
@custom_permission_required('view_trainer')
def trainer_list(request):
    gym = getattr(request, 'gym', None)
    trainers_list = Trainer.objects.filter(gym=gym)

    query = request.GET.get('q')
    if query:
        trainers_list = trainers_list.filter(
            Q(name__icontains=query) |
            Q(email__icontains=query) |
            Q(phone__icontains=query) |
            Q(specialization__icontains=query)
        ).distinct()

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
            messages.success(request, 'Trainer updated successfully!')
            return redirect('trainer_list')
    else:
        form = TrainerForm(instance=trainer)
    return render(request, 'trainers/edit_trainer.html', {'form': form})

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
