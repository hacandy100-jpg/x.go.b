from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db import transaction
from django.utils import timezone

from django.db.models import Sum, Case, When, Value, DecimalField, Q
from django.db.models.functions import Coalesce
from rest_framework.exceptions import ValidationError
from inventory.models import Batch, InventoryTransaction
from .models import SaleOrder

from .serializers import SaleOrderSerializer


class SaleOrderViewSet(viewsets.ModelViewSet):
    queryset = SaleOrder.objects.all().order_by('-order_date')
    serializer_class = SaleOrderSerializer
    permission_classes = [AllowAny]
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ['code', 'customer__name', 'note']
    ordering_fields = ['order_date', 'delivery_date', 'status']  # Bỏ total_value vì là property
    ordering = ['-order_date']

    def get_queryset(self):
        queryset = super().get_queryset().filter(is_deleted=False)

        status_filter = self.request.query_params.get('status')
        customer_id = self.request.query_params.get('customer')

        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if customer_id:
            queryset = queryset.filter(customer_id=customer_id)

        # Tối ưu N+1 queries: prefetch items + product + unit
        if self.action in ['list', 'retrieve']:
            queryset = queryset.prefetch_related(
                'items__product__unit'
            )

        return queryset

    def destroy(self, request, *args, **kwargs):
        """Soft-delete thay vì xóa thật"""
        instance = self.get_object()
        instance.is_deleted = True
        instance.save(update_fields=['is_deleted'])
        return Response(status=status.HTTP_204_NO_CONTENT)

    def perform_create(self, serializer):
        """Tự động sinh code nếu không có"""
        if 'code' not in self.request.data or not self.request.data['code']:
            next_id = SaleOrder.objects.count() + 1
            generated_code = f"DH-{next_id:04d}"
            serializer.save(code=generated_code)
        else:
            serializer.save()

    # @action(detail=True, methods=['post'])
    # def confirm_delivery(self, request, pk=None):
    #     """
    #     API: /api/sales/orders/{id}/confirm_delivery/
    #     - Trừ kho thành phẩm theo FIFO
    #     - Cập nhật trạng thái COMPLETED
    #     - An toàn với transaction + lock row để tránh race condition
    #     """
    #     order = self.get_object()

    #     if order.status == 'COMPLETED':
    #         return Response({'error': 'Đơn hàng đã giao rồi!'}, status=status.HTTP_400_BAD_REQUEST)

    #     try:
    #         with transaction.atomic():
    #             # Lock các batch tiềm năng của sản phẩm trong đơn để tránh race condition
    #             product_ids = order.items.values_list('product_id', flat=True)
    #             Batch.objects.filter(product__in=product_ids).select_for_update()

    #             for item in order.items.all():
    #                 qty_needed = item.quantity
    #                 product = item.product

    #                 # Lấy danh sách lô FIFO có sẵn (đã lock)
    #                 available_batches = Batch.objects.available_for_export(product.id, qty_needed)

    #                 qty_fulfilled = 0
    #                 for batch in available_batches:
    #                     current_stock = batch.current_stock  # Giả định property đã có ở Batch
    #                     if current_stock <= 0:
    #                         continue

    #                     qty_to_take = min(current_stock, qty_needed - qty_fulfilled)

    #                     InventoryTransaction.objects.create(
    #                         batch=batch,
    #                         transaction_type='EXPORT',
    #                         quantity=qty_to_take,
    #                         note=f"Giao hàng cho đơn {order.code}",
    #                         created_by=request.user
    #                     )

    #                     qty_fulfilled += qty_to_take

    #                     if qty_fulfilled >= qty_needed:
    #                         break

    #                 if qty_fulfilled < qty_needed:
    #                     raise Exception(
    #                         f"Không đủ tồn kho cho sản phẩm {product.name}. "
    #                         f"Thiếu {qty_needed - qty_fulfilled} {product.unit.name}"
    #                     )

    #             # Cập nhật đơn hàng
    #             order.status = 'COMPLETED'
    #             order.delivery_date = request.data.get('date') or timezone.now().date()
    #             order.save(update_fields=['status', 'delivery_date'])

    #         return Response({'status': 'Giao hàng thành công! Đã trừ kho.'})

        # except Exception as e:
        #     return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)



    @action(detail=True, methods=['post'])
    @transaction.atomic
    
    def confirm_delivery(self, request, pk=None):
        order = self.get_object()
        
        for item in order.items.all():
            product = item.product
            needed_qty = item.quantity
            remaining_qty = needed_qty
            
            # Lấy tất cả batch của sản phẩm, sắp xếp FIFO: cũ nhất trước
            batches = Batch.objects.filter(product=product).order_by('import_date')
            
            for batch in batches:
                if remaining_qty <= 0:
                    break
                
                # Tính tồn kho hiện tại của batch từ transactions
                import_total = batch.transactions.filter(transaction_type='IMPORT').aggregate(
                    total=Coalesce(Sum('quantity'), Value(0), output_field=DecimalField())
                )['total']
                
                export_total = batch.transactions.filter(transaction_type='EXPORT').aggregate(
                    total=Coalesce(Sum('quantity'), Value(0), output_field=DecimalField())
                )['total']
                
                batch_stock = import_total - export_total
                
                if batch_stock <= 0:
                    continue  # lô này hết stock → bỏ qua
                
                # Xuất bao nhiêu từ lô này
                qty_to_export = min(remaining_qty, batch_stock)
                
                # Tạo transaction EXPORT
                InventoryTransaction.objects.create(
                    batch=batch,
                    transaction_type='EXPORT',
                    quantity=qty_to_export,
                    note=f"Xuất giao đơn hàng {order.code} - Sản phẩm {product.name}",
                    created_by=request.user
                )
                
                remaining_qty -= qty_to_export
            
            # Sau khi duyệt hết lô, kiểm tra còn thiếu không
            if remaining_qty > 0:
                raise ValidationError({
                    "error": f"Không đủ tồn kho cho sản phẩm {product.name}. "
                            f"Thiếu {remaining_qty} {product.unit.name}"
                })
        
        # Nếu tất cả sản phẩm đều đủ → cập nhật trạng thái đơn hàng
        order.status = 'DELIVERED'  # hoặc 'SHIPPED', 'COMPLETED' tùy bạn
        order.save()
        
        return Response({"detail": "Giao hàng thành công!"})



    @action(detail=True, methods=['patch'])
    def update_status(self, request, pk=None):
        """
        API: /api/sales/orders/{id}/update_status/
        Cập nhật trạng thái đơn hàng
        """
        order = self.get_object()
        new_status = request.data.get('status')

        if not new_status:
            return Response({'error': 'Thiếu trường status'}, status=status.HTTP_400_BAD_REQUEST)

        valid_statuses = dict(SaleOrder.STATUS_CHOICES).keys()
        if new_status not in valid_statuses:
            return Response({'error': 'Trạng thái không hợp lệ'}, status=status.HTTP_400_BAD_REQUEST)

        # Tùy chọn: Nếu update lên COMPLETED thì nên gọi confirm_delivery
        if new_status == 'COMPLETED' and order.status != 'COMPLETED':
            return Response(
                {'error': 'Vui lòng dùng API confirm_delivery để hoàn tất giao hàng'},
                status=status.HTTP_400_BAD_REQUEST
            )

        order.status = new_status
        order.save(update_fields=['status'])

        return Response({
            'status': 'Cập nhật trạng thái thành công',
            'order': SaleOrderSerializer(order).data
        })