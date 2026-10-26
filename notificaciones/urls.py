from django.urls import path

from .views import MarcarNotificacionLeidaView, NotificacionesListView, ProbarCorreoView

app_name = "notificaciones"

urlpatterns = [
    path("", NotificacionesListView.as_view(), name="index"),
    path("correo-prueba/", ProbarCorreoView.as_view(), name="probar_correo"),
    path("marcar-leida/", MarcarNotificacionLeidaView.as_view(), name="marcar_leida"),
]
