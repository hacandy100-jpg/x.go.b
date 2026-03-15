from django.contrib import admin
from .models import SaleOrder, SaleOrderItem

# Cho phép nhập các dòng sản phẩm ngay trong trang chi tiết đơn hàng
class SaleOrderItemInline(admin.TabularInline):
    model = SaleOrderItem
    extra = 1 # Mặc định hiện sẵn 1 dòng trống để nhập

@admin.register(SaleOrder)
class SaleOrderAdmin(admin.ModelAdmin):
    list_display = ('code', 'customer', 'order_date', 'status', 'total_value_display')
    list_filter = ('status', 'order_date')
    search_fields = ('code', 'customer__name')
    inlines = [SaleOrderItemInline] # Gắn bảng con vào bảng cha

    # Hiển thị tổng tiền đẹp hơn
    def total_value_display(self, obj):
        return "{:,.0f} đ".format(obj.total_value)
    total_value_display.short_description = "Tổng trị giá"