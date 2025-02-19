from django.urls import path
from .import views


urlpatterns = [
    path('place_order/', views.place_order, name = 'place_order'),
    path('payments/', views.payments, name = 'payments'),
    path('khalti/initiate/', views.khalti_initiate, name='khalti_initiate'),
    path('khalti/return/', views.khalti_return, name='khalti_return'),
    path('khalti-verify/', views.khalti_verify_payment, name='khalti_verify_payment'),
    path('order_complete/', views.order_complete, name='order_complete'),

]
