from rest_framework import serializers
from .models import Batch, InventoryTransaction

class BatchSerializer(serializers.ModelSerializer):
    # Hiển thị tên thay vì ID cho dễ nhìn
    product_name = serializers.CharField(source='product.name', read_only=True)
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    unit_name = serializers.CharField(source='product.unit.name', read_only=True)

    class Meta:
        model = Batch
        fields = '__all__'

class InventoryTransactionSerializer(serializers.ModelSerializer):
    batch_code = serializers.CharField(source='batch.batch_code', read_only=True)
    product_name = serializers.CharField(source='batch.product.name', read_only=True)

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("Số lượng phải lớn hơn 0")
        return value
    
    class Meta:
        model = InventoryTransaction
        fields = '__all__'