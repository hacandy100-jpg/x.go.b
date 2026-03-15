from django.db import models
from django.utils import timezone
from core.models import Product, Partner
from django.db.models import Q, Sum

class BatchManager(models.Manager):
    def available_for_export(self, product_id, needed_qty):
        """Trả về các lô theo FIFO có đủ hàng để xuất"""
        return self.get_queryset().filter(
            product_id=product_id,
            transactions__transaction_type='IMPORT'
        ).annotate(
            current_stock=Sum('transactions__quantity', filter=Q(transactions__transaction_type='IMPORT')) -
                         Sum('transactions__quantity', filter=Q(transactions__transaction_type='EXPORT'))
        ).filter(current_stock__gt=0).order_by('import_date')


class Batch(models.Model):
    """
    Quản lý Lô hàng.
    Mỗi lần nhập gỗ từ NCC về, ta tạo 1 Lô mới.
    """
    batch_code = models.CharField(max_length=50, unique=True, verbose_name="Mã lô") # VD: LO-20231025-01
    product = models.ForeignKey(Product, on_delete=models.PROTECT, verbose_name="Sản phẩm/Gỗ")
    supplier = models.ForeignKey(Partner, on_delete=models.PROTECT, verbose_name="Nhà cung cấp")

    import_date = models.DateTimeField(default=timezone.now, verbose_name="Ngày nhập")
    note = models.TextField(blank=True, null=True, verbose_name="Ghi chú")
    
    created_at = models.DateTimeField(auto_now_add=True)
    objects = BatchManager()

    @property
    def current_stock(self):
        total_import = self.transactions.filter(transaction_type='IMPORT').aggregate(Sum('quantity'))['quantity__sum'] or 0
        total_export = self.transactions.filter(transaction_type='EXPORT').aggregate(Sum('quantity'))['quantity__sum'] or 0
        return total_import - total_export

    class Meta:
        indexes = [
            models.Index(fields=['batch_code']),
            models.Index(fields=['import_date']),
            models.Index(fields=['product']),
            models.Index(fields=['supplier']),
        ]

    def __str__(self):
        return f"{self.batch_code} - {self.product.name}"

class InventoryTransaction(models.Model):
    """
    Lưu vết mọi biến động kho (Nhập vào / Xuất ra).
    Tồn kho = Tổng Nhập - Tổng Xuất.
    """
    TRANSACTION_TYPES = [
        ('IMPORT', 'Nhập kho'),
        ('EXPORT', 'Xuất kho'),
        ('ADJUST', 'Kiểm kê/Điều chỉnh'), # Dùng khi bị mất mát, hư hỏng
    ]

    batch = models.ForeignKey(Batch, on_delete=models.CASCADE, related_name='transactions', verbose_name="Lô hàng")
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPES, verbose_name="Loại giao dịch")
    
    quantity = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Số lượng")
    # Lưu ý: Import thì số dương, Export ta cũng lưu số dương (logic trừ sẽ xử lý ở code)
    
    date = models.DateTimeField(default=timezone.now, verbose_name="Thời gian giao dịch")
    note = models.TextField(blank=True, null=True, verbose_name="Diễn giải")
    
    created_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Người thực hiện")
    class Meta:
        indexes = [
            models.Index(fields=['batch', 'transaction_type']),
            models.Index(fields=['date']),
        ]

    def __str__(self):
        return f"{self.transaction_type} - {self.batch.batch_code} - {self.quantity}"
    

