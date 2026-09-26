"""Root URL configuration for Aldra Pilates."""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("cuentas/", include("django.contrib.auth.urls")),
    path("clientes/", include("clientes.urls")),
    path("planes/", include("planes.urls")),
    path("mensualidades/", include("mensualidades.urls")),
    path("pagos/", include("pagos.urls")),
    path("", include("dashboard.urls")),
]
