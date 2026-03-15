from multiprocessing.sharedctypes import Value
from rest_framework import viewsets, status

from django.contrib.auth import login  
from django.views.decorators.csrf import ensure_csrf_cookie 

from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.response import Response
from .models import Unit, Partner, Product
from .serializers import UnitSerializer, PartnerSerializer, ProductSerializer, LoginSerializer, UserSerializer
from django.db.models import Sum, Count, F, Q, DecimalField
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.db.models.functions import Coalesce
from sales.models import SaleOrder, SaleOrderItem
from django.db.models import Sum, F, ExpressionWrapper, Value, Case, When
from django.utils import timezone
from rest_framework.authtoken.models import Token
from inventory.models import Batch, InventoryTransaction



class UnitViewSet(viewsets.ModelViewSet):
    queryset = Unit.objects.all()
    serializer_class = UnitSerializer
    permission_classes = [AllowAny]
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ['code', 'name']
    ordering_fields = ['code', 'name']
    ordering = ['code']

class PartnerViewSet(viewsets.ModelViewSet):
    queryset = Partner.objects.all()
    serializer_class = PartnerSerializer
    permission_classes = [AllowAny]
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ['name', 'phone', 'address']
    ordering_fields = ['name', 'created_at']
    ordering = ['-created_at']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        partner_type = self.request.query_params.get('partner_type')
        if partner_type:
            queryset = queryset.filter(partner_type=partner_type)
        return queryset

    @action(detail=True, methods=['get'], url_path='history')
    def history(self, request, pk=None):
        """
        API: /api/partners/{id}/history/
        Trả về lịch sử đơn hàng của khách hàng và tổng tiền đã tiêu
        """
        partner = self.get_object()
        
        # Lấy tất cả đơn hàng của khách hàng này (chỉ lấy khách hàng)
        if partner.partner_type not in ['CUSTOMER', 'BOTH']:
            return Response({
                'error': 'Đối tác này không phải là khách hàng'
            }, status=400)
        
        # Lấy danh sách đơn hàng
        orders = SaleOrder.objects.filter(customer=partner).order_by('-order_date')
        
        # Tính tổng tiền đã tiêu (chỉ tính các đơn đã hoàn thành)
        completed_orders = orders.filter(status='COMPLETED')
        total_spent = sum(order.total_value for order in completed_orders)
        
        # Serialize đơn hàng
        orders_data = []
        for order in orders:
            orders_data.append({
                'id': order.id,
                'code': order.code,
                'order_date': order.order_date,
                'delivery_date': order.delivery_date,
                'status': order.status,
                'status_display': order.get_status_display(),
                'total_value': order.total_value,
                'note': order.note,
            })
        
        return Response({
            'partner': {
                'id': partner.id,
                'name': partner.name,
                'phone': partner.phone,
                'address': partner.address,
            },
            'total_orders': orders.count(),
            'completed_orders': completed_orders.count(),
            'total_spent': total_spent,
            'orders': orders_data
        })

class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [AllowAny]
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ['sku', 'name', 'description']
    ordering_fields = ['sku', 'name', 'product_type', 'price']
    ordering = ['sku']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        p_type = self.request.query_params.get('type') or self.request.query_params.get('product_type')
        if p_type:
            queryset = queryset.filter(product_type=p_type)
        return queryset


@api_view(['GET'])
@permission_classes([AllowAny])
def dashboard_stats(request):
    # 1. Tổng quan
    total_orders = SaleOrder.objects.count()
    completed_orders = SaleOrder.objects.filter(status='COMPLETED')

    # Tính revenue đúng cách: quantity * price (dùng ExpressionWrapper để nhân trong DB)
    total_revenue = SaleOrderItem.objects.filter(
        order__status='COMPLETED'
    ).aggregate(
        revenue=Sum(
            ExpressionWrapper(
                F('quantity') * F('price'),
                output_field=DecimalField(max_digits=20, decimal_places=0)
            )
        )
    )['revenue'] or 0

    # 3. Cảnh báo tồn kho thấp (tối ưu, đã fix cú pháp Case + Sum + Coalesce)
    low_stock_alerts = []

    batches = Batch.objects.select_related('product', 'product__unit').annotate(
        total_import=Coalesce(
            Sum(
                Case(
                    When(transactions__transaction_type='IMPORT', then=F('transactions__quantity')),
                    default=Value(0),
                    output_field=DecimalField(max_digits=12, decimal_places=2)
                )
            ),
            Value(0, output_field=DecimalField())
        ),
        total_export=Coalesce(
            Sum(
                Case(
                    When(transactions__transaction_type='EXPORT', then=F('transactions__quantity')),
                    default=Value(0),
                    output_field=DecimalField(max_digits=12, decimal_places=2)
                )
            ),
            Value(0, output_field=DecimalField())
        )
    ).annotate(
        stock=F('total_import') - F('total_export')
    ).filter(
        stock__gt=0,
        stock__lt=50
    )[:5]

    for b in batches:
        low_stock_alerts.append({
            'batch': b.batch_code,
            'product': b.product.name,
            'stock': float(b.stock),
            'unit': b.product.unit.name
        })

    return Response({
        'summary': {
            'total_orders': total_orders,
            'completed_orders': completed_orders.count(),
            'total_revenue': float(total_revenue),
        },
        'low_stock': low_stock_alerts
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    serializer = LoginSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.validated_data['user']
        
        # --- BƯỚC QUAN TRỌNG NHẤT: TẠO SESSION/COOKIE ---
        login(request, user) 
        # Lệnh này sẽ bảo Django gửi Header "Set-Cookie" về trình duyệt
        
        # Vẫn giữ Token nếu bạn muốn dùng song song
        token, created = Token.objects.get_or_create(user=user)
        
        return Response({
            'token': token.key,
            'user': UserSerializer(user).data,
            'detail': 'Login successful and Session created'
        }, status=status.HTTP_200_OK)
    
    return Response(
        {'detail': serializer.errors},
        status=status.HTTP_400_BAD_REQUEST
    )

@api_view(['GET'])
@permission_classes([AllowAny])
@ensure_csrf_cookie # Ép Django gửi cookie csrftoken về
def get_csrf_token(request):
    return Response({"detail": "CSRF cookie set"})


@api_view(['POST'])
@permission_classes([AllowAny])
def logout_view(request):
    """
    API: POST /api/auth/logout/
    Response: { "detail": "Logout successful" }
    """
    try:
        request.user.auth_token.delete()
    except AttributeError:
        pass
    
    return Response(
        {'detail': 'Logout successful'},
        status=status.HTTP_200_OK
    )

