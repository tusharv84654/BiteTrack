from django.db import models
from django.contrib.auth.models import User


class MenuItem(models.Model):
    CATEGORY_CHOICES = [
        ('Meals', 'Meals'),
        ('Snacks', 'Snacks'),
        ('Drinks', 'Drinks'),
        ('Bakery', 'Bakery'),
    ]

    name = models.CharField(max_length=100)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default='Snacks')
    price = models.DecimalField(max_digits=6, decimal_places=2)
    stock = models.PositiveIntegerField(default=10)
    description = models.TextField(blank=True, default='')
    is_available = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} (Rs. {self.price})"


class Order(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('PREPARING', 'Preparing'),
        ('READY', 'Ready'),
        ('COMPLETED', 'Completed'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders')
    total_amount = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Order #{self.id} - {self.user.username} ({self.status})"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    item = models.ForeignKey(MenuItem, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=6, decimal_places=2)

    def __str__(self):
        return f"{self.quantity}x {self.item.name}"