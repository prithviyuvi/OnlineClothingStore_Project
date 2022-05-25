import django
from django.contrib.auth.models import User
from store.models import Address, Cart, Category, Order, Product
from django.shortcuts import redirect, render, get_object_or_404, HttpResponse
from .forms import RegistrationForm, AddressForm
from django.contrib import messages
from django.views import View
import decimal
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator # for Class Based Views
import urllib
import bs4 as bs
import re
import razorpay
from django.views.decorators.csrf import csrf_exempt
from jewelryshop.settings import RAZORPAY_API_KEY, RAZORPAY_API_SECRET_KEY
from .search import google, duck, bing, givewater

# Create your views here.

def home(request):
    categories = Category.objects.filter(is_active=True, is_featured=True)[:3]
    products = Product.objects.filter(is_active=True, is_featured=True)[:8]
    context = {
        'categories': categories,
        'products': products,
    }
    return render(request, 'store/index.html', context)


def detail(request, slug):
    product = get_object_or_404(Product, slug=slug)
    related_products = Product.objects.exclude(id=product.id).filter(is_active=True, category=product.category)
    context = {
        'product': product,
        'related_products': related_products,

    }
    return render(request, 'store/detail.html', context)


def all_categories(request):
    categories = Category.objects.filter(is_active=True)
    return render(request, 'store/categories.html', {'categories':categories})


def category_products(request, slug):
    category = get_object_or_404(Category, slug=slug)
    products = Product.objects.filter(is_active=True, category=category)
    categories = Category.objects.filter(is_active=True)
    context = {
        'category': category,
        'products': products,
        'categories': categories,
    }
    return render(request, 'store/category_products.html', context)


# Authentication Starts Here

class RegistrationView(View):
    def get(self, request):
        form = RegistrationForm()
        return render(request, 'account/register.html', {'form': form})
    
    def post(self, request):
        form = RegistrationForm(request.POST)
        if form.is_valid():
            messages.success(request, "Congratulations! Registration Successful!")
            form.save()
        return render(request, 'account/register.html', {'form': form})
        

@login_required
def profile(request):
    addresses = Address.objects.filter(user=request.user)
    orders = Order.objects.filter(user=request.user)
    return render(request, 'account/profile.html', {'addresses':addresses, 'orders':orders})


@method_decorator(login_required, name='dispatch')
class AddressView(View):
    def get(self, request):
        form = AddressForm()
        return render(request, 'account/add_address.html', {'form': form})

    def post(self, request):
        form = AddressForm(request.POST)
        if form.is_valid():
            user=request.user
            locality = form.cleaned_data['locality']
            city = form.cleaned_data['city']
            state = form.cleaned_data['state']
            reg = Address(user=user, locality=locality, city=city, state=state)
            reg.save()
            messages.success(request, "New Address Added Successfully.")
        return redirect('store:profile')


@login_required
def remove_address(request, id):
    a = get_object_or_404(Address, user=request.user, id=id)
    a.delete()
    messages.success(request, "Address removed.")
    return redirect('store:profile')

@login_required
def add_to_cart(request):
    user = request.user
    product_id = request.GET.get('prod_id')
    product = get_object_or_404(Product, id=product_id)

    # Check whether the Product is alread in Cart or Not
    item_already_in_cart = Cart.objects.filter(product=product_id, user=user)
    if item_already_in_cart:
        cp = get_object_or_404(Cart, product=product_id, user=user)
        cp.quantity += 1
        cp.save()
    else:
        Cart(user=user, product=product).save()
    
    return redirect('store:cart')


@login_required
def cart(request):
    user = request.user
    cart_products = Cart.objects.filter(user=user)

    # Display Total on Cart Page
    amount = decimal.Decimal(0)
    shipping_amount = decimal.Decimal(10)
    # using list comprehension to calculate total amount based on quantity and shipping
    cp = [p for p in Cart.objects.all() if p.user==user]
    if cp:
        for p in cp:
            temp_amount = (p.quantity * p.product.price)
            amount += temp_amount

    # Customer Addresses
    addresses = Address.objects.filter(user=user)

    context = {
        'cart_products': cart_products,
        'amount': amount,
        'shipping_amount': shipping_amount,
        'total_amount': amount + shipping_amount,
        'addresses': addresses,
    }
    return render(request, 'store/cart.html', context)


@login_required
def remove_cart(request, cart_id):
    if request.method == 'GET':
        c = get_object_or_404(Cart, id=cart_id)
        c.delete()
        messages.success(request, "Product removed from Cart.")
    return redirect('store:cart')


@login_required
def plus_cart(request, cart_id):
    if request.method == 'GET':
        cp = get_object_or_404(Cart, id=cart_id)
        cp.quantity += 1
        cp.save()
    return redirect('store:cart')


@login_required
def minus_cart(request, cart_id):
    if request.method == 'GET':
        cp = get_object_or_404(Cart, id=cart_id)
        # Remove the Product if the quantity is already 1
        if cp.quantity == 1:
            cp.delete()
        else:
            cp.quantity -= 1
            cp.save()
    return redirect('store:cart')


@login_required
def checkout(request):
    user = request.user
    address_id = request.GET.get('address')
    
    address = get_object_or_404(Address, id=address_id)
    # Get all the products of User in Cart
    cart = Cart.objects.filter(user=user)
    for c in cart:
        # Saving all the products from Cart to Order
        Order(user=user, address=address, product=c.product, quantity=c.quantity).save()
        # And Deleting from Cart
        c.delete()
    return redirect('store:orders')



@csrf_exempt
def success(request):
    return render(request, "success.html")


@login_required
def orders(request):
    all_orders = Order.objects.filter(user=request.user).order_by('-ordered_date')
    return render(request, 'store/orders.html', {'orders': all_orders})





def shop(request):
    return render(request, 'store/shop.html')


def test(request):
    return render(request, 'store/test.html')

# article web scrapping
def articles(request):
    # *****************  source1   ********************
    source = urllib.request.urlopen('https://en.wikipedia.org/wiki/Fashion').read()
    soup = bs.BeautifulSoup(source, 'lxml')
    text = []
    for paragraph in soup.find_all('p'):
        text.append(paragraph.text)
    tex = []
    for t in text:
        t = re.sub(r'\[[0-9]*\]', ' ', t)
        tex.append(t)
    # source 1 image scrapping
    list = []
    for item in soup.find_all('img'):
        list.append(item['src'])
    text.clear()
    # *****************  source2  ********************
    source2 = urllib.request.urlopen('https://hmgroup.com/sustainability/circular-and-climate-positive/recycling/').read()
    soup2 = bs.BeautifulSoup(source2, 'lxml')
    text1 = []
    for paragraph in soup2.find_all('p'):
        text1.append(paragraph.text)
    tex1 = []
    for t in text1:
        t = re.sub(r'\[[0-9]*\]', ' ', t)
        tex1.append(t)
    text1.clear()

    # *****************  source3  ********************

    source3 = urllib.request.urlopen('https://www.vogue.in/fashion').read()
    soup3 = bs.BeautifulSoup(source3, 'lxml')
    text2 = []
    for paragraph in soup3.find_all('p'):
        text2.append(paragraph.text)

    tex2 = []
    for t in text2:
        t = re.sub(r'\[[0-9]*\]', ' ', t)
        tex2.append(t)

    text2.clear()


    return render(request, 'store/articles.html',
                  {'text': tex, 'text2': tex1[:len(tex1) - 30], 'text3': tex2[2:len(tex2) - 20], 'list2': list[2],
                   'list3': list[3], 'list4': list[4], 'list5': list[5]})



client = razorpay.Client(auth=(RAZORPAY_API_KEY, RAZORPAY_API_SECRET_KEY))
def index(request):
    """amount = decimal.Decimal(0)
    shipping_amount = decimal.Decimal(10)
    # using list comprehension to calculate total amount based on quantity and shipping
    cp = [p for p in Cart.objects.all() if p.user == user]
    if cp:
        for p in cp:
            temp_amount = (p.quantity * p.product.price)
            amount += temp_amount
    context = {
        'cart_products': cart_products,
        'amount': amount,
        'shipping_amount': shipping_amount,
        'total_amount': amount + shipping_amount,
        'addresses': addresses,
    }"""
    order_amount = 50000
    order_currency = 'INR'
    payment_order = client.order.create(dict(amount=order_amount, currency=order_currency, payment_capture='1'))
    payment_id = payment_order['id']
    context = {
        'amount': {{amount}}, 'api_key':rzp_test_JbdMtn5pZ84MBr
    }
    return redirect('store:orders')

import time
import googlemaps
import pandas as pd

def storelocator(request):


    return render(request,'store/storelocator.html')



#---------search enginee------------------------


def searchhome(request):
    #return render(request, 'store/serachhome.html')
    return render(request, 'store/serachhome.html')


def searchresults(request):
    if request.method == "POST":
        result = request.POST.get('search')
        google_link, google_text = google(result)
        google_data = zip(google_link, google_text)
        duck_link, duck_text = duck(result)
        duck_data = zip(duck_link, duck_text)
        bing_link, bing_text = bing(result)
        bing_data = zip(bing_link, bing_text)
        givewater_link, givewater_text = givewater(result)
        givewater_data = zip(givewater_link, givewater_text)

        if result == '':
            return redirect('searchhome')
        else:
            return render(request, 'store/searchresults.html',
                          {'search': result, 'google': google_data, 'duck': duck_data, 'bing': bing_data,
                           'givewater': givewater_data})













































