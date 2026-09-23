from django.shortcuts import render, redirect, get_object_or_404
from .models import Item, StockLog, Equipment, Maintenance
from .forms import ItemForm, StockOutForm, EquipmentForm, MaintenanceForm
from django.contrib import messages
from django.db.models import Q, F
from django.contrib.auth.decorators import login_required
from apps.login.decorators import custom_permission_required
from django.db.models import Sum, Count
from django.utils import timezone
from datetime import timedelta

@login_required
@custom_permission_required('view_item')
def inventory_dashboard(request):
    gym = getattr(request, 'gym', None)

    # Date filtering
    start_date_str = request.GET.get('from_date')
    end_date_str = request.GET.get('to_date')

    if start_date_str and end_date_str:
        start_date = timezone.datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = timezone.datetime.strptime(end_date_str, '%Y-%m-%d').date()
    else:
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=30)

    # KPI Calculations
    total_products = Item.objects.filter(gym=gym, is_deleted=False).exclude(category='equipment').count()
    total_equipment = Equipment.objects.filter(gym=gym, is_deleted=False).count()
    low_stock_items = Item.objects.filter(gym=gym, is_deleted=False, current_stock__gt=0, current_stock__lte=F('reorder_level')).count()
    
    stock_out_in_period = StockLog.objects.filter(
        gym=gym,
        transaction_type='stock_out',
        date__date__range=[start_date, end_date]
    ).count()

    # Chart Data
    monthly_stock_usage = StockLog.objects.filter(
        gym=gym,
        transaction_type='stock_out',
        date__range=[start_date, end_date]
    ).values('item__name').annotate(total_quantity=Sum('quantity')).order_by('-total_quantity')[:10]

    equipment_status = Equipment.objects.filter(gym=gym, is_deleted=False).values('status').annotate(count=Count('id'))

    # Recent Transactions
    recent_transactions = StockLog.objects.filter(gym=gym, date__date__range=[start_date, end_date]).order_by('-date')[:10]

    context = {
        'gym': gym,
        'total_products': total_products,
        'total_equipment': total_equipment,
        'low_stock_items': low_stock_items,
        'stock_out_in_period': stock_out_in_period,
        'monthly_stock_usage': monthly_stock_usage,
        'equipment_status': equipment_status,
        'start_date': start_date.strftime('%Y-%m-%d'),
        'end_date': end_date.strftime('%Y-%m-%d'),
        'recent_transactions': recent_transactions,
    }
    return render(request, 'inventory/inventory_dashboard.html', context)

@login_required
@custom_permission_required('view_item')
def all_items(request):
    gym = getattr(request, 'gym', None)
    query = request.GET.get('q')
    category = request.GET.get('category')
    supplier = request.GET.get('supplier')
    stock_status = request.GET.get('status')

    items = Item.objects.filter(gym=gym, is_deleted=False)

    if query:
        items = items.filter(
            Q(name__icontains=query) |
            Q(sku__icontains=query)
        )
    
    if category:
        items = items.filter(category__iexact=category)
    
    if supplier:
        items = items.filter(supplier__iexact=supplier)

    if stock_status:
        if stock_status == 'in_stock':
            items = items.filter(current_stock__gt=F('reorder_level'))
        elif stock_status == 'low_stock':
            items = items.filter(current_stock__lte=F('reorder_level'), current_stock__gt=0)
        elif stock_status == 'out_of_stock':
            items = items.filter(current_stock=0)

    context = {
        'items': items,
        'categories': Item.objects.filter(gym=gym).values_list('category', flat=True).distinct(),
        'suppliers': Item.objects.filter(gym=gym).values_list('supplier', flat=True).distinct(),
        'gym': gym,
        'stock_status': stock_status,
    }
    return render(request, 'inventory/all_items.html', context)

@login_required
@custom_permission_required('change_item')
def add_edit_item(request, id=None):
    gym = getattr(request, 'gym', None)
    if id:
        item = Item.objects.filter(id=id, gym=gym).first()
        if not item:
            messages.error(request, 'Item not found.')
            return redirect('inventory:all_items')
        form = ItemForm(request.POST or None, request.FILES or None, instance=item)
    else:
        form = ItemForm(request.POST or None, request.FILES or None)

    if request.method == 'POST':
        if form.is_valid():
            instance = form.save(commit=False)
            instance.added_by = request.user
            instance.gym = gym
            instance.save()
            messages.success(request, 'Item saved successfully!')
            return redirect('inventory:all_items')
        else:
            messages.error(request, 'Please correct the errors below.')

    item_suppliers = Item.objects.filter(gym=gym).values_list('supplier', flat=True).distinct()
    equipment_suppliers = Equipment.objects.filter(gym=gym).values_list('supplier', flat=True).distinct()
    suppliers = sorted([s for s in set(list(item_suppliers) + list(equipment_suppliers)) if s])

    categories = Item.objects.filter(gym=gym).values_list('category', flat=True).distinct()

    context = {
        'form': form,
        'suppliers': suppliers,
        'categories': categories,
        'gym': gym,
    }
    return render(request, 'inventory/add_inventory_item.html', context)

def _get_suppliers(gym):
    item_suppliers = Item.objects.filter(gym=gym).values_list('supplier', flat=True).distinct()
    equipment_suppliers = Equipment.objects.filter(gym=gym).values_list('supplier', flat=True).distinct()
    suppliers = sorted([s for s in set(list(item_suppliers) + list(equipment_suppliers)) if s])
    return suppliers

@login_required
@custom_permission_required('change_item')
def stock_out_view(request, item_id=None):
    gym = getattr(request, 'gym', None)
    items = Item.objects.filter(gym=gym, is_deleted=False)

    if request.method == 'POST':
        form = StockOutForm(request.POST, gym=gym)
        if form.is_valid():
            stock_log = form.save(commit=False)
            stock_log.transaction_type = 'stock_out'
            stock_log.added_by = request.user
            stock_log.gym = gym
            
            item = stock_log.item
            if item.current_stock < stock_log.quantity:
                messages.error(request, f'Not enough stock for {item.name}.')
                return redirect('inventory:stock_out')

            item.current_stock -= stock_log.quantity
            item.save()
            
            stock_log.selling_price = item.selling_price
            stock_log.total_amount = (item.selling_price * stock_log.quantity) - stock_log.discount
            stock_log.save()
            
            messages.success(request, f'{item.name} has been stocked out successfully.')
            return redirect('inventory:stock_log', item_id=item.id)
    else:
        initial_data = {}
        if item_id:
            item = Item.objects.filter(id=item_id, gym=gym).first()
            if item:
                initial_data['item'] = item
                initial_data['unit_price'] = item.selling_price
        form = StockOutForm(initial=initial_data, gym=gym)
    
    context = {
        'form': form,
        'items': items,
        'suppliers': _get_suppliers(gym),
        'gym': gym,
    }
    return render(request, 'inventory/stock_out.html', context)

@login_required
def stock_log_view(request, item_id):
    gym = getattr(request, 'gym', None)
    item = Item.objects.filter(id=item_id, gym=gym).first()
    if not item:
        messages.error(request, 'Item not found.')
        return redirect('inventory:all_items')
    logs = StockLog.objects.filter(item=item).order_by('-date')
    context = {
        'item': item,
        'logs': logs,
        'gym': gym,
    }
    return render(request, 'inventory/stock_log.html', context)

@login_required
@custom_permission_required('view_equipment')
def all_equipment(request):
    gym = getattr(request, 'gym', None)
    query = request.GET.get('q')
    category = request.GET.get('category')
    status = request.GET.get('status')

    equipments = Equipment.objects.filter(gym=gym, is_deleted=False)

    if query:
        equipments = equipments.filter(
            Q(name__icontains=query) |
            Q(serial_number__icontains=query)
        )
    
    if category:
        equipments = equipments.filter(category__iexact=category)

    if status:
        equipments = equipments.filter(status__iexact=status)

    context = {
        'equipments': equipments,
        'categories': Equipment.objects.filter(gym=gym).values_list('category', flat=True).distinct(),
        'gym': gym,
    }
    return render(request, 'inventory/all_equipment.html', context)

@login_required
@custom_permission_required('change_equipment')
def add_edit_equipment(request, id=None):
    gym = getattr(request, 'gym', None)
    if id:
        equipment = Equipment.objects.filter(id=id, gym=gym).first()
        if not equipment:
            messages.error(request, 'Equipment not found.')
            return redirect('inventory:all_equipment')
        form = EquipmentForm(request.POST or None, request.FILES or None, instance=equipment)
    else:
        form = EquipmentForm(request.POST or None, request.FILES or None)

    if request.method == 'POST':
        if form.is_valid():
            instance = form.save(commit=False)
            instance.added_by = request.user
            instance.gym = gym
            instance.save()
            messages.success(request, 'Equipment saved successfully!')
            return redirect('inventory:all_equipment')
        else:
            messages.error(request, 'Please correct the errors below.')
    
    categories = Item.objects.filter(gym=gym).values_list('category', flat=True).distinct()

    context = {
        'form': form,
        'suppliers': _get_suppliers(gym),
        'categories': categories,
        'gym': gym,
    }
    return render(request, 'inventory/add_equipment.html', context)

@login_required
def maintenance_log(request):
    gym = getattr(request, 'gym', None)
    form = MaintenanceForm(request.POST or None, gym=gym)
    if request.method == 'POST':
        if form.is_valid():
            maintenance = form.save(commit=False)
            maintenance.added_by = request.user
            maintenance.gym = gym
            maintenance.save()
            messages.success(request, 'Maintenance log added successfully!')
            return redirect('inventory:maintenance_log')

    logs = Maintenance.objects.filter(gym=gym).order_by('-service_date')
    context = {
        'form': form,
        'logs': logs,
        'gym': gym,
    }
    return render(request, 'inventory/maintenance_log.html', context)