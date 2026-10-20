import json
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


# 1. Catalog Endpoint: Anyone can view active menu items
@api_view(['GET'])
@permission_classes([AllowAny])
def menu_list(request):
    items = MenuItem.objects.filter(is_available=True)
    serializer = MenuItemSerializer(items, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


# 2. Order Placement (API): Atomic checkout with stock deduction
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

                # Deduct stock and record line item
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


# 3. Order History: Logged-in student views their own orders
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_orders(request):
    orders = Order.objects.filter(user=request.user).prefetch_related('items__item')
    serializer = OrderDetailSerializer(orders, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


# --- Template Views ---

# 4. Student Menu Catalog Page
@login_required(login_url='login')
def home_view(request):
    # Staff / admin are redirected to the kitchen dashboard
    if request.user.is_staff or request.user.is_superuser:
        return redirect('kitchen')

    items = MenuItem.objects.all()
    return render(request, 'index.html', {
        'items': items,
        'username': request.user.username
    })


# 5. Dedicated Kitchen / Admin Orders 3-Column Kanban View
@login_required(login_url='login')
def kitchen_view(request):
    if not (request.user.is_staff or request.user.is_superuser):
        return redirect('home')

    all_orders = Order.objects.all().order_by('-created_at').prefetch_related('items__item')

    pending_orders = []
    preparing_orders = []
    ready_orders = []

    # Safe categorization: No order will ever be omitted
    for order in all_orders:
        st = (order.status or '').strip().lower()
        if st == 'preparing':
            preparing_orders.append(order)
        elif st in ['ready', 'completed']:
            ready_orders.append(order)
        else:
            # Captures 'pending', empty string, None, or any unhandled status
            pending_orders.append(order)

    return render(request, 'orders_dashboard.html', {
        'pending_orders': pending_orders,
        'preparing_orders': preparing_orders,
        'ready_orders': ready_orders,
    })


# 6. Login View (Auto-registers new students or authenticates existing users)
def user_login(request):
    if request.user.is_authenticated:
        if request.user.is_staff or request.user.is_superuser:
            return redirect('kitchen')
        return redirect('home')

    error = None
    if request.method == 'POST':
        u = request.POST.get('username', '').strip()
        p = request.POST.get('password', '').strip()
        remember_me = request.POST.get('remember_me')

        if not u or not p:
            error = "Username and password are required."
            return render(request, 'login.html', {'error': error})

        # Check existing vs new student
        if User.objects.filter(username=u).exists():
            user = authenticate(request, username=u, password=p)
            if user is None:
                error = "Incorrect password for existing user."
                return render(request, 'login.html', {'error': error})
        else:
            user = User.objects.create_user(username=u, password=p)

        login(request, user)
        if remember_me:
            request.session.set_expiry(604800)  # 7 days
        else:
            request.session.set_expiry(0)       # Closes on browser exit

        if user.is_staff or user.is_superuser:
            return redirect('kitchen')
        return redirect('home')

    return render(request, 'login.html', {'error': error})


# 7. Logout View
def user_logout(request):
    logout(request)
    return redirect('login')


# 8. Web Checkout Handler for POS Cart
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

                    # Deduct inventory count
                    menu_item.stock -= qty
                    menu_item.save()

                    # Create order line item
                    OrderItem.objects.create(
                        order=order,
                        item=menu_item,
                        quantity=qty,
                        unit_price=price
                    )
                    total += price * qty

                # Add 5% campus tax
                tax = total * 0.05
                order.total_amount = round(total + tax, 2)
                order.save()

            return JsonResponse({'status': 'success', 'order_id': order.id})

        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)


# 9. Status Progression Endpoint for Kanban Board
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