from django.contrib import admin
from django.urls import path, include
from django.conf import settings
import django_cas_ng.views

urlpatterns = [
    path('admin/', admin.site.urls),

    # All /api/ requests go to spanish/urls.py
    path('api/', include('spanish.urls')),

    # ── CAS Authentication URLs ──────────────────────────────
    # These are only active when DEV_MODE = False
    path('accounts/login/',    django_cas_ng.views.LoginView.as_view(),    name='cas_login'),
    path('accounts/logout/',   django_cas_ng.views.LogoutView.as_view(),   name='cas_logout'),
    path('accounts/callback/', django_cas_ng.views.CallbackView.as_view(), name='cas_callback'),
]