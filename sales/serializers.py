from rest_framework import serializers
from django.db.models import Sum
from .models import SaleOrder, SaleOrderItem
from inventory.models import Batch
from core.models import Product
from django.db import transaction   


class SaleOrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    unit_name = serializers.CharField(source='product.unit.name', read_only=True)

    class Meta:
        model = SaleOrderItem
        fields = [
            'id', 'product', 'product_name', 'unit_name',
            'quantity', 'price', 'total_price'
        ]

    def validate(self, data):
        """Validation cơ bản cho từng dòng item"""
        quantity = data.get('quantity')
        product = data.get('product')

        if quantity is None or quantity <= 0:
            raise serializers.ValidationError("Số lượng phải lớn hơn 0")

        if product.product_type == 'RAW':
            raise serializers.ValidationError("Không thể bán nguyên liệu thô (RAW)")

        return data


class SaleOrderSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    items = SaleOrderItemSerializer(many=True)

    class Meta:
        model = SaleOrder
        fields = [
            'id', 'code', 'customer', 'customer_name',
            'order_date', 'delivery_date', 'status', 'note',
            'total_value', 'items'
        ]
        read_only_fields = ['code', 'total_value']

    def create(self, validated_data):
        """Tạo đơn hàng + các dòng item (cha-con)"""
        items_data = validated_data.pop('items')

        with transaction.atomic():  # An toàn hơn khi tạo nhiều dòng
            order = SaleOrder.objects.create(**validated_data)

            for item_data in items_data:
                SaleOrderItem.objects.create(order=order, **item_data)

        return order

    def to_representation(self, instance):
        """Tối ưu: Tính current_stock một lần cho toàn bộ sản phẩm trong đơn"""
        ret = super().to_representation(instance)

        if instance.items.exists():
            # Lấy tất cả product trong đơn
            products = [item.product for item in instance.items.all()]

            # Tính stock tổng cho từng product (sử dụng property current_stock nếu có)
            stock_dict = {}
            batches = Batch.objects.filter(product__in=products).prefetch_related('transactions')

            for batch in batches:
                stock = batch.current_stock  # Giả định property current_stock đã có ở Batch
                stock_dict.setdefault(batch.product_id, 0)
                stock_dict[batch.product_id] += stock

            # Gán stock vào từng item trong response
            for item_data in ret['items']:
                product_id = item_data['product']
                item_data['current_stock'] = stock_dict.get(product_id, 0.0)

        return ret

    def validate(self, data):
        """Validation tổng thể cho đơn hàng (tùy chọn nâng cao)"""
        items_data = data.get('items', [])

        if not items_data:
            raise serializers.ValidationError("Đơn hàng phải có ít nhất 1 sản phẩm")

        # Kiểm tra tổng quantity > 0 (tùy chọn)
        total_qty = sum(item['quantity'] for item in items_data)
        if total_qty <= 0:
            raise serializers.ValidationError("Tổng số lượng phải lớn hơn 0")

        return data