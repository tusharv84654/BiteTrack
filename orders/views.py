import json
import os
import re
from datetime import datetime
from django.conf import settings
from django.db import transaction
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .models import MenuItem, Order, OrderItem
from .serializers import MenuItemSerializer, OrderDetailSerializer

# File path for student registration log file
STUDENT_RECORDS_FILE = os.path.join(settings.BASE_DIR, 'student_records.txt')


# --- File Management & Regex Helper Functions ---

def validate_student_input(username, enrollment, mobile, department):
    """Uses Regular Expressions to strictly validate user inputs."""
    # 1. Username Regex: 3 to 20 alphanumeric characters or underscores
    if not re.fullmatch(r'^[a-zA-Z0-9_]{3,20}$', username):
        return False, "Username must be 3-20 characters (letters, numbers, underscores only)."

    # 2. Enrollment Regex: Exactly 14 digits
    if not re.fullmatch(r'^[0-9]{14}$', enrollment):
        return False, "Enrollment number must be exactly 14 numeric digits."

    # 3. Mobile Regex: 10 digits starting with 6, 7, 8, or 9
    if not re.fullmatch(r'^[6-9][0-9]{9}$', mobile):
        return False, "Mobile number must be a valid 10-digit number."

    # 4. Department dropdown validation
    valid_departments = ['CSE-IoT', 'CSE', 'IT', 'EC', 'ME']
    if department not in valid_departments:
        return False, "Please select a valid department from the list."

    return True, ""


def save_student_to_file(username, enrollment, mobile, department):
    """File Management: Appends student credentials and academic data to a text file."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    record_line = f"{timestamp} | Username: {username} | Enrollment: {enrollment} | Mobile: {mobile} | Dept: {department}\n"
    
    with open(STUDENT_RECORDS_FILE, 'a+', encoding='utf-8') as f:
        f.write(record_line)


# --- 1. Catalog Endpoint: Anyone can view active menu items ---
@api_view(['GET'])
@permission_classes([AllowAny])
def menu_list(request):
    items = MenuItem.objects.filter(is_available=True)
    serializer = MenuItemSerializer(items, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


# --- 2. Order Placement (API): Atomic checkout with stock deduction ---
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def place_order(request):
    order_items_data = request.data.get('items', [])
    if not order_items_data:
        return Response({'error': 'No items provided in order.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        with transaction.atomic():
            order = Order.objects.create(user=request.user, status='Pending')
            total = 0

            for entry in order_items_data:
                item_id = entry.get('item_id')
                qty = int(entry.get('quantity', 1))

                menu_item = MenuItem.objects.select_for_update().get(id=item_id, is_available=True)

                if menu_item.stock < qty:
                    raise ValueError(f"Insufficient stock for {menu_item.name}.")

                menu_item.stock -= qty
                menu_item.save()

                OrderItem.objects.create(
                    order=order,
                    item=menu_item,
                    quantity=qty,
                    unit_price=menu_item.price
                )
                total += menu_item.price * qty

            order.total_amount = total
            order.save()

            serializer = OrderDetailSerializer(order)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

    except MenuItem.DoesNotExist:
        return Response({'error': 'One or more items do not exist.'}, status=status.HTTP_404_NOT_FOUND)
    except ValueError as err:
        return Response({'error': str(err)}, status=status.HTTP_400_BAD_REQUEST)


# --- 3. Order History: Logged-in student views their own orders ---
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_orders(request):
    orders = Order.objects.filter(user=request.user).prefetch_related('items__item')
    serializer = OrderDetailSerializer(orders, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


# --- 4. Student Menu Catalog Page ---
@login_required(login_url='login')
def home_view(request):
    if request.user.is_staff or request.user.is_superuser:
        return redirect('kitchen')

    items = MenuItem.objects.all()
    return render(request, 'index.html', {
        'items': items,
        'username': request.user.username
    })


# --- 5. Dedicated Kitchen 3-Column Kanban View ---
@login_required(login_url='login')
def kitchen_view(request):
    if not (request.user.is_staff or request.user.is_superuser):
        return redirect('home')

    all_orders = Order.objects.all().order_by('-created_at').prefetch_related('items__item')

    pending_orders = []
    preparing_orders = []
    ready_orders = []

    for order in all_orders:
        st = (order.status or '').strip().lower()
        if st == 'preparing':
            preparing_orders.append(order)
        elif st in ['ready', 'completed']:
            ready_orders.append(order)
        else:
            pending_orders.append(order)

    return render(request, 'orders_dashboard.html', {
        'pending_orders': pending_orders,
        'preparing_orders': preparing_orders,
        'ready_orders': ready_orders,
    })


# --- 6. Login View (File Management & Regex-Driven Authentication) ---
def user_login(request):
    if request.user.is_authenticated:
        if request.user.is_staff or request.user.is_superuser:
            return redirect('kitchen')
        return redirect('home')

    error = None
    form_data = {}

    if request.method == 'POST':
        u = request.POST.get('username', '').strip()
        p = request.POST.get('password', '').strip()
        enrollment = request.POST.get('enrollment', '').strip()
        mobile = request.POST.get('mobile', '').strip()
        department = request.POST.get('department', '').strip()
        remember_me = request.POST.get('remember_me')

        form_data = {
            'username': u,
            'enrollment': enrollment,
            'mobile': mobile,
            'department': department,
            'remember_me': remember_me
        }

        # Basic empty check
        if not u or not p:
            error = "Username and password are required."
            return render(request, 'login.html', {'error': error, 'form_data': form_data})

        existing_user = User.objects.filter(username=u).first()
        is_staff_or_admin = existing_user and (existing_user.is_staff or existing_user.is_superuser)

        # Non-staff student validation via Regular Expressions
        if not is_staff_or_admin:
            is_valid, validation_msg = validate_student_input(u, enrollment, mobile, department)
            if not is_valid:
                return render(request, 'login.html', {'error': validation_msg, 'form_data': form_data})

        # Authentication or creation
        if existing_user:
            user = authenticate(request, username=u, password=p)
            if user is None:
                error = "Incorrect password for existing user."
                return render(request, 'login.html', {'error': error, 'form_data': form_data})
        else:
            # Auto-register new student and log to file management system
            user = User.objects.create_user(username=u, password=p)
            save_student_to_file(u, enrollment, mobile, department)

        login(request, user)
        if remember_me:
            request.session.set_expiry(604800)
        else:
            request.session.set_expiry(0)

        if user.is_staff or user.is_superuser:
            return redirect('kitchen')
        return redirect('home')

    return render(request, 'login.html', {'error': error, 'form_data': form_data})


# --- 7. Logout View ---
def user_logout(request):
    logout(request)
    return redirect('login')


# --- 8. Web Checkout Handler for POS Cart ---
@login_required(login_url='login')
def submit_order_web(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            cart_items = data.get('cart', [])

            if not cart_items:
                return JsonResponse({'status': 'error', 'message': 'Cart is empty'}, status=400)

            with transaction.atomic():
                order = Order.objects.create(user=request.user, status='Pending')
                total = 0

                for item_data in cart_items:
                    item_id = item_data.get('id')
                    qty = int(item_data.get('qty', 1))
                    price = float(item_data.get('price', 0))

                    menu_item = MenuItem.objects.select_for_update().get(id=item_id)

                    if menu_item.stock < qty:
                        return JsonResponse({
                            'status': 'error',
                            'message': f'Not enough stock for {menu_item.name}'
                        }, status=400)

                    menu_item.stock -= qty
                    menu_item.save()

                    OrderItem.objects.create(
                        order=order,
                        item=menu_item,
                        quantity=qty,
                        unit_price=price
                    )
                    total += price * qty

                tax = total * 0.05
                order.total_amount = round(total + tax, 2)
                order.save()

            return JsonResponse({'status': 'success', 'order_id': order.id})

        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)


# --- 9. Status Progression Endpoint for Kanban Board ---
@login_required(login_url='login')
def update_order_status(request, order_id):
    if not (request.user.is_staff or request.user.is_superuser):
        return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=403)

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            new_status = data.get('status')

            order = Order.objects.get(id=order_id)
            order.status = new_status
            order.save()

            return JsonResponse({'status': 'success', 'new_status': order.status})
        except Order.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Order not found'}, status=404)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

    return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=405)