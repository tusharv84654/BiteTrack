from rest_framework import serializers
from .models import MenuItem, Order, OrderItem


class MenuItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = MenuItem
        fields = ['id', 'name', 'category', 'price', 'stock', 'is_available']


class OrderItemSerializer(serializers.ModelSerializer):
    item_name = serializers.ReadOnlyField(source='item.name')

    class Meta:
        model = OrderItem
        fields = ['id', 'item', 'item_name', 'quantity', 'unit_price']
        read_only_fields = ['unit_price']


class OrderDetailSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    username = serializers.ReadOnlyField(source='user.username')

    class Meta:
        model = Order
        fields = ['id', 'user', 'username', 'status', 'total_amount', 'created_at', 'items']