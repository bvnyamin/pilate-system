"""Root URL configuration for Aledra Pilates."""

from django.contrib import admin
from django.urls import include, path

from clientes.google_forms_webhook import recibir_respuesta_ficha_medica

urlpatterns = [
    path("admin/", admin.site.urls),
    path("cuentas/", include("django.contrib.auth.urls")),
    path("accounts/", include("allauth.urls")),
    path("clientes/", include("clientes.urls")),
    path("integraciones/google-forms/ficha-medica/", recibir_respuesta_ficha_medica, name="google_forms_medical_webhook"),
    path("planes/", include("planes.urls")),
    path("mensualidades/", include("mensualidades.urls")),
    path("pagos/", include("pagos.urls")),
    path("asistencias/", include("asistencias.urls")),
    path("reportes/", include("reportes.urls")),
    path("notificaciones/", include("notificaciones.urls")),
    path("", include("dashboard.urls")),
]
