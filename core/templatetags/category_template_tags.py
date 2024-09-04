from django import template
from django.utils.safestring import mark_safe

from core.models import Category

register = template.Library()


@register.simple_tag
def categories():
    items = Category.objects.filter(is_active=True).order_by('title')
    items_li = ""
    for i in items:
        items_li += """<li><a href="/category/{}">{}</a></li>""".format(i.slug, i.title)
    return mark_safe(items_li)

@register.simple_tag
def categories_mobile():
    items = Category.objects.filter(is_active=True).order_by('title')
    items_li = ""
    for i in items:
        items_li += """<li class="item-menu-mobile"><a href="/category/{}">{}</a></li>""".format(i.slug, i.title)
    return mark_safe(items_li)


@register.simple_tag
def categories_li_a():
    items = Category.objects.filter(is_active=True).order_by('title')
    items_li_a = ""
    for i in items:
        items_li_a += """<li class="list-group">
                            <a href="/category/{}" class="s-text13">{}</a>
                         </li>""".format(i.slug, i.title)
    return mark_safe(items_li_a)


@register.simple_tag
def categories_div():
    """
    Generate HTML for displaying categories in a Bootstrap card layout.
    :return: Safe HTML string
    """
    items = Category.objects.filter(is_active=True).order_by('title')[:10]  # Limit to 10 items
    item_div_list = ""
    
    for i, j in enumerate(items):
        item_div = f"""
        <div class="col-md-3 mb-4">
            <div class="card">
                <img src="{j.image.url}" class="card-img-top img-fluid " alt="{j.title}" style="object-fit: cover; height: 300px;">
                <div class="card-body">
                    <h5 class="card-title">{j.title}</h5>
                    <p class="card-text">{j.description[:100]}...</p>
                    <a href="{j.get_absolute_url()}" class="btn btn-primary">View Category</a>
                </div>
            </div>
        </div>
        """
        item_div_list += item_div

    return mark_safe(item_div_list)