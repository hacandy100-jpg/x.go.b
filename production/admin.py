from django.contrib import admin
from .models import ProductionOrder, ProductionRun, ProductionOutput

class ProductionOutputInline(admin.TabularInline):
    model = ProductionOutput
    extra = 1

@admin.register(ProductionRun)
class ProductionRunAdmin(admin.ModelAdmin):
    list_display = ('production_order', 'date', 'raw_batch', 'raw_qty_used')
    inlines = [ProductionOutputInline] # Cho phép nhập Output ngay trong trang nhập Input

@admin.register(ProductionOrder)
class ProductionOrderAdmin(admin.ModelAdmin):
    list_display = ('code', 'sale_order', 'start_date', 'status')