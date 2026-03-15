from rest_framework import viewsets, status
from rest_framework.permissions import AllowAny
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.decorators import action
from rest_framework.response import Response
from datetime import datetime
from django.db.models import Prefetch
from .models import ProductionOrder, ProductionRun
from .serializers import ProductionOrderSerializer, ProductionRunSerializer
from inventory.models import Batch  

class ProductionOrderViewSet(viewsets.ModelViewSet):
    queryset = ProductionOrder.objects.all().order_by('-created_at')
    serializer_class = ProductionOrderSerializer
    permission_classes = [AllowAny]
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ['code', 'sale_order__code', 'note']
    ordering_fields = ['created_at', 'status', 'start_date']
    ordering = ['-created_at']

    def get_queryset(self):
        queryset = super().get_queryset()
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        # Tối ưu query: prefetch runs + outputs để giảm N+1
        if self.action in ['list', 'retrieve']:
            queryset = queryset.prefetch_related(
                Prefetch('runs', queryset=ProductionRun.objects.select_related('raw_batch', 'raw_batch__product')),
                'runs__outputs__product'
            )
        return queryset

    def perform_create(self, serializer):
        # Tự sinh code nếu không có hoặc để trống
        if 'code' not in self.request.data or not self.request.data.get('code'):
            now = datetime.now()
            generated_code = f"LSX-{now.strftime('%Y%m%d%H%M%S')}"
            serializer.save(code=generated_code)
        else:
            serializer.save()

    def destroy(self, request, *args, **kwargs):
        """
        Override destroy để thêm kiểm tra trước khi xóa
        - Không cho xóa nếu lệnh đã COMPLETED
        - Không cho xóa nếu đã có mẻ sản xuất (runs) để tránh mất dữ liệu lịch sử
        """
        order = self.get_object()

        if order.status == 'COMPLETED':
            return Response(
                {"detail": "Không thể xóa lệnh sản xuất đã hoàn thành"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if order.runs.exists():
            return Response(
                {"detail": "Không thể xóa lệnh vì đã có mẻ sản xuất. Hãy hủy lệnh hoặc xóa mẻ trước."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Nếu qua được kiểm tra → xóa bình thường
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=['post'], url_path='complete')
    def complete(self, request, pk=None):
        order = self.get_object()
        if order.status == 'COMPLETED':
            return Response({"detail": "Lệnh đã hoàn thành"}, status=status.HTTP_400_BAD_REQUEST)

        if not order.runs.exists():
            return Response({"detail": "Chưa có mẻ sản xuất nào"}, status=status.HTTP_400_BAD_REQUEST)

        order.status = 'COMPLETED'
        order.end_date = timezone.now().date()
        order.save(update_fields=['status', 'end_date'])
        return Response({"detail": "Lệnh SX đã hoàn thành", "status": order.status})

    # (Tùy chọn) Nếu bạn muốn action riêng để hủy lệnh thay vì xóa
    @action(detail=True, methods=['post'], url_path='cancel')
    def cancel(self, request, pk=None):
        order = self.get_object()
        if order.status == 'COMPLETED':
            return Response({"detail": "Không thể hủy lệnh đã hoàn thành"}, status=400)
        
        order.status = 'CANCELLED'
        order.save(update_fields=['status'])
        return Response({"detail": "Lệnh đã được hủy", "status": order.status})
class ProductionRunViewSet(viewsets.ModelViewSet):
    queryset = ProductionRun.objects.all().order_by('-date')
    serializer_class = ProductionRunSerializer
    permission_classes = [AllowAny]
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ['production_order__code', 'raw_batch__batch_code', 'note']
    ordering_fields = ['date', 'raw_qty_used']
    ordering = ['-date']

    def get_queryset(self):
        queryset = super().get_queryset()
        order_id = self.request.query_params.get('production_order')
        if order_id:
            queryset = queryset.filter(production_order_id=order_id)
        return queryset

    @action(detail=False, methods=['get'], url_path='suggest-input')
    def suggest_input(self, request):
        product_id = request.query_params.get('product_id')
        if not product_id:
            return Response({"error": "Cần product_id"}, status=400)

        available = Batch.objects.available_for_export(product_id, needed_qty=0)  
        suggestions = [
            {
                "batch_id": b.id,
                "batch_code": b.batch_code,
                "current_stock": float(b.current_stock),  
                "import_date": b.import_date,
                "supplier": b.supplier.name
            }
            for b in available[:10]  # Top 10 lô cũ nhất
        ]
        return Response({"suggestions": suggestions})