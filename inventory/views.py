from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db.models import Sum, Case, When, F, DecimalField, Value

from .models import Batch, InventoryTransaction
from django.db import transaction
from .serializers import BatchSerializer, InventoryTransactionSerializer

class BatchViewSet(viewsets.ModelViewSet):
    queryset = Batch.objects.all().order_by('-import_date')
    serializer_class = BatchSerializer
    permission_classes = [AllowAny]
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ['batch_code', 'product__name', 'supplier__name', 'note']
    ordering_fields = ['import_date', 'batch_code']
    ordering = ['-import_date']
    
   
    @action(detail=False, methods=['get'])
    def stock_report(self, request):
        # Import Coalesce để xử lý trường hợp Sum ra None (null)
        from django.db.models.functions import Coalesce 
        
        queryset = Batch.objects.select_related('product', 'product__unit', 'supplier')

        p_type = request.query_params.get('product_type')
        if p_type:
            queryset = queryset.filter(product__product_type=p_type)

        batches = queryset.annotate(
            total_import=Coalesce(Sum(
                Case(When(transactions__transaction_type='IMPORT', then='transactions__quantity'), default=0, output_field=DecimalField())
            ), Value(0, output_field=DecimalField())),
            
            total_export=Coalesce(Sum(
                Case(When(transactions__transaction_type='EXPORT', then='transactions__quantity'), default=0, output_field=DecimalField())
            ), Value(0, output_field=DecimalField())),
            
            db_current_stock=F('total_import') - F('total_export')
        ).filter(db_current_stock__gt=0).order_by('import_date')  

        # Pagination
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 50))
        start = (page - 1) * page_size
        end = start + page_size

        paginated = batches[start:end]

        data = [
            {
                'id': b.id,
                'batch_code': b.batch_code,
                'product_name': b.product.name,
                'unit_name': b.product.unit.name,
                'supplier_name': b.supplier.name,               
                'current_stock': float(b.db_current_stock), 
                'import_date': b.import_date,
                'product_type': b.product.product_type
            }
            for b in paginated
        ]

        return Response({
            'results': data,
            'total': batches.count(),
            'page': page,
            'page_size': page_size
        })

class TransactionViewSet(viewsets.ModelViewSet):
    queryset = InventoryTransaction.objects.all().order_by('-date')
    serializer_class = InventoryTransactionSerializer
    permission_classes = [AllowAny]
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ['batch__batch_code', 'note', 'created_by__username']
    ordering_fields = ['date', 'quantity', 'transaction_type']
    ordering = ['-date']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        transaction_type = self.request.query_params.get('transaction_type')
        batch_id = self.request.query_params.get('batch')
        
        if transaction_type:
            queryset = queryset.filter(transaction_type=transaction_type)
        if batch_id:
            queryset = queryset.filter(batch_id=batch_id)
            
        return queryset
    
    def perform_create(self, serializer):
        # Only attach created_by when there is an authenticated user.
        user = getattr(self.request, 'user', None)
        with transaction.atomic():
            if user and getattr(user, 'is_authenticated', False):
                serializer.save(created_by=user)
            else:
                serializer.save()