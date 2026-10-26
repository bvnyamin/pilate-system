from django.urls import path

from .views import NotificacionesListView, ProbarCorreoView

app_name = "notificaciones"

urlpatterns = [
    path("", NotificacionesListView.as_view(), name="index"),
    path("correo-prueba/", ProbarCorreoView.as_view(), name="probar_correo"),
]
