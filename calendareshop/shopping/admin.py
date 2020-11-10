# -*- coding: utf-8 -*-
import datetime
import logging

from django.contrib import admin
from django.conf import settings
from django.forms import Textarea
from django.utils.translation import ugettext_lazy as _
from django.db import models as django_models

from plata.shop.admin import OrderAdmin, OrderPaymentAdmin, OrderItemInline, OrderStatusInline
from plata.shop import signals
from plata.shop import models as plata_models
from modeltranslation.admin import TranslationAdmin

from . import models
from notifications import SendCompletedHandler
from import_export.admin import ExportActionMixin

logger = logging.getLogger(__name__)


class ProductPriceInline(admin.TabularInline):
    model = models.ProductPrice
    extra = 0


class ProductAdmin(TranslationAdmin):
    inlines = [ProductPriceInline]
    list_display = ('is_active', 'name', 'items_in_stock', 'ordering')
    list_display_links = ('name',)
    list_filter = ('is_active',)
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name', 'description')
    filter_horizontal = ('projects',)
    readonly_fields = ['items_in_stock', 'is_available']

admin.site.register(models.Product, ProductAdmin)


class CustomOrderItemInline(OrderItemInline):
    exclude = ['product', 'sku', '_unit_price', '_unit_tax', 'tax_rate', 'tax_class', '_line_item_tax', '_line_item_price', '_line_item_discount', 'data']


class CustomOrderAdmin(ExportActionMixin, OrderAdmin):
    inlines = [CustomOrderItemInline, OrderStatusInline]
    list_display = (
        'admin_order_id', 'created', 'full_name', 'email', 'status', 'total_custom',
        'admin_is_paid', 'shipping_type', 'payment_type', 'notes', 'additional_info')
    list_filter = ('status', 'shipping_type', 'payment_type', 'items__product')
    actions = [
        'complete_order',
    ]
    readonly_fields = ['full_shipping_address', 'subtotal', 'payment', 'payment_type', 'shipping']
    formfield_overrides = {
        django_models.TextField: {'widget': Textarea(attrs={'rows':3, 'cols':40})},
    }

    def get_fieldsets(self, request, obj=None):
        fieldsets = [
            (None, {
                'fields': (
                    'created', 'confirmed', 'email',
                    'language_code', 'status'),
            }),
            (_('Billing address'), {
                'fields': ['full_shipping_address', 'notes'] + models.Order.address_fields('billing_'),
            }),
            (_('Shipping address'), {
                'fields': (
                    ['shipping_same_as_billing'] +
                    models.Order.address_fields('shipping_')),
            }),
            (_('Order items'), {
                'fields': ('subtotal', ),
            }),
            (_('Shipping'), {
                'fields': ('shipping', 'shipping_cost', 'shipping_tax', 'shipping_type'),
            }),
            (_('Payment'), {
                'fields': ('payment', 'payment_type'),
            }),
            (_('Total'), {
                'fields': ('currency', 'total', 'paid'),
            }),
        ]
        if obj and obj.shipping_same_as_billing:
            del fieldsets[2]
        return fieldsets

    def complete_order(self, request, queryset):
        for item in queryset:
            if item.statuses.filter(status__gte=models.CustomOrder.PAID).exists():
                logger.debug("Completing order: %s, sending notification email.", item)
                if item.shipping_type == models.Shipping.objects.get(code='cpost'):
                    # send notification ONLy if sending by Ceska Posta!
                    SendCompletedHandler(always_bcc=settings.ALWAYS_BCC)(item.__class__, order=item)

                # create new OrderStatus(status=COMPLETED) if not already created
                status = plata_models.OrderStatus(order=item, status=models.CustomOrder.COMPLETED, notes="Order completed by admin interface")
                status.save()
    complete_order.short_description = "Complete order (package sent)"

    def get_queryset(self, request):
        qs = super(CustomOrderAdmin, self).get_queryset(request)
        if 'status__exact' not in request.GET:
            qs = qs.filter(status__gte=models.CustomOrder.CONFIRMED)
        return qs

    def full_name(self, obj):
        return "%s %s" % (obj.billing_first_name, obj.billing_last_name)

    def full_shipping_address(self, obj):
        fields = ['first_name', 'last_name', 'address', 'zip_code', 'city']
        if obj.shipping_same_as_billing:
            key = u'billing'
        else:
            key = u'shipping'
        values = [getattr(obj, u"%s_%s" % (key, val), u'') for val in fields]
        res = u"""{} {}<br />
{}<br />
{} {}""".format(*values)
        return res
    full_shipping_address.allow_tags = True
    full_shipping_address.short_description = _("Full shipping address")

    def total_custom(self, obj):
        return settings.CURRENCY_FORMATS[obj.currency].format(obj.total)
    total_custom.short_description = "Celkem"

    def shipping(self, obj):
        return int(obj.shipping)

    def payment(self, obj):
        return "%.2f" % float(obj.payment)


admin.site.register(models.CustomOrder, CustomOrderAdmin)


admin.site.register(models.Region)
admin.site.register(models.Country)


class ShippingAdmin(TranslationAdmin):
    pass

admin.site.register(models.Shipping, ShippingAdmin)


class PaymentAdmin(TranslationAdmin):
    list_display = ('name', 'module', 'is_active')

admin.site.register(models.Payment, PaymentAdmin)


class ShippingPaymentAdmin(admin.ModelAdmin):
    list_filter = ('shipping', 'payment')

admin.site.register(models.ShippingPayment, ShippingPaymentAdmin)


class ShippingRegionPriceInline(admin.TabularInline):
    model = models.ShippingRegionPrice
    extra = 0


class ShippingRegionAdmin(admin.ModelAdmin):
    inlines = [ShippingRegionPriceInline]
    list_filter = ('shipping', 'region')


admin.site.register(models.ShippingRegion, ShippingRegionAdmin)


# TODO make django adminaction to confirm payment, move logic to OrderPayment model
#def confirm_payment(modeladmin, request, queryset):
#    for item in queryset:
#        item.


class CustomOrderPaymentAdmin(OrderPaymentAdmin):

    def save_form(self, request, form, *args, **kwargs):
        # store old status value
        old_status = None
        if form.instance.pk:
            old_status = plata_models.OrderPayment.objects.get(pk=form.instance.pk).status

        obj = super(CustomOrderPaymentAdmin, self).save_form(request, form, *args, **kwargs)

        # test if payment has been authorized
        if old_status != obj.status and obj.status == plata_models.OrderPayment.AUTHORIZED:
            obj.authorized = datetime.datetime.now()
            # payment has been paid --> send order_paid signal
            signals.order_paid.send(
                sender=obj,
                order=obj.order,
                payment=obj,
                request=request
            )
            # create new OrderStatus(status=PAID) if not already created
            if not obj.order.statuses.filter(status__gte=models.CustomOrder.PAID).exists():
                status = plata_models.OrderStatus(order=obj.order, status=models.CustomOrder.PAID)
                status.save()

        return obj


admin.site.unregister(plata_models.Order)
admin.site.unregister(plata_models.OrderPayment)
admin.site.register(plata_models.OrderPayment, CustomOrderPaymentAdmin)
