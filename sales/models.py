from django.db import models
from core.models import Partner, Product
from django.utils import timezone

class SaleOrder(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Chờ xử lý'),       # Mới tạo, chưa làm gì
        ('CONFIRMED', 'Đã chốt đơn'),   # Đã báo giá xong, chuẩn bị SX
        ('PRODUCTION', 'Đang sản xuất'),# Đang xẻ gỗ
        ('COMPLETED', 'Hoàn thành'),    # Đã giao hàng xong
        ('CANCELLED', 'Đã hủy'),
    ]

    code = models.CharField(max_length=20, unique=True, verbose_name="Mã đơn hàng") # VD: DH-2023-001
    customer = models.ForeignKey(Partner, on_delete=models.PROTECT, limit_choices_to={'partner_type': 'CUSTOMER'}, verbose_name="Khách hàng")
    order_date = models.DateTimeField(default=timezone.now, verbose_name="Ngày đặt")
    delivery_date = models.DateField(blank=True, null=True, verbose_name="Ngày giao dự kiến")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING', verbose_name="Trạng thái")
    note = models.TextField(blank=True, null=True, verbose_name="Ghi chú")
    
    created_at = models.DateTimeField(auto_now_add=True)
    is_deleted = models.BooleanField(default=False, verbose_name="Đã xóa")

    def __str__(self):
        return f"{self.code} - {self.customer.name}"

    @property
    def total_value(self):
        # Tính tổng tiền tự động từ các dòng chi tiết
        return sum(item.total_price for item in self.items.all())

class SaleOrderItem(models.Model):
    order = models.ForeignKey(SaleOrder, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.PROTECT, verbose_name="Sản phẩm")
    
    quantity = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Số lượng")
    price = models.DecimalField(max_digits=12, decimal_places=0, verbose_name="Đơn giá")
    
    def __str__(self):
        return f"{self.product.name} - {self.quantity}"

    @property
    def total_price(self):
        return self.quantity * self.price