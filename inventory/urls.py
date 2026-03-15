from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import BatchViewSet, TransactionViewSet

router = DefaultRouter()
router.register(r'batches', BatchViewSet)
router.register(r'transactions', TransactionViewSet)

urlpatterns = [
    path('', include(router.urls)),
]