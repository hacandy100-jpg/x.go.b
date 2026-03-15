from rest_framework import serializers
from django.db import transaction
from django.db.models import Sum
from .models import ProductionOrder, ProductionRun, ProductionOutput

class ProductionOutputSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    unit_name = serializers.CharField(source='product.unit.name', read_only=True)

    class Meta:
        model = ProductionOutput
        fields = ['id', 'product', 'product_name', 'unit_name', 'quantity']

class ProductionRunSerializer(serializers.ModelSerializer):
    raw_batch_code = serializers.CharField(source='raw_batch.batch_code', read_only=True)
    product_name = serializers.CharField(source='raw_batch.product.name', read_only=True)
    # Lồng danh sách đầu ra vào trong đầu vào
    outputs = ProductionOutputSerializer(many=True)
    # Thêm trường tính tỷ lệ hao hụt
    wastage_rate = serializers.SerializerMethodField()
    efficiency_rate = serializers.SerializerMethodField()

    class Meta:
        model = ProductionRun
        fields = ['id', 'production_order', 'date', 'raw_batch', 'raw_batch_code', 'product_name', 'raw_qty_used', 'note', 'outputs', 'wastage_rate', 'efficiency_rate']

    def get_efficiency_rate(self, obj):
        """
        Tính hiệu suất: (Tổng Output / Input) * 100%
        """
        if not obj.raw_qty_used or obj.raw_qty_used <= 0:
            return None
        
        # Tính tổng số lượng đầu ra
        total_output = sum(output.quantity for output in obj.outputs.all())
        
        if total_output <= 0:
            return 0.0
        
        # Tính hiệu suất (%)
        efficiency = (float(total_output) / float(obj.raw_qty_used)) * 100
        return round(efficiency, 2)

    def get_wastage_rate(self, obj):
        """
        Tính tỷ lệ hao hụt: ((Input - Output) / Input) * 100%
        """
        if not obj.raw_qty_used or obj.raw_qty_used <= 0:
            return None
        
        # Tính tổng số lượng đầu ra
        total_output = sum(output.quantity for output in obj.outputs.all())
        
        # Tính hao hụt (%)
        wastage = ((float(obj.raw_qty_used) - float(total_output)) / float(obj.raw_qty_used)) * 100
        return round(wastage, 2)

    # Logic lưu đa cấp (Cha + Con cùng lúc)
    def create(self, validated_data):
        outputs_data = validated_data.pop('outputs')
        try:
            with transaction.atomic(): # <--- Bọc tất cả vào khối an toàn này
                # 1. Tạo ProductionRun (Sẽ trừ kho tạm thời)
                run = ProductionRun.objects.create(**validated_data)
                
                # 2. Tạo các Output (Sẽ cộng kho thành phẩm)
                for output_data in outputs_data:
                    ProductionOutput.objects.create(run=run, **output_data)
                
                # Nếu chạy đến đây mà không lỗi thì Database mới chính thức lưu
                return run
                
        except Exception as e:
            # Nếu có bất kỳ lỗi gì trong khối transaction.atomic()
            # Django sẽ tự động ROLLBACK (Hoàn tác) lại việc trừ kho ở bước 1
            raise e
        
    def validate(self, data):
        raw_batch = data.get('raw_batch')
        raw_qty_used = data.get('raw_qty_used')
        
        if raw_batch and raw_qty_used:
            # Tính stock hiện tại (dùng annotate hoặc property)
            total_import = raw_batch.transactions.filter(transaction_type='IMPORT').aggregate(Sum('quantity'))['quantity__sum'] or 0
            total_export = raw_batch.transactions.filter(transaction_type='EXPORT').aggregate(Sum('quantity'))['quantity__sum'] or 0
            current_stock = total_import - total_export
            
            if raw_qty_used > current_stock:
                raise serializers.ValidationError(
                    f"Không đủ kho nguyên liệu: lô {raw_batch.batch_code} chỉ còn {current_stock}"
                )
        return data

class ProductionOrderSerializer(serializers.ModelSerializer):
    sale_order_code = serializers.CharField(source='sale_order.code', read_only=True)
    runs = ProductionRunSerializer(many=True, read_only=True)

    class Meta:
        model = ProductionOrder
        fields = '__all__'