# production/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction
from django.utils import timezone
from django.db.models import F, Sum
from .models import ProductionRun, ProductionOutput, ProductionOrder
from inventory.models import Batch, InventoryTransaction
from core.models import Partner

# Cache Partner nội bộ (tạo 1 lần)
INTERNAL_SUPPLIER = None

def get_internal_supplier():
    global INTERNAL_SUPPLIER
    if INTERNAL_SUPPLIER is None:
        INTERNAL_SUPPLIER, _ = Partner.objects.get_or_create(
            name="Xưởng Sản Xuất",
            defaults={'partner_type': 'SUPPLIER'}
        )
    return INTERNAL_SUPPLIER

@receiver(post_save, sender=ProductionRun, dispatch_uid="handle_input_inventory_unique")
@transaction.atomic
def handle_input_inventory(sender, instance, created, **kwargs):
    if created:
        current_stock = instance.raw_batch.current_stock 
        if current_stock < instance.raw_qty_used:
            raise ValueError(f"Không đủ kho: lô {instance.raw_batch} chỉ còn {current_stock}")
        
        InventoryTransaction.objects.create(
            batch=instance.raw_batch,
            transaction_type='EXPORT',
            quantity=instance.raw_qty_used,
            note=f"Xuất xẻ gỗ cho lệnh {instance.production_order.code}",
            created_by=None  
        )

@receiver(post_save, sender=ProductionOutput, dispatch_uid="handle_output_inventory_unique")
@transaction.atomic
def handle_output_inventory(sender, instance, created, **kwargs):
    if created:
        try:
            internal_supplier = get_internal_supplier()
            
            # Tạo mã lô thành phẩm duy nhất
            new_batch_code = f"TP-{instance.run.production_order.code}-{instance.run.id}-{instance.product.id}"
            
            # Tạo Batch mới cho thành phẩm (không cần gán current_stock)
            new_batch = Batch.objects.create(
                batch_code=new_batch_code,
                product=instance.product,
                supplier=internal_supplier,
                import_date=timezone.now().date(),
                note=f"Thành phẩm từ mẻ xẻ ID {instance.run.id} - Lệnh {instance.run.production_order.code}"
            )

            qty = float(instance.quantity)  # đảm bảo số

            # Tạo transaction IMPORT → tồn kho sẽ tự động tăng khi tính từ transactions
            InventoryTransaction.objects.create(
                batch=new_batch,
                transaction_type='IMPORT',
                quantity=qty,
                note=f"Nhập kho thành phẩm từ lệnh {instance.run.production_order.code} - Mẻ {instance.run.id}"
            )
            
            print(f"[DEBUG] Thành công: Tạo batch thành phẩm {new_batch.batch_code} và nhập {qty} {instance.product.unit}")
        except Exception as e:
            print(f"[ERROR] Signal handle_output_inventory thất bại cho ProductionOutput {instance.id}: {str(e)}")
            raise  # Để thấy lỗi rõ trong console server

@receiver(post_save, sender=ProductionOrder, dispatch_uid="production_order_completed")
def handle_production_order_completed(sender, instance, created, **kwargs):
    """
    Khi một ProductionOrder được cập nhật (ví dụ status -> COMPLETED), tính tổng input/output,
    tính wastage và đặt cờ cảnh báo nếu >15%.
    """
    try:
        if instance.status == 'COMPLETED':
            total_input = instance.runs.aggregate(total=Sum('raw_qty_used'))['total'] or 0

            # Tổng output: sum quantity của outputs across runs
            total_output = ProductionOutput.objects.filter(run__production_order=instance).aggregate(total=Sum('quantity'))['total'] or 0

            wastage_percent = 0
            if float(total_input) > 0:
                wastage_percent = float((float(total_input) - float(total_output)) / float(total_input) * 100)

            instance.total_input = total_input
            instance.total_output = total_output
            instance.wastage_percent = round(wastage_percent, 2)
            instance.wastage_alert = wastage_percent > 15
            # Save without triggering recursive signal loop
            ProductionOrder.objects.filter(pk=instance.pk).update(
                total_input=instance.total_input,
                total_output=instance.total_output,
                wastage_percent=instance.wastage_percent,
                wastage_alert=instance.wastage_alert
            )
    except Exception as e:
        print('Error computing wastage for production order', instance.pk, e)