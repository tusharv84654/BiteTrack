from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect
from django.urls import include, path
from rest_framework.authtoken.views import obtain_auth_token
from orders import views

urlpatterns = [
    path('', views.home_view, name='home'),
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    path('kitchen/', views.kitchen_view, name='kitchen'),
    path('admin/', admin.site.urls),
    path('submit-order/', views.submit_order_web, name='submit_order_web'),
    path('kitchen/update-status/<int:order_id>/', views.update_order_status, name='update_order_status'),

    # Auth token generation
    path('api/auth/token/', obtain_auth_token, name='api_token_auth'),

    # Canteen REST API endpoints
    path('api/menu/', views.menu_list, name='api_menu_list'),
    path('api/orders/place/', views.place_order, name='api_place_order'),
    path('api/orders/my/', views.my_orders, name='api_my_orders'),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.BASE_DIR / 'orders' / 'templates')
