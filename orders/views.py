import json
import datetime
import requests
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from carts.models import CartItem
from .forms import OrderForm
from .models import Order, Payment, OrderProduct
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.http import HttpResponse
from django.urls import reverse

def payments(request):
    return render(request, 'orders/payments.html')

def place_order(request, total=0, quantity=0):
    current_user = request.user
    cart_items = CartItem.objects.filter(user=current_user)
    cart_count = cart_items.count()
    if cart_count <= 0:
        return redirect('store')
    
    grand_total = 0
    tax = 0
    for cart_item in cart_items:
        total += (cart_item.product.price * cart_item.quantity)
        quantity += cart_item.quantity
    tax = (3 * total) / 100
    grand_total = total + tax
    
    if request.method == 'POST':
        form = OrderForm(request.POST)
        if form.is_valid():
            data = Order()
            data.user = current_user
            data.first_name = form.cleaned_data['first_name']
            data.last_name = form.cleaned_data['last_name']
            data.phone = form.cleaned_data['phone']
            data.email = form.cleaned_data['email'] 
            data.address_line_1 = form.cleaned_data['address_line_1']
            data.address_line_2 = form.cleaned_data['address_line_2']
            data.country = form.cleaned_data['country']
            data.state = form.cleaned_data['state']
            data.city = form.cleaned_data['city']
            data.order_note = form.cleaned_data['order_note']
            data.order_total = grand_total
            data.tax = tax
            data.ip = request.META.get('REMOTE_ADDR')
            data.save()
            
            # Generate order number based on current date and order ID
            yr = int(datetime.date.today().strftime('%Y'))
            dt = int(datetime.date.today().strftime('%d'))
            mt = int(datetime.date.today().strftime('%m'))
            d = datetime.date(yr, mt, dt)
            current_date = d.strftime("%Y%m%d")
            order_number = current_date + str(data.id)
            data.order_number = order_number
            data.save()
            
            order = Order.objects.get(user=current_user, is_ordered=False, order_number=data.order_number)
            context = {
                'order': order,
                'cart_items': cart_items,
                'total': total,
                'tax': tax,
                'grand_total': grand_total,
            }
            return render(request, 'orders/payments.html', context)
    else:
        return redirect('checkout')



def khalti_initiate(request):
    if request.method == "POST":
        order_number = request.POST.get("order_number")
        order = get_object_or_404(Order, order_number=order_number, is_ordered=False)
        
        # Build payload. Note: amount is in paisa (i.e., Rs * 100)
        payload = {
            "return_url": request.build_absolute_uri(reverse("khalti_return")),
            "website_url": settings.SITE_WEBSITE_URL,
            "amount": int(order.order_total * 100),
            "purchase_order_id": order.order_number,
            "purchase_order_name": "Order Payment",
            "customer_info": {
                "name": f"{order.first_name} {order.last_name}",
                "email": order.email,
                "phone": order.phone,
            }
            # Optionally, add amount_breakdown or product_details here if needed
        }
        
        headers = {
            "Authorization": f"Key {settings.KHALTI_SECRET_KEY}",
            "Content-Type": "application/json",
        }
        
        response = requests.post(settings.KHALTI_INITIATE_URL, json=payload, headers=headers)
        result = response.json()
        
        if result.get("payment_url"):
            # Optionally, you can save the returned pidx in your order if desired.
            # order.pidx = result.get("pidx")  # (if you add a field in Order model)
            # order.save()
            return redirect(result.get("payment_url"))
        else:
            error_message = json.dumps(result)
            return HttpResponse("Error initiating payment: " + error_message)
    return redirect("store")




def khalti_return(request):
    # Extract parameters from Khalti's callback
    pidx = request.GET.get("pidx")
    purchase_order_id = request.GET.get("purchase_order_id")
    
    # Optional: You can inspect additional GET parameters such as status, transaction_id, etc.
    
    # Verify payment using Khalti's lookup API
    lookup_url = "https://dev.khalti.com/api/v2/epayment/lookup/"
    payload = {"pidx": pidx}
    headers = {
        "Authorization": f"Key {settings.KHALTI_SECRET_KEY}",
        "Content-Type": "application/json",
    }
    
    lookup_response = requests.post(lookup_url, json=payload, headers=headers)
    lookup_result = lookup_response.json()
    
    # Only treat status "Completed" as success
    if lookup_result.get("status") == "Completed":
        try:
            order = Order.objects.get(order_number=purchase_order_id, is_ordered=False)
        except Order.DoesNotExist:
            return HttpResponse("Order not found.")
        
        # Create a Payment record
        payment = Payment.objects.create(
            user=order.user,
            payment_id=pidx,
            payment_method="Khalti",
            amount_paid=order.order_total,
            status="Completed"
        )
        order.payment = payment
        order.is_ordered = True
        order.save()
        
        # (Optional) Process cart items to create OrderProduct entries.
        
        # Redirect to an order confirmation page
        return redirect("order_complete")  # Ensure you have an 'order_complete' URL/view
    else:
        return HttpResponse("Payment verification failed. Status: " + lookup_result.get("status", "Unknown"))






def khalti_verify_payment(request):
    if request.method == "POST":
        data = json.loads(request.body)
        token = data.get("token")
        amount = data.get("amount")
        order_number = data.get("order_number")
        
        # Verify payment with Khalti
        verify_url = "https://khalti.com/api/v2/payment/verify/"
        payload = {
            "token": token,
            "amount": amount
        }
        headers = {
            "Authorization": "Key {settings.KHALTI_SECRET_KEY}",  # your actual secret key
            "Content-Type": "application/json",
        }
        response = requests.post(verify_url, json=payload, headers=headers)
        result = response.json()
        
        # If Khalti returns an identifier (e.g., "idx"), consider the payment verified
        if result.get("idx"):
            try:
                order = Order.objects.get(order_number=order_number, is_ordered=False)
            except Order.DoesNotExist:
                return JsonResponse({"status": "failed", "error": "Order not found"})
            
            # Create Payment record
            payment = Payment.objects.create(
                user=order.user,
                payment_id=result.get("idx"),
                payment_method="Khalti",
                amount_paid=order.order_total,
                status="Completed"
            )
            order.payment = payment
            order.is_ordered = True
            order.save()
            
            return JsonResponse({"status": "success"})
        else:
            return JsonResponse({"status": "failed", "error": "Verification failed"})
    return JsonResponse({"status": "invalid request"}, status=400)

from django.shortcuts import render



def order_complete(request):
   # Your view logic here
    return render(request, 'orders/order_complete.html')


# def order_complete(request):
#     order_number = request.GET.get("order_number")  # Retrieve order_number from query params
#     try:
#         order = Order.objects.get(order_number=order_number, is_ordered=True)
#         order_products = OrderProduct.objects.filter(order=order)
#         payment = Payment.objects.get(order=order)

#         context = {
#             "order": order,
#             "order_products": order_products,
#             "payment": payment,
#         }
#         return render(request, "orders/order_complete.html", context)
#     except Order.DoesNotExist:
#         return redirect("store") 