from django.shortcuts import get_object_or_404


# context_processors.py
from .models import Item

def cart_data(request):
    if not request.user.is_authenticated:
        cart = request.session.get('cart', {})
        items = [
            {
                'item': get_object_or_404(Item, id=item_data['item_id']),
                'quantity': item_data['quantity']
            }
            for item_data in cart.values()
        ]
        total_price = sum(item['item'].price * item['quantity'] for item in items)
        return {'cart_items': items, 'total_price': total_price}
    else:
        return {'cart_items': [], 'total_price': 0}  # Adjust this for logged-in users if needed
