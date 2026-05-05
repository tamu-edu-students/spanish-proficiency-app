from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),

    # All /api/ requests go to spanish/urls.py
    path('api/', include('spanish.urls')),
]