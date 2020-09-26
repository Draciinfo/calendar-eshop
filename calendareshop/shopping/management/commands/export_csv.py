# -*- coding: utf-8 -*-
import logging
import csv
import datetime

from django.core.management.base import BaseCommand

from shopping.models import CustomOrder

logger = logging.getLogger(__name__)

def full_shipping_address(obj):
    fields = ['first_name', 'last_name', 'address', 'zip_code', 'city']
    if obj.shipping_same_as_billing:
        key = u'billing'
    else:
        key = u'shipping'
    values = [getattr(obj, u"%s_%s" % (key, val), u'') for val in fields]
    print values
    res = u"""{} {}
{}
{} {}""".format(*values)
    return res


class Command(BaseCommand):

    def handle(self, *args, **options):
        with open('order_export.csv', 'w') as f:
            writer = csv.writer(f, delimiter=';', quoting=csv.QUOTE_MINIMAL)
            # write header
            writer.writerow(['id', 'paid', 'email', 'shipping_type', 'shipping_address', 'order', 'note'])
            # write rows
            for order in CustomOrder.objects.filter(status=CustomOrder.PAID, confirmed__year=datetime.date.today().year):
                paid = order.is_paid()
                email = order.email
                shipping_address = full_shipping_address(order)
                items = u"\n".join(map(lambda x: str(x).decode('utf8'), order.items.all()))
                row = [order.id, paid, email, order.shipping_type, shipping_address, items, order.notes]
                row = [r.encode('utf8') if isinstance(r, basestring) else r for r in row]
                writer.writerow(row)




