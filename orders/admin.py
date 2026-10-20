from django.contrib import admin
from django.contrib.auth.models import Group
from .models import MenuItem, Order, OrderItem

# Unregister default Groups model from admin dashboard
admin.site.unregister(Group)


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'total_amount', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    inlines = [OrderItemInline]


@admin.register(MenuItem)
class MenuItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'price', 'stock', 'is_available')
    list_filter = ('category', 'is_available')