from django.db import models

# 1. Đơn vị tính (m3, sit, bó, thanh...)
class Unit(models.Model):
    code = models.CharField(max_length=10, unique=True, verbose_name="Mã đơn vị") # VD: m3, kg
    name = models.CharField(max_length=50, verbose_name="Tên đơn vị") # VD: Mét khối
    
    def __str__(self):
        return f"{self.name} ({self.code})"

# 2. Đối tác (Dùng chung cho cả Khách hàng và Nhà cung cấp)
class Partner(models.Model):
    PARTNER_TYPES = [
        ('CUSTOMER', 'Khách hàng'),
        ('SUPPLIER', 'Nhà cung cấp'),
        ('BOTH', 'Vừa là Khách vừa là NCC'),
    ]
    
    name = models.CharField(max_length=200, verbose_name="Tên đối tác")
    partner_type = models.CharField(max_length=10, choices=PARTNER_TYPES, default='CUSTOMER', verbose_name="Loại đối tác")
    phone = models.CharField(max_length=20, blank=True, null=True, verbose_name="Số điện thoại")
    address = models.TextField(blank=True, null=True, verbose_name="Địa chỉ")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['partner_type']),
        ]

    def __str__(self):
        return f"{self.name} - {self.get_partner_type_display()}"

# 3. Sản phẩm
class Product(models.Model):
    PRODUCT_TYPES = [
        ('RAW', 'Nguyên liệu gỗ thô'),     # Gỗ tròn, gỗ khúc nhập về
        ('FINISHED', 'Thành phẩm'),        # Phôi, nan, ván sau khi xẻ
        ('BYPRODUCT', 'Phụ phẩm'),         # Mùn cưa, vỏ
    ]

    sku = models.CharField(max_length=50, unique=True, verbose_name="Mã sản phẩm/SKU")
    name = models.CharField(max_length=200, verbose_name="Tên sản phẩm")
    product_type = models.CharField(max_length=10, choices=PRODUCT_TYPES, verbose_name="Loại sản phẩm")
    
    min_stock_threshold = models.PositiveIntegerField(default=50, verbose_name="Ngưỡng tồn kho tối thiểu")
    updated_at = models.DateTimeField(auto_now=True)  # theo dõi cập nhật

    class Meta:
        indexes = [
            models.Index(fields=['sku']),
            models.Index(fields=['product_type']),
        ]
    # Link tới Unit
    unit = models.ForeignKey(Unit, on_delete=models.PROTECT, verbose_name="Đơn vị tính")
    
    description = models.TextField(blank=True, null=True, verbose_name="Mô tả kích thước/quy cách")
    
    # Giá tham khảo (có thể thay đổi theo từng đơn hàng/lô, nhưng cứ để giá gợi ý)
    price = models.DecimalField(max_digits=12, decimal_places=0, default=0, verbose_name="Giá tham khảo")

    def __str__(self):
        return f"[{self.sku}] {self.name}"