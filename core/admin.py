from django.contrib import admin
from .models import Unit, Partner, Product

@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    list_display = ('name', 'code')

@admin.register(Partner)
class PartnerAdmin(admin.ModelAdmin):
    list_display = ('name', 'partner_type', 'phone')
    list_filter = ('partner_type',)

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('sku', 'name', 'product_type', 'unit', 'price')
    list_filter = ('product_type',)
    search_fields = ('name', 'sku')