from django.urls import path

from .views import NotificacionesListView

app_name = "notificaciones"

urlpatterns = [path("", NotificacionesListView.as_view(), name="index")]
