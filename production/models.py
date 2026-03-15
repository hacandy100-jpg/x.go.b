from django.db import models
from django.utils import timezone
from sales.models import SaleOrder
from inventory.models import Batch
from core.models import Product

class ProductionOrder(models.Model):
    # (Giữ nguyên như cũ - không thay đổi)
    STATUS_CHOICES = [
        ('PLANNED', 'Đã lên kế hoạch'),
        ('IN_PROGRESS', 'Đang thực hiện'),
        ('COMPLETED', 'Đã hoàn thành'),
        ('CANCELLED', 'Hủy bỏ'),
    ]
    code = code = models.CharField(
        max_length=20, unique=True, blank=True, null=False, verbose_name="Mã lệnh SX" )
    sale_order = models.ForeignKey(SaleOrder, on_delete=models.PROTECT, verbose_name="Sản xuất cho Đơn hàng")
    start_date = models.DateField(default=timezone.now, verbose_name="Ngày bắt đầu")
    end_date = models.DateField(blank=True, null=True, verbose_name="Ngày kết thúc")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PLANNED', verbose_name="Trạng thái")
    note = models.TextField(blank=True, null=True, verbose_name="Ghi chú SX")
    created_at = models.DateTimeField(auto_now_add=True)
    # Aggregates and warnings
    total_input = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_output = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    wastage_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    wastage_alert = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.code} (Cho đơn: {self.sale_order.code})"

class ProductionRun(models.Model):
    """
    Bảng Cha: Quản lý ĐẦU VÀO (Input)
    Mỗi lần chạy máy xẻ là 1 ProductionRun
    """
    production_order = models.ForeignKey(ProductionOrder, on_delete=models.CASCADE, related_name='runs', verbose_name="Thuộc lệnh SX")
    date = models.DateTimeField(default=timezone.now, verbose_name="Thời gian thực hiện")
    
    # INPUT: Trừ kho nguyên liệu ở đây
    raw_batch = models.ForeignKey(Batch, on_delete=models.PROTECT, related_name='used_in_runs', verbose_name="Lô gỗ nguyên liệu (Input)")
    raw_qty_used = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Số lượng gỗ tiêu thụ")
    
    note = models.TextField(blank=True, null=True, verbose_name="Ghi chú")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Xẻ {self.raw_qty_used} {self.raw_batch.product.unit.code} từ lô {self.raw_batch.batch_code}"

class ProductionOutput(models.Model):
    """
    Bảng Con: Quản lý ĐẦU RA (Output)
    Một lần xẻ ra nhiều loại thành phẩm
    """
    run = models.ForeignKey(ProductionRun, on_delete=models.CASCADE, related_name='outputs')
    product = models.ForeignKey(Product, on_delete=models.PROTECT, verbose_name="Thành phẩm/Phụ phẩm")
    quantity = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Số lượng thu được")

    def __str__(self):
        return f"Ra: {self.quantity} {self.product.name}"