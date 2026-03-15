from django.contrib import admin
from .models import *

@admin.register(Batch) 
class BatchAdmin(admin.ModelAdmin):
    list_display = ('batch_code', 'product', 'supplier', 'import_date')
    search_fields = ('batch_code', 'product__name', 'supplier__name')
    list_filter = ('import_date', 'supplier')


@admin.register(InventoryTransaction)
class InventoryTransactionAdmin(admin.ModelAdmin):
    list_display = ('batch', 'transaction_type', 'quantity', 'date', 'created_by')
    search_fields = ('batch__batch_code', 'batch__product__name', 'created_by__username')
    list_filter = ('transaction_type', 'date')
