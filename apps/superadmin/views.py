from django.utils import timezone
from django.shortcuts import render,get_object_or_404, redirect
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from .forms import GymForm, GymAdminForm, SubscriptionPlanForm
from .models import Gym, GymAdmin, SubscriptionPlan, GymSubscription
from apps.members.models import Member, MembershipHistory
from apps.billing.models import Payment
from django.db.models import Q, Sum
from django.contrib.auth.decorators import login_required
from .decorators import superadmin_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db.models import F
from decimal import Decimal
from datetime import date, datetime, timedelta
from django.contrib import messages
from apps.website.models import WebsiteContactSubmission

def invoice_view(request, subscription_id):
    subscription = get_object_or_404(
        GymSubscription.objects.select_related('gym', 'subscription'),
        id=subscription_id
    )
    return render(request, 'superadmin/invoice.html', {'subscription': subscription})

@login_required
@superadmin_required
def toggle_gym_freeze(request, gym_id):
    gym = get_object_or_404(Gym, pk=gym_id)
    gym.is_frozen = not gym.is_frozen
    gym.save()
    messages.success(request, f"Gym '{gym.name}' has been {'frozen' if gym.is_frozen else 'unfrozen'}.")
    return redirect('superadmin:gym_profile', gym_id=gym.id)

@login_required
@superadmin_required
def toggle_whatsapp(request, gym_id):
    gym = get_object_or_404(Gym, pk=gym_id)
    gym.whatsapp_enabled = not gym.whatsapp_enabled
    gym.save()
    status = 'enabled' if gym.whatsapp_enabled else 'disabled'
    messages.success(request, f"WhatsApp messaging for '{gym.name}' has been {status}.")
    return redirect('superadmin:gym_profile', gym_id=gym.id)

@login_required
@superadmin_required
def dashboard(request):
    total_gyms = Gym.objects.count()
    total_members = Member.objects.count()
    active_subscriptions = MembershipHistory.objects.filter(status='active').count()

    context = {
        'total_gyms': total_gyms,
        'total_members': total_members,
        'active_subscriptions': active_subscriptions,
    }
    return render(request, 'superadmin/dashboard.html', context)


@login_required
@superadmin_required
def add_gym(request):
    if request.method == 'POST':
        form = GymForm(request.POST, request.FILES)
        if form.is_valid():
            gym = form.save(commit=False)
            
            # Handle GST fields
            gst_enabled = form.cleaned_data.get('gst_enabled', False)
            if gst_enabled:
                gym.gst_enabled = True
                gym.gst_rate = form.cleaned_data.get('gst_rate')
                gym.gst_number = form.cleaned_data.get('gst_number')
            else:
                gym.gst_enabled = False
                gym.gst_rate = None
                gym.gst_number = None

            gym.save()
            messages.success(request, f"Gym '{gym.name}' has been added successfully.")
            return redirect('superadmin:create_gym_admin', gym_id=gym.id)
    else:
        form = GymForm()
    return render(request, 'superadmin/add_gym.html', {'form': form, 'page_title': 'Add Gym', 'button_text': 'Add Gym'})


@login_required
@superadmin_required
def create_gym_admin(request, gym_id):
    gym = get_object_or_404(Gym, id=gym_id)
    if request.method == 'POST':
        form = GymAdminForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save()
            user.is_staff = True
            user.save()

            gym_admin = GymAdmin.objects.create(
                user=user,
                gym=gym,
                name=form.cleaned_data['name'],
                Phone_number=form.cleaned_data['Phone_number'],
                Department=form.cleaned_data.get('Department'),
                notes=form.cleaned_data.get('notes')
            )

            if 'photo' in request.FILES:
                gym_admin.photo = request.FILES['photo']
                gym_admin.save()

            messages.success(request, f"Admin for '{gym.name}' has been created successfully.")
            return redirect('superadmin:gym_list')
    else:
        form = GymAdminForm()
    return render(request, 'superadmin/create_gym_admin.html', {'form': form, 'gym': gym})



@login_required
@superadmin_required
def gym_list(request):
    query = request.GET.get('q')
    if query:
        gyms_list = Gym.objects.filter(
            Q(name__icontains=query) |
            Q(gym_id__icontains=query) |
            Q(address__icontains=query)
        ).distinct()
    else:
        gyms_list = Gym.objects.all()

    for gym in gyms_list:
        admin = GymAdmin.objects.filter(gym=gym).first()
        gym.has_admin = bool(admin)
        gym.admin_name = f"{admin.user.first_name} {admin.user.last_name}".strip() or admin.user.username if admin else "N/A"
        gym.admin_username = admin.user.username if admin else "N/A"

        latest_subscription = GymSubscription.objects.filter(gym=gym, is_deleted=False).order_by('-end_date').first()
        if latest_subscription:
            gym.expiry_date = latest_subscription.end_date
            today = timezone.now().date()
            if gym.expiry_date < today:
                gym.membership_status = 'Expired'
                gym.remaining_months = 0
                gym.remaining_days = 0
            else:
                gym.membership_status = 'Active'
                remaining_time = gym.expiry_date - today
                total_days = remaining_time.days
                gym.remaining_months = total_days // 30
                gym.remaining_days = total_days % 30
        else:
            gym.expiry_date = None
            gym.membership_status = 'No Subscription'
            gym.remaining_months = 0
            gym.remaining_days = 0

    paginator = Paginator(gyms_list, 10)  # Show 10 gyms per page
    page = request.GET.get('page')
    gyms = paginator.get_page(page)

    open_invoice_id = request.session.pop('open_invoice_id', None)
    return render(request, 'superadmin/gym_list.html', {'gyms': gyms, 'open_invoice_id': open_invoice_id})


@login_required
@superadmin_required
def update_gym(request, gym_id):
    gym = get_object_or_404(Gym, pk=gym_id)
    if request.method == 'POST':
        form = GymForm(request.POST, request.FILES, instance=gym)
        if form.is_valid():
            gym = form.save()
            messages.success(request, f"Gym '{gym.name}' has been updated successfully.")
            return redirect('superadmin:gym_list')
    else:
        form = GymForm(instance=gym)
    return render(request, 'superadmin/add_gym.html', {'form': form, 'page_title': 'Update Gym', 'button_text': 'Update Gym'})

@login_required
@superadmin_required
@require_POST
def delete_gym(request, gym_id):
    gym = get_object_or_404(Gym, pk=gym_id)
    try:
        gym.delete()
        messages.success(request, 'Gym has been deleted successfully.')
        return JsonResponse({'status': 'success', 'message': 'Gym deleted successfully.'})
    except Exception as e:
        messages.error(request, f'An error occurred: {e}')
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
@superadmin_required
def gym_profile(request, gym_id):
    gym = get_object_or_404(Gym, pk=gym_id)
    form = GymForm(instance=gym)

    # Paginate payment history
    payment_list = Payment.objects.filter(gym=gym, is_deleted=False).order_by('-payment_date')
    paginator_payments = Paginator(payment_list, 10)  # Show 10 payments per page
    page_payments = request.GET.get('page_payments')
    try:
        payment_history = paginator_payments.page(page_payments)
    except PageNotAnInteger:
        payment_history = paginator_payments.page(1)
    except EmptyPage:
        payment_history = paginator_payments.page(paginator_payments.num_pages)

    gym_subscriptions = GymSubscription.objects.filter(gym=gym, is_deleted=False)
    active_subscription = gym_subscriptions.filter(start_date__lte=date.today(), end_date__gte=date.today()).first()
    gym_admins = GymAdmin.objects.filter(gym=gym)
    admin_form = GymAdminForm()

    # Calculate due amount
    aggregation = gym_subscriptions.aggregate(
        total_amount=Sum('total_amount'),
        paid_amount=Sum('paid_amount')
    )
    due_amount = (aggregation['total_amount'] or 0) - (aggregation['paid_amount'] or 0)

    return render(request, 'superadmin/gym_profile.html', {
        'gym': gym,
        'form': form,
        'payment_history': payment_history,
        'gym_subscriptions': gym_subscriptions,
        'active_subscription': active_subscription,
        'gym_admins': gym_admins,
        'admin_form': admin_form,
        'due_amount': due_amount
    })

@login_required
@superadmin_required
def reset_admin_password(request, admin_id):
    admin = get_object_or_404(GymAdmin, id=admin_id)
    user = admin.user
    user.set_password('BTsquare@123')
    user.save()
    
    # Mark the gym for password reset
    admin.gym.password_reset_required = True
    admin.gym.save()
    
    messages.success(request, f"Password for {user.username} has been reset successfully.")
    return redirect('superadmin:gym_profile', gym_id=admin.gym.id)


@login_required
@superadmin_required
def subscription_plan_list(request):
    query = request.GET.get('q')
    if query:
        plans = SubscriptionPlan.objects.filter(
            Q(name__icontains=query) |
            Q(price__icontains=query) |
            Q(duration_months__icontains=query)
        ).distinct()
    else:
        plans = SubscriptionPlan.objects.all()
    return render(request, 'superadmin/subscription_plan_list.html', {'plans': plans})

@login_required
@superadmin_required
def add_subscription_plan(request):
    if request.method == 'POST':
        form = SubscriptionPlanForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Subscription plan created successfully.")
            return redirect('superadmin:subscription_plan_list')
    else:
        form = SubscriptionPlanForm()
    return render(request, 'superadmin/add_subscription_plan.html', {'form': form})

@login_required
@superadmin_required
def update_subscription_plan(request, plan_id):
    plan = get_object_or_404(SubscriptionPlan, id=plan_id)
    if request.method == 'POST':
        form = SubscriptionPlanForm(request.POST, instance=plan)
        if form.is_valid():
            form.save()
            return redirect('superadmin:subscription_plan_list')
    else:
        form = SubscriptionPlanForm(instance=plan)
    return render(request, 'superadmin/update_subscription_plan.html', {'form': form})

@login_required
@superadmin_required
@require_POST
def delete_subscription_plan(request, plan_id):
    plan = get_object_or_404(SubscriptionPlan, id=plan_id)
    try:
        plan.delete()
        messages.success(request, 'Subscription plan has been deleted successfully.')
        return JsonResponse({'status': 'success', 'message': 'Subscription plan deleted successfully.'})
    except Exception as e:
        messages.error(request, f'An error occurred: {e}')
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
@superadmin_required
def assign_subscription(request):
    if request.method == 'POST':
        gym_id = request.POST.get('gym')
        subscription_id = request.POST.get('subscription')
        start_date = request.POST.get('start_date')
        discount = request.POST.get('discount')
        total_amount = request.POST.get('total_amount')
        paid_amount = request.POST.get('paid_amount')
        payment_mode = request.POST.get('payment_mode')
        transaction_id = request.POST.get('transaction_id')
        remark = request.POST.get('remark')

        gym = get_object_or_404(Gym, id=gym_id)
        subscription = get_object_or_404(SubscriptionPlan, id=subscription_id)

        start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
        end_date = start_date_obj + timedelta(days=subscription.duration_months * 30)

        new_subscription = GymSubscription.objects.create(
            gym=gym,
            subscription=subscription,
            start_date=start_date,
            end_date=end_date,
            discount=discount,
            total_amount=total_amount,
            paid_amount=paid_amount,
            payment_mode=payment_mode,
            transaction_id=transaction_id,
            remark=remark
        )
        messages.success(request, f'Subscription assigned to {gym.name} successfully.')
        request.session['open_invoice_id'] = new_subscription.id
        return redirect('superadmin:gym_list')

    else:
        gyms = Gym.objects.all()
        subscriptions = SubscriptionPlan.objects.all()
        payment_modes = GymSubscription.PAYMENT_MODE_CHOICES
        selected_gym_id = request.GET.get('gym_id')
        selected_plan_id = request.GET.get('plan_id')
        
        return render(request, 'superadmin/assign_subscription.html', {
            'gyms': gyms,
            'subscriptions': subscriptions,
            'payment_modes': payment_modes,
            'selected_plan_id': selected_plan_id,
            'selected_gym_id': selected_gym_id,
        })


@login_required
@superadmin_required
def billing_history(request):
    query = request.GET.get('q')
    status_filter = request.GET.get('status')
    type_filter = request.GET.get('type')

    base_queryset = GymSubscription.objects.filter(is_deleted=False) if request.user.is_superuser else GymSubscription.objects.filter(gym=request.user.gymadmin.gym, is_deleted=False)

    subscriptions = base_queryset.annotate(
        due_amount_calculated=F('total_amount') - F('paid_amount')
    ).order_by('-start_date')

    if query:
        subscriptions = subscriptions.filter(gym__name__icontains=query)

    if status_filter:
        if status_filter == 'paid':
            subscriptions = subscriptions.filter(due_amount_calculated=0)
        elif status_filter == 'unpaid':
            subscriptions = subscriptions.filter(due_amount_calculated__gt=0)

    # Get payments that are submitted via super admin (gym-to-platform payments)
    # These payments have no member associated with them
    payments = Payment.objects.filter(
        gym__in=subscriptions.values('gym'), 
        member__isnull=True, 
        is_deleted=False
    ).order_by('-payment_date')

    if type_filter == 'subscription':
        history = list(subscriptions)
    elif type_filter == 'payment':
        history = list(payments)
    else:
        # Combine and sort both types
        history = sorted(
            list(subscriptions) + list(payments),
            key=lambda item: item.start_date if isinstance(item, GymSubscription) else item.payment_date.date(),
            reverse=True
        )

    paginator = Paginator(history, 10)
    page = request.GET.get('page')
    try:
        history_page = paginator.page(page)
    except PageNotAnInteger:
        history_page = paginator.page(1)
    except EmptyPage:
        history_page = paginator.page(paginator.num_pages)

    # Calculate stats for the dashboard cards
    total_revenue = GymSubscription.objects.filter(is_deleted=False).aggregate(Sum('paid_amount'))['paid_amount__sum'] or 0
    total_revenue += Payment.objects.filter(member__isnull=True, is_deleted=False).aggregate(Sum('amount'))['amount__sum'] or 0
    
    total_due = GymSubscription.objects.filter(is_deleted=False).aggregate(
        total=Sum('total_amount'),
        paid=Sum('paid_amount')
    )
    total_due_amount = (total_due['total'] or 0) - (total_due['paid'] or 0)

    context = {
        'history': history_page,
        'query': query,
        'status_filter': status_filter,
        'type_filter': type_filter,
        'total_revenue': total_revenue,
        'total_due': total_due_amount,
        'active_gyms_count': Gym.objects.filter(is_frozen=False).count(),
    }
    return render(request, 'superadmin/billing_history.html', context)


@login_required
@superadmin_required
def submit_due(request):
    if request.method == 'POST':
        gym_id = request.POST.get('gym')
        amount_to_pay = request.POST.get('amount_to_pay')
        payment_method = request.POST.get('payment_method')
        notes = request.POST.get('notes')
        
        if gym_id and amount_to_pay:
            gym = get_object_or_404(Gym, id=gym_id)
            amount_to_pay_decimal = Decimal(amount_to_pay)

            # Total due for the gym
            aggregation = GymSubscription.objects.filter(gym=gym, is_deleted=False).aggregate(
                total_amount=Sum('total_amount'),
                paid_amount=Sum('paid_amount')
            )
            gym_total_due = (aggregation['total_amount'] or 0) - (aggregation['paid_amount'] or 0)

            if amount_to_pay_decimal > gym_total_due:
                messages.error(request, 'Amount to pay cannot be greater than the total due amount.')
            else:
                # Apply payment to subscriptions, oldest first
                subscriptions = GymSubscription.objects.filter(gym=gym, is_deleted=False).annotate(
                    due=F('total_amount') - F('paid_amount')
                ).filter(due__gt=0).order_by('start_date')
                
                payment_to_apply = amount_to_pay_decimal
                for sub in subscriptions:
                    if payment_to_apply <= 0:
                        break
                    
                    current_due = sub.total_amount - sub.paid_amount
                    payable = min(payment_to_apply, current_due)
                    sub.paid_amount += payable
                    sub.save()
                    payment_to_apply -= payable

                Payment.objects.create(
                    gym=gym,
                    amount=amount_to_pay_decimal,
                    payment_date=date.today(),
                    payment_mode=payment_method,
                    comment=notes
                )
                messages.success(request, 'Due amount submitted successfully.')
                # Open invoice in new tab via session
                if subscriptions:
                    last_sub = subscriptions.last()
                    request.session['open_invoice_id'] = last_sub.id
        
        return redirect('superadmin:submit_due')

    gyms_with_due = Gym.objects.filter(gymsubscription__is_deleted=False).annotate(
        total_subscription_amount=Sum('gymsubscription__total_amount'),
        total_paid_amount=Sum('gymsubscription__paid_amount')
    ).filter(total_subscription_amount__gt=F('total_paid_amount')).annotate(
        total_due=F('total_subscription_amount') - F('total_paid_amount'),
        admin_name=F('gymadmin__name'),
        contact_no=F('phone'),
    )

    for gym in gyms_with_due:
        gym.latest_subscription = GymSubscription.objects.filter(gym=gym).latest('start_date')

    query = request.GET.get('q')
    if query:
        gyms_with_due = gyms_with_due.filter(
            Q(name__icontains=query) |
            Q(gym_id__icontains=query) |
            Q(admin_name__icontains=query)
        ).distinct()

    open_invoice_id = request.session.pop('open_invoice_id', None)

    return render(request, 'superadmin/submit_due.html', {
        'gyms': gyms_with_due, 
        'query': query,
        'open_invoice_id': open_invoice_id
    })

@login_required
@superadmin_required
def get_due_amount(request, gym_id):
    gym = get_object_or_404(Gym, id=gym_id)
    aggregation = GymSubscription.objects.filter(gym=gym).aggregate(
        total_amount=Sum('total_amount'),
        paid_amount=Sum('paid_amount')
    )
    due_amount = (aggregation['total_amount'] or 0) - (aggregation['paid_amount'] or 0)
    return JsonResponse({'due_amount': due_amount})

@login_required
@superadmin_required
def website_contact_submissions(request):
    query = request.GET.get('q')
    type_filter = request.GET.get('type')
    
    submissions_list = WebsiteContactSubmission.objects.all()
    
    if query:
        submissions_list = submissions_list.filter(
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(email__icontains=query) |
            Q(business_name__icontains=query) |
            Q(message__icontains=query)
        )
        
    if type_filter:
        submissions_list = submissions_list.filter(inquiry_type=type_filter)

    paginator = Paginator(submissions_list, 20)
    page = request.GET.get('page')
    submissions = paginator.get_page(page)
    
    context = {
        'submissions': submissions,
        'page_title': 'Website Contact Submissions',
        'query': query,
        'type_filter': type_filter,
    }
    return render(request, 'superadmin/website_contact_submissions.html', context)

@login_required
@superadmin_required
@require_POST
def mark_submission_read(request, submission_id):
    submission = get_object_or_404(WebsiteContactSubmission, id=submission_id)
    submission.is_read = True
    submission.save()
    return JsonResponse({'status': 'success'})

@login_required
@superadmin_required
@require_POST
def delete_submission(request, submission_id):
    submission = get_object_or_404(WebsiteContactSubmission, id=submission_id)
    submission.delete()
    return JsonResponse({'status': 'success'})

@login_required
@superadmin_required
@require_POST
def delete_subscription(request, subscription_id):
    subscription = get_object_or_404(GymSubscription, id=subscription_id)
    subscription.is_deleted = True
    subscription.save()
    messages.success(request, 'Subscription moved to trash.')
    return JsonResponse({'status': 'success'})

@login_required
@superadmin_required
@require_POST
def delete_payment(request, payment_id):
    payment = get_object_or_404(Payment, id=payment_id)
    payment.is_deleted = True
    payment.save()
    messages.success(request, 'Payment moved to trash.')
    return JsonResponse({'status': 'success'})

@login_required
@superadmin_required
def billing_trash(request):
    query = request.GET.get('q')
    
    subscriptions = GymSubscription.objects.filter(is_deleted=True).annotate(
        due_amount_calculated=F('total_amount') - F('paid_amount')
    )
    payments = Payment.objects.filter(is_deleted=True, member__isnull=True)

    if query:
        subscriptions = subscriptions.filter(gym__name__icontains=query)
        payments = payments.filter(gym__name__icontains=query)

    history = sorted(
        list(subscriptions) + list(payments),
        key=lambda item: item.start_date if isinstance(item, GymSubscription) else item.payment_date.date(),
        reverse=True
    )

    paginator = Paginator(history, 10)
    page = request.GET.get('page')
    history_page = paginator.get_page(page)

    return render(request, 'superadmin/billing_trash.html', {'history': history_page, 'query': query})

@login_required
@superadmin_required
@require_POST
def restore_billing(request, item_id, item_type):
    if item_type == 'subscription':
        item = get_object_or_404(GymSubscription, id=item_id)
    else:
        item = get_object_or_404(Payment, id=item_id)
    
    item.is_deleted = False
    item.save()
    messages.success(request, 'Record restored successfully.')
    return JsonResponse({'status': 'success'})

@login_required
@superadmin_required
@require_POST
def permanent_delete_billing(request, item_id, item_type):
    if item_type == 'subscription':
        item = get_object_or_404(GymSubscription, id=item_id)
    else:
        item = get_object_or_404(Payment, id=item_id)
    
    item.delete()
    messages.success(request, 'Record deleted permanently.')
    return JsonResponse({'status': 'success'})