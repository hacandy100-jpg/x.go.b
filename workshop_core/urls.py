from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse

def root(request):
    return JsonResponse({"status": "API is running"})

urlpatterns = [
    path('', root),
    path('admin/', admin.site.urls),
    path('api/', include('core.urls')),
    path('api/inventory/', include('inventory.urls')),
    path('api/sales/', include('sales.urls')),
    path('api/production/', include('production.urls')),

]