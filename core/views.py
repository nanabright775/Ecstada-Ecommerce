from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, get_object_or_404
from django.views.generic import ListView, DetailView, View
from django.shortcuts import redirect, render
from django.utils import timezone
from .forms import CouponForm, RefundForm, BillingAddressForm, CheckoutForm
from .models import Item, OrderItem, Order, BillingAddress, Payment, Coupon, Refund, Category
import requests
from django.http import JsonResponse
from .models import Item
import random
import string
import stripe
from .forms import RegisterForm
from .models import OtpToken
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.contrib.auth import authenticate, login, logout
from django.urls import reverse
stripe.api_key = settings.STRIPE_SECRET_KEY


def create_ref_code():
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=20))


def signin(request):
    if request.method == 'POST':
        email = request.POST['username']  # This should be email, not username
        password = request.POST['password']
        user = authenticate(request, email=email, password=password)
        
        if user is not None:
            login(request, user)
            merge_cart_for_logged_in_user(user, request)  # Merge session cart with user cart
            messages.success(request, f"Hi {request.user.username}, you are now logged-in")
            return redirect(request.GET.get('next', '/'))  # Redirect to the URL the user intended to visit
        else:
            messages.warning(request, "Invalid credentials")
            return render(request, "account/login.html")  # Show login page with warning
        
    return render(request, "account/login.html")


def verify_email(request, username):
    user = get_user_model().objects.get(username=username)
    user_otp = OtpToken.objects.filter(user=user).last()
    
    
    if request.method == 'POST':
        # valid token
        if user_otp.otp_code == request.POST['otp_code']:
            
            # checking for expired token
            if user_otp.otp_expires_at > timezone.now():
                user.is_active=True
                user.save()
                messages.success(request, "Account activated successfully!! Visit the Login page and Login.")
                return redirect("/")
            
            # expired token
            else:
                messages.warning(request, "The OTP has expired, get a new OTP!")
            return redirect(f"/verifyemail/{user.username}/", username=user.username)
        
        
        # invalid otp code
        else:
            messages.warning(request, "Invalid OTP entered, enter a valid OTP!")
            return redirect(f"/verifyemail/{user.username}/", username=user.username)
        
    context = {}
    return render(request, "account/verify_token.html", context)



def generate_otp():
    """Generate a random 6-digit OTP."""
    return str(random.randint(100000, 999999))


def resend_otp(request):
    if request.method == 'POST':
        user_email = request.POST["otp_email"]
        
        if get_user_model().objects.filter(email=user_email).exists():
            user = get_user_model().objects.get(email=user_email)
            otp = OtpToken.objects.create(user=user, otp_expires_at=timezone.now() + timezone.timedelta(minutes=5))
            
            
            # email variables
            subject="Email Verification"
            message = f"""
                                Hi {user.username}, here is your OTP {otp.otp_code} 
                                it expires in 5 minute, use the url below to redirect back to the website
                                http://127.0.0.1:8000/verifyemail/{user.username}
                                
                                """
            sender = "clintonmatics@gmail.com"
            receiver = [user.email, ]
        
        
            # send email
            send_mail(
                    subject,
                    message,
                    sender,
                    receiver,
                    fail_silently=False,
                )
            
            messages.success(request, "A new OTP has been sent to your email-address")
            return redirect(f"/verifyemail/{user.username}/", username=user.username)

        else:
            messages.warning(request, "This email dosen't exist in the database")
            return redirect("resend-otp/")
        
           
    context = {}
    return render(request, "account/resend_otp.html", context)


def signup(request):
    form = RegisterForm()
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Account created successfully! An OTP was sent to your Email")
            # return render(request, "account/verify_token.html", username=form.cleaned_data['email'])
            return render(request, "account/verify_token.html")

    context = {"form": form}
    return render(request, "account/signup.html", context)


@login_required
def payment_verification(request):
    reference = request.GET.get('reference')
    if reference:
        url = f"https://api.paystack.co/transaction/verify/{reference}"
        headers = {
            "Authorization": "Bearer sk_test_81268c8c2f76186a2cea978bf19099c8b35eb522",  # secret key
        }
        response = requests.get(url, headers=headers)
        data = response.json()

        if data.get('status') and data['data'].get('status') == 'success':
            try:
                payment_data = data['data']
                # Payment was successful
                payment = Payment()
                payment.paystack_charge_id = reference  # Store reference as the ID
                payment.user = request.user
                payment.amount = payment_data['amount'] / 100  # Convert from kobo to GHS
                payment.save()

                # Mark order as paid
                order = Order.objects.get(user=request.user, ordered=False)
                order.ordered = True
                order.payment = payment
                order.ref_code = create_ref_code()
                order.save()

                messages.success(request, "Payment was successful")
                return render(request, "thankyou.html")#to redirect to a page thanking the buyer
            except Exception as e:
                messages.error(request, "Error processing your payment.")
                return redirect("core:checkout")
        else:
            messages.error(request, "Payment verification failed")
            return redirect("core:checkout")
    else:
        messages.error(request, "No reference found")
        return redirect("core:checkout")




def logout_view(request):
    logout(request)
    messages.success(request, "You have been logged out successfully.")
    return redirect("/")  # Redirect to the sign-in page or any other page


class HomeView(ListView):
    template_name = "index.html"
    queryset = Item.objects.filter(is_active=True)
    context_object_name = 'items'



class OrderSummaryView(View):
    def get(self, *args, **kwargs):
        if self.request.user.is_authenticated:
            # Logic for logged-in users
            try:
                order = Order.objects.get(user=self.request.user, ordered=False)
                context = {
                    'object': order
                }
                return render(self.request, 'order_summary.html', context)
            except ObjectDoesNotExist:
                messages.error(self.request, "You do not have an active order")
                return redirect("/")
        else:
            # Logic for anonymous users (session-based cart)
            cart = self.request.session.get('cart', {})
            items = []
            total_price = 0

            for slug, item_data in cart.items():
                item = get_object_or_404(Item, slug=slug)
                items.append({
                    'item': item,
                    'quantity': item_data['quantity']
                })
                total_price += item.price * item_data['quantity']

            if items:
                context = {
                    'items': items,
                    'total_price': total_price
                }
                return render(self.request, 'order_summary.html', context)
            else:
                messages.error(self.request, "Your cart is empty.")
                return redirect("/")



#To display the users paid item
class MyOrderedSummaryView(LoginRequiredMixin, View):
    def get(self, *args, **kwargs):
        try:
            order = Order.objects.filter(user=self.request.user, ordered=True).last()
            if order:
                context = {
                    'object': order
                }
                return render(self.request, 'my_order_summary.html', context)
            else:
                messages.error(self.request, "You do not have any completed orders.")
                return redirect("core:shop") 
        except ObjectDoesNotExist:
            messages.error(self.request, "You do not have an active order")
            return redirect("core:shop")  # Redirect to a valid view name



class ShopView(ListView):
    model = Item
    paginate_by = 6
    template_name = "shop.html"

    
class ItemDetailView(DetailView):
    model = Item
    template_name = "product-detail.html"


class CategoryView(View):
    def get(self, *args, **kwargs):
        category = Category.objects.get(slug=self.kwargs['slug'])
        item_query = Item.objects.filter(category=category, is_active=True)
        
        # Get the price range from the query parameters
        lower = self.request.GET.get('lower')
        upper = self.request.GET.get('upper')
        
        if lower and upper:
            item_query = item_query.filter(price__gte=lower, price__lte=upper)
        
        context = {
            'object_list': item_query,
            'category_title': category,
            'category_description': category.description,
            'category_image': category.image
        }
        return render(self.request, "category.html", context)



 


class CheckoutView(LoginRequiredMixin, View):
    login_url = '/signin/'  # Redirect to login if not authenticated

    def get(self, *args, **kwargs):
        # Check if the user is logged in
        if not self.request.user.is_authenticated:
            # Redirect to login page, with 'next' parameter set to the current checkout page
            return redirect(f"{self.login_url}?next=checkout")

        try:
            # For logged-in users, retrieve the order
            order = Order.objects.get(user=self.request.user, ordered=False)
            form = BillingAddressForm()
            context = {
                'form': form,
                'couponform': CouponForm(),
                'order': order,
                'DISPLAY_COUPON_FORM': True
            }
            return render(self.request, "checkout.html", context)

        except ObjectDoesNotExist:
            messages.info(self.request, "You do not have an active order")
            return redirect("core:checkout")

    def post(self, *args, **kwargs):
        form = BillingAddressForm(self.request.POST or None)
        if not self.request.user.is_authenticated:
            # Redirect to login page if not authenticated
            return JsonResponse({"success": False, "error": "You need to log in to proceed with checkout."})

        try:
            order = Order.objects.get(user=self.request.user, ordered=False)
            if form.is_valid():
                street_address = form.cleaned_data.get('street_address')
                apartment_address = form.cleaned_data.get('apartment_address')
                country = form.cleaned_data.get('country')
                zip_code = form.cleaned_data.get('zip')

                # Saving billing address
                billing_address = BillingAddress(
                    user=self.request.user,
                    street_address=street_address,
                    apartment_address=apartment_address,
                    country=country,
                    zip=zip_code
                )
                billing_address.save()

                # Link the billing address to the order
                order.billing_address = billing_address
                order.save()

                # Return a JSON response indicating success
                return JsonResponse({"success": True})

            else:
                # Form is invalid, return error message
                return JsonResponse({"success": False, "error": "Invalid form data"})

        except ObjectDoesNotExist:
            messages.error(self.request, "You do not have an active order")
            return JsonResponse({"success": False, "error": "No active order"})




def add_to_cart(request, slug):
    item = get_object_or_404(Item, slug=slug)

    # If the user is not logged in, use session to handle the cart
    if not request.user.is_authenticated:
        cart = request.session.get('cart', {})
        if slug in cart:
            cart[slug]['quantity'] += 1
        else:
            cart[slug] = {
                'item_id': item.id,
                'quantity': 1,
            }
        request.session['cart'] = cart
        messages.info(request, "Item added to your cart.")
        return redirect("core:order-summary")

    # If user is logged in, continue with the usual cart logic
    order_item, created = OrderItem.objects.get_or_create(
        item=item,
        user=request.user,
        ordered=False
    )
    order_qs = Order.objects.filter(user=request.user, ordered=False)
    if order_qs.exists():
        order = order_qs[0]
        if order.items.filter(item__slug=item.slug).exists():
            order_item.quantity += 1
            order_item.save()
            messages.info(request, "Item quantity was updated.")
        else:
            order.items.add(order_item)
            messages.info(request, "Item was added to your cart.")
    else:
        ordered_date = timezone.now()
        order = Order.objects.create(
            user=request.user, ordered_date=ordered_date)
        order.items.add(order_item)
        messages.info(request, "Item was added to your cart.")
    return redirect("core:order-summary")



#merge the cart for a logged in user
def merge_cart_for_logged_in_user(user, request):
    # Get the cart from the session
    session_cart = request.session.get('cart', {})

    if not session_cart:
        return

    # Get or create the user's order
    order_qs = Order.objects.filter(user=user, ordered=False)
    if order_qs.exists():
        order = order_qs[0]
    else:
        ordered_date = timezone.now()
        order = Order.objects.create(user=user, ordered_date=ordered_date)

    # Merge session cart with user's order
    for slug, item_data in session_cart.items():
        item = get_object_or_404(Item, id=item_data['item_id'])
        order_item, created = OrderItem.objects.get_or_create(
            item=item,
            user=user,
            ordered=False
        )
        if created:
            order_item.quantity = item_data['quantity']
            order_item.save()
        else:
            order_item.quantity += item_data['quantity']
            order_item.save()

        if not order.items.filter(item__slug=item.slug).exists():
            order.items.add(order_item)

    # Clear the session cart
    request.session.pop('cart', None)




def remove_from_cart(request, slug):
    item = get_object_or_404(Item, slug=slug)

    # If user is not logged in, remove item from session cart
    if not request.user.is_authenticated:
        cart = request.session.get('cart', {})
        if slug in cart:
            del cart[slug]
            request.session['cart'] = cart
            messages.info(request, "Item was removed from your cart.")
        else:
            messages.info(request, "Item was not in your cart.")
        return redirect("core:order-summary")

    # Continue with normal cart removal if user is logged in
    order_qs = Order.objects.filter(user=request.user, ordered=False)
    if order_qs.exists():
        order = order_qs[0]
        if order.items.filter(item__slug=item.slug).exists():
            order_item = OrderItem.objects.filter(
                item=item,
                user=request.user,
                ordered=False
            )[0]
            order.items.remove(order_item)
            messages.info(request, "Item was removed from your cart.")
        else:
            messages.info(request, "Item was not in your cart.")
    else:
        messages.info(request, "You don't have an active order.")
    return redirect("core:order-summary")



def remove_single_item_from_cart(request, slug):
    item = get_object_or_404(Item, slug=slug)

    # If the user is not logged in, modify the cart in session
    if not request.user.is_authenticated:
        cart = request.session.get('cart', {})
        if slug in cart:
            if cart[slug]['quantity'] > 1:
                cart[slug]['quantity'] -= 1
            else:
                del cart[slug]
            request.session['cart'] = cart
            messages.info(request, "This item quantity was updated.")
        else:
            messages.info(request, "Item was not in your cart.")
        return redirect("core:order-summary")

    # Continue with the usual logic for logged-in users
    order_qs = Order.objects.filter(user=request.user, ordered=False)
    if order_qs.exists():
        order = order_qs[0]
        # check if the order item is in the order
        if order.items.filter(item__slug=item.slug).exists():
            order_item = OrderItem.objects.filter(
                item=item,
                user=request.user,
                ordered=False
            )[0]
            if order_item.quantity > 1:
                order_item.quantity -= 1
                order_item.save()
            else:
                order.items.remove(order_item)
            messages.info(request, "This item quantity was updated.")
            return redirect("core:order-summary")
        else:
            messages.info(request, "Item was not in your cart.")
            return redirect("core:product", slug=slug)
    else:
        messages.info(request, "You don't have an active order.")
        return redirect("core:product", slug=slug)



def get_coupon(request, code):
    try:
        coupon = Coupon.objects.get(code=code)
        return coupon
    except ObjectDoesNotExist:
        messages.info(request, "This coupon does not exist")
        return redirect("core:checkout")


class AddCouponView(View):
    def post(self, *args, **kwargs):
        form = CouponForm(self.request.POST or None)
        if form.is_valid():
            try:
                code = form.cleaned_data.get('code')
                order = Order.objects.get(
                    user=self.request.user, ordered=False)
                order.coupon = get_coupon(self.request, code)
                order.save()
                messages.success(self.request, "Successfully added coupon")
                return redirect("core:checkout")

            except ObjectDoesNotExist:
                messages.info(requests, "You do not have an active order")
                return redirect("core:checkout")


class RequestRefundView(View):
    def get(self, *args, **kwargs):
        form = RefundForm()
        context = {
            'form': form
        }
        return render(self.request, "request_refund.html", context)

    def post(self, *args, **kwargs):
        form = RefundForm(self.request.POST)
        if form.is_valid():
            ref_code = form.cleaned_data.get('ref_code')
            message = form.cleaned_data.get('message')
            email = form.cleaned_data.get('email')
            # edit the order
            try:
                order = Order.objects.get(ref_code=ref_code)
                order.refund_requested = True
                order.save()

                # store the refund
                refund = Refund()
                refund.order = order
                refund.reason = message
                refund.email = email
                refund.save()

                messages.info(self.request, "Your request was received")
                return redirect("core:request-refund")

            except ObjectDoesNotExist:
                messages.info(self.request, "This order does not exist")
                return redirect("core:request-refund")



def filter_products(request):
    try:
        lower = float(request.GET.get('lower', 0))
        upper = float(request.GET.get('upper', 10000))
    except ValueError:
        lower = 0
        upper = 10000
    filtered_items = Item.objects.filter(price__gte=lower, price__lte=upper, is_active=True)

    print(filtered_items)
    print(f'this is lower:{lower}')
    print(f'this is upper: {upper}')
    products = []
    for item in filtered_items:
        products.append({
            'title': item.title,
            'price': item.price,
            'image_url': item.image.url,
            'slug': item.slug
        })

    return JsonResponse({'products': products})



@login_required
def my_orders(request):
    # Fetch the orders for the logged-in user
    orders = Order.objects.filter(user=request.user, ordered=True).prefetch_related('items', 'billing_address')

    context = {
        'orders': orders
    }
    return render(request, 'my_orders.html', context)



@login_required
def delete_order(request, order_id):
    # Fetch the order
    order = get_object_or_404(Order, id=order_id, user=request.user)
    
    if request.method == "POST":
        order.delete()
        messages.success(request, "Order deleted successfully.")
        return redirect('core:my-orders')


def thank_you_view(request):
    return render(request, 'thankyou.html')


#users profile
def user_profile(request):
    if not request.user.is_authenticated:
        return redirect('/signin')  # Redirect to login if not authenticated
    
    user = request.user
    orders = Order.objects.filter(user=user).order_by('-ordered_date')
    
    context = {
        'user': user,
        'orders': orders,
    }
    return render(request, 'account/user_profile.html', context)
