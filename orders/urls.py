from django.urls import path
from .import views


urlpatterns = [
    path('place_order/', views.place_order, name = 'place_order'),
    path('payments/', views.payments, name = 'payments'),
    path('esewa_success/', views.esewa_success, name='esewa_success'),
    path('esewa_failure/', views.esewa_failure, name='esewa_failure'),
 
]
