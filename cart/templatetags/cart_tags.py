from django import template

register = template.Library()


@register.filter
def product_quantity(quantities, product_id):
    return quantities.get(product_id, 0) if isinstance(quantities, dict) else 0
