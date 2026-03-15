from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ProductionOrderViewSet, ProductionRunViewSet

router = DefaultRouter()
router.register(r'orders', ProductionOrderViewSet)
router.register(r'runs', ProductionRunViewSet) 

urlpatterns = [
    path('', include(router.urls)),
]