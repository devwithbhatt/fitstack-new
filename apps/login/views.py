from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from apps.superadmin.models import GymAdmin
from django.views.decorators.cache import never_cache
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User, Permission
from functools import wraps
from django.contrib.contenttypes.models import ContentType
from django.http import JsonResponse
from .models import SubAdmin, ROLE_CHOICES
from .models import SubAdminPermission


def gym_admin_required(view_func):
    """
    Ensures that only GymAdmins or Superusers can access sub-admin management.
    Sub-admins are forbidden from managing staff accounts.
    """
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if request.user.is_superuser or hasattr(request.user, 'gymadmin'):
            return view_func(request, *args, **kwargs)
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({
                'status': 'error',
                'code': 'permission_denied',
                'message': 'Access Restricted: Only Gym Administrators have permission to manage staff sub-admin accounts.'
            }, status=403)
        messages.warning(
            request,
            'Access Restricted: Only Gym Administrators have permission to manage staff sub-admin accounts.',
            extra_tags='permission_denied'
        )
        return redirect('dashboard')
    return _wrapped


@never_cache
def superadmin_login(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None and user.is_superuser:
            login(request, user)
            request.session['role'] = 'superadmin'
            return redirect('superadmin:dashboard')
        else:
            messages.error(request, 'Invalid username or password for superadmin.')
    return render(request, 'login/superadmin_login.html')

def _resolve_identifier_to_username(identifier):
    """
    Resolve a login identifier (mobile number, email, or username) to a
    Django ``auth.User`` username so that ``authenticate()`` can be called.

    Lookup order:
      1. Member by mobile_number  → member_id (Django username)
      2. Member by email          → member_id (Django username)
      3. Trainer by phone         → trainer_id (Django username)
      4. Trainer by email         → trainer_id (Django username)
      5. SubAdmin by phone_number → user.username
      6. GymAdmin by email        → user.username
      7. Direct User.username match (passthrough)
    """
    if not identifier:
        return identifier

    identifier = identifier.strip()

    # --- Member lookup ---
    try:
        from apps.members.models import Member
        # by mobile number
        member = Member.objects.filter(mobile_number=identifier).select_related('user').first()
        if member and member.user:
            return member.user.username
        # by email
        member = Member.objects.filter(email__iexact=identifier).select_related('user').first()
        if member and member.user:
            return member.user.username
    except Exception:
        pass

    # --- Trainer lookup ---
    try:
        from apps.trainers.models import Trainer
        # by phone
        trainer = Trainer.objects.filter(phone=identifier).select_related('user').first()
        if trainer and trainer.user:
            return trainer.user.username
        # by email
        trainer = Trainer.objects.filter(email__iexact=identifier).select_related('user').first()
        if trainer and trainer.user:
            return trainer.user.username
    except Exception:
        pass

    # --- SubAdmin lookup by phone ---
    try:
        sub_admin = SubAdmin.objects.filter(phone_number=identifier).select_related('user').first()
        if sub_admin and sub_admin.user:
            return sub_admin.user.username
    except Exception:
        pass

    # --- GymAdmin lookup by email ---
    try:
        gym_admin = GymAdmin.objects.filter(user__email__iexact=identifier).select_related('user').first()
        if gym_admin and gym_admin.user:
            return gym_admin.user.username
    except Exception:
        pass

    # --- Fallback: treat identifier as a plain username ---
    return identifier


#gym login view
@never_cache
def user_login(request):
    if request.method == 'POST':
        # Template sends 'identifier' (mobile / email / username).
        # Fall back to 'username' for backwards-compat.
        identifier = request.POST.get('identifier') or request.POST.get('username', '')
        password = request.POST.get('password')

        # Resolve identifier → Django username
        resolved_username = _resolve_identifier_to_username(identifier)

        user = authenticate(request, username=resolved_username, password=password)
        if user is not None:
            login(request, user)
            if user.is_superuser:
                request.session['role'] = 'superadmin'
                # Redirect to a superadmin-specific dashboard if you have one
                return redirect('dashboard') 
            
            try:
                gym_admin = GymAdmin.objects.get(user=user)
                request.session['gym_id'] = gym_admin.gym.id
                request.session['gym_name'] = gym_admin.gym.name
                request.session['gym_logo'] = gym_admin.gym.logo.url if gym_admin.gym.logo else None
                request.session['gym_phone'] = gym_admin.gym.phone
                request.session['role'] = 'gym_admin'
                return redirect('dashboard')
            except GymAdmin.DoesNotExist:
                # Handle regular users or other roles if necessary
                try:
                    sub_admin = SubAdmin.objects.get(user=user)
                    request.session['gym_id'] = sub_admin.gym.id
                    request.session['gym_name'] = sub_admin.gym.name
                    request.session['gym_logo'] = sub_admin.gym.logo.url if sub_admin.gym.logo else None
                    request.session['gym_phone'] = sub_admin.gym.phone
                    request.session['role'] = sub_admin.role
                    request.session['subadmin_id'] = sub_admin.id
                    return redirect('dashboard')
                except SubAdmin.DoesNotExist:
                    pass

            messages.error(request, 'Invalid user role.')
            return redirect('login')
        else:
            messages.error(request, 'Invalid username or password.')
    return render(request, 'login/login.html')


def user_logout(request):
    if 'gym_id' in request.session:
        del request.session['gym_id']
    if 'role' in request.session:
        del request.session['role']
    logout(request)
    request.session.flush()  # Clear all session data
    print("Session data after logout:", request.session.items())  # Debugging line
    return redirect('index')


MODULE_DEFINITIONS = [
    {
        'app': 'enquiry',
        'title': 'Lead & Enquiry Management',
        'icon': 'mdi-help-circle-outline',
        'badge_class': 'badge-soft-primary',
        'desc': 'Capture walk-ins, schedule trials, and track prospect conversions',
    },
    {
        'app': 'members',
        'title': 'Members Management',
        'icon': 'mdi-account-group-outline',
        'badge_class': 'badge-soft-info',
        'desc': 'Member profiles, registrations, biometric KYC, and membership freeze',
    },
    {
        'app': 'trainers',
        'title': 'Trainers & Instructors',
        'icon': 'mdi-account-tie-outline',
        'badge_class': 'badge-soft-success',
        'desc': 'Instructor profiles, work shifts, specialties, and client assignments',
    },
    {
        'app': 'attendance',
        'title': 'Attendance & Check-Ins',
        'icon': 'mdi-calendar-check-outline',
        'badge_class': 'badge-soft-warning',
        'desc': 'Daily check-in logs, biometric QR scanner records, and staff leaves',
    },
    {
        'app': 'billing',
        'title': 'Billing, Payments & Invoices',
        'icon': 'mdi-cash-register',
        'badge_class': 'badge-soft-success',
        'desc': 'Fee collection, membership invoices, payment receipts & tax records',
    },
    {
        'app': 'expenses',
        'title': 'Expenses & Outflows',
        'icon': 'mdi-credit-card-outline',
        'badge_class': 'badge-soft-danger',
        'desc': 'Operational gym expenditures, utility bills, maintenance, & vendor payouts',
    },
    {
        'app': 'inventory',
        'title': 'Equipment & Inventory',
        'icon': 'mdi-package-variant-closed',
        'badge_class': 'badge-soft-primary',
        'desc': 'Gym machines maintenance logs, retail supplement stocks, and supplies',
    },
    {
        'app': 'events',
        'title': 'Events & Fitness Workshops',
        'icon': 'mdi-calendar-star',
        'badge_class': 'badge-soft-info',
        'desc': 'Special workout events, fitness bootcamps, and participant rosters',
    },
    {
        'app': 'management',
        'model': 'membershipplan',
        'title': 'Membership Packages & Plans',
        'icon': 'mdi-wallet-membership',
        'badge_class': 'badge-soft-warning',
        'desc': 'Gym membership subscription tiers, package validity, and pricing',
    },
    {
        'app': 'management',
        'model': 'dietplan',
        'title': 'Diet & Nutrition Plans',
        'icon': 'mdi-food-apple-outline',
        'badge_class': 'badge-soft-success',
        'desc': 'Dietary guidelines, daily calorie targets, and meal plans',
    },
    {
        'app': 'management',
        'model': 'workoutplan',
        'title': 'Workout & Exercise Plans',
        'icon': 'mdi-dumbbell',
        'badge_class': 'badge-soft-primary',
        'desc': 'Workout schedules, body splits, exercise sets, and fitness routines',
    },
    {
        'app': 'settings',
        'title': 'System & Payment Settings',
        'icon': 'mdi-cog-outline',
        'badge_class': 'badge-soft-secondary',
        'desc': 'Payment gateway configurations, alert preferences, and branch settings',
    },
]

def _build_permission_modules(assigned_ids=None):
    if assigned_ids is None:
        assigned_ids = []
    
    app_permissions = {}
    module_list = []
    
    for item in MODULE_DEFINITIONS:
        app = item['app']
        model = item.get('model')
        if model:
            content_type = ContentType.objects.filter(app_label=app, model=model).first()
        else:
            content_type = ContentType.objects.filter(app_label=app).first()
        if not content_type:
            continue
        perms = Permission.objects.filter(content_type=content_type)
        key = f"{app}_{model}" if model else app
        app_permissions[key] = perms
        
        view_perm = perms.filter(codename__startswith='view_').first()
        add_perm = perms.filter(codename__startswith='add_').first()
        change_perm = perms.filter(codename__startswith='change_').first()
        delete_perm = perms.filter(codename__startswith='delete_').first()
        
        module_list.append({
            'app': app,
            'model': model or '',
            'title': item['title'],
            'icon': item['icon'],
            'badge_class': item['badge_class'],
            'desc': item['desc'],
            'view_perm': view_perm,
            'add_perm': add_perm,
            'change_perm': change_perm,
            'delete_perm': delete_perm,
            'has_view': bool(view_perm and view_perm.id in assigned_ids),
            'has_add': bool(add_perm and add_perm.id in assigned_ids),
            'has_change': bool(change_perm and change_perm.id in assigned_ids),
            'has_delete': bool(delete_perm and delete_perm.id in assigned_ids),
        })
        
    return app_permissions, module_list


@never_cache
@login_required(login_url='login')
@gym_admin_required
def add_gym_subadmin(request):
    gym = getattr(request, 'gym', None)
    if not gym:
        gym_admin = GymAdmin.objects.filter(user=request.user).first()
        if gym_admin:
            gym = gym_admin.gym

    if request.method == 'POST':
        # Personal Information
        full_name = request.POST.get('full_name') or request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        phone_number = request.POST.get('phone_number') or request.POST.get('mobile', '').strip()
        address = request.POST.get('address', '').strip()
        photo = request.FILES.get('photo')
        role = request.POST.get('role', 'subadmin')

        # Login Credentials
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()

        # Permissions
        permissions = request.POST.getlist('permissions')

        if not username:
            messages.error(request, 'Username is required.')
        elif User.objects.filter(username=username).exists():
            messages.error(request, f'Username "{username}" already exists. Please choose a different username.')
        elif not password:
            messages.error(request, 'Password is required for new sub-admin.')
        elif not gym:
            messages.error(request, 'No active gym found for this account. Please verify gym setup.')
        else:
            try:
                # Create the user
                user = User.objects.create_user(username=username, email=email, password=password)
                if full_name:
                    parts = full_name.strip().split(' ', 1)
                    user.first_name = parts[0]
                    if len(parts) > 1:
                        user.last_name = parts[1]
                user.save()

                # Create the sub-admin profile
                sub_admin = SubAdmin.objects.create(
                    user=user,
                    gym=gym,
                    phone_number=phone_number,
                    address=address,
                    photo=photo,
                    role=role
                )

                # Assign permissions
                for perm_id in permissions:
                    try:
                        perm = Permission.objects.get(id=perm_id)
                        SubAdminPermission.objects.create(sub_admin=sub_admin, permission_name=perm.codename)
                    except Permission.DoesNotExist:
                        pass

                messages.success(request, f'Sub-admin "{user.get_full_name() or username}" created successfully!')
                return redirect('view_subadmins')

            except Exception as e:
                messages.error(request, f'Error creating sub-admin: {e}')

    app_permissions, module_list = _build_permission_modules([])

    context = {
        'app_permissions': app_permissions,
        'module_list': module_list,
        'ROLE_CHOICES': ROLE_CHOICES,
        'assigned_permissions': []
    }
    return render(request, 'login/add_gym_subadmin.html', context)


@login_required
def password_reset_page(request):
    if request.method == 'POST':
        current_password = request.POST.get('current_password')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')

        user = request.user
        if not user.check_password(current_password):
            messages.error(request, 'Invalid current password.')
        elif new_password != confirm_password:
            messages.error(request, 'New passwords do not match.')
        elif ' ' in new_password:
            messages.error(request, 'Password cannot contain spaces.')
        else:
            user.set_password(new_password)
            user.save()
            
            if hasattr(user, 'gymadmin'):
                gym_admin = user.gymadmin
                if hasattr(gym_admin, 'gym'):
                    gym_admin.gym.password_reset_required = False
                    gym_admin.gym.save()
            
            messages.success(request, 'Password updated successfully.')
            return redirect('dashboard')
            
    return render(request, 'login/password_reset.html')

@never_cache
@login_required(login_url='login')
@gym_admin_required
def view_subadmins(request):
    gym = getattr(request, 'gym', None)
    if not gym:
        gym_admin = GymAdmin.objects.filter(user=request.user).first()
        if gym_admin:
            gym = gym_admin.gym
    sub_admins = SubAdmin.objects.filter(gym=gym) if gym else SubAdmin.objects.none()
    context = {
        'sub_admins': sub_admins
    }
    return render(request, 'login/view_subadmins.html', context)


@never_cache
@login_required(login_url='login')
@gym_admin_required
def delete_subadmin(request, sub_admin_id):
    try:
        sub_admin = SubAdmin.objects.get(id=sub_admin_id)
        user = sub_admin.user
        sub_admin.delete()
        user.delete()
        messages.success(request, 'Sub-admin deleted successfully.')
    except SubAdmin.DoesNotExist:
        messages.error(request, 'Sub-admin not found.')
    except Exception as e:
        messages.error(request, f'An error occurred: {e}')
    return redirect('view_subadmins')

@never_cache
@login_required(login_url='login')
@gym_admin_required
def edit_subadmin(request, sub_admin_id):
    try:
        sub_admin = SubAdmin.objects.get(id=sub_admin_id)
        user = sub_admin.user
    except SubAdmin.DoesNotExist:
        messages.error(request, 'Sub-admin not found.')
        return redirect('view_subadmins')

    if request.method == 'POST':
        full_name = request.POST.get('full_name') or request.POST.get('name', '').strip()
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        phone_number = request.POST.get('phone_number') or request.POST.get('mobile', '').strip()
        address = request.POST.get('address', '').strip()
        photo = request.FILES.get('photo')
        permissions = request.POST.getlist('permissions')
        role = request.POST.get('role', sub_admin.role)
        new_password = request.POST.get('password', '').strip()

        if not username:
            messages.error(request, 'Username is required.')
        elif username != user.username and User.objects.filter(username=username).exclude(id=user.id).exists():
            messages.error(request, f'Username "{username}" is already taken.')
        else:
            try:
                if full_name:
                    parts = full_name.split(' ', 1)
                    user.first_name = parts[0]
                    if len(parts) > 1:
                        user.last_name = parts[1]
                user.username = username
                user.email = email
                if new_password:
                    user.set_password(new_password)
                user.save()

                sub_admin.phone_number = phone_number
                sub_admin.address = address
                sub_admin.role = role
                if photo:
                    sub_admin.photo = photo
                sub_admin.save()
                
                SubAdminPermission.objects.filter(sub_admin=sub_admin).delete()
                for perm_id in permissions:
                    try:
                        perm = Permission.objects.get(id=perm_id)
                        SubAdminPermission.objects.create(sub_admin=sub_admin, permission_name=perm.codename)
                    except Permission.DoesNotExist:
                        pass

                messages.success(request, f'Sub-admin "{user.get_full_name() or username}" updated successfully.')
                return redirect('view_subadmins')
            except Exception as e:
                messages.error(request, f'Error updating sub-admin: {e}')

    assigned_permissions_qs = SubAdminPermission.objects.filter(sub_admin=sub_admin).values_list('permission_name', flat=True)
    assigned_permissions = list(Permission.objects.filter(codename__in=list(assigned_permissions_qs)).values_list('id', flat=True))
    app_permissions, module_list = _build_permission_modules(assigned_permissions)

    context = {
        'sub_admin': sub_admin,
        'app_permissions': app_permissions,
        'module_list': module_list,
        'assigned_permissions': assigned_permissions,
        'ROLE_CHOICES': ROLE_CHOICES
    }
    return render(request, 'login/add_gym_subadmin.html', context)