from django.urls import path, include
from .views import get_csrf_token
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'units', views.UnitViewSet)
router.register(r'partners', views.PartnerViewSet)
router.register(r'products', views.ProductViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('get_csrf_token/', get_csrf_token, name='get_csrf_token'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard-stats/', views.dashboard_stats, name='dashboard-stats'),
]