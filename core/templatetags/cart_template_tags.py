from django import template
from core.models import Order

register = template.Library()


@register.filter
def cart_item_count(request):
    if request.user.is_authenticated:
        # For logged-in users
        order_qs = Order.objects.filter(user=request.user, ordered=False)
        if order_qs.exists():
            return order_qs[0].items.count()
    else:
        # For anonymous users
        cart = request.session.get('cart', {})
        return sum(item['quantity'] for item in cart.values())
    return 0
