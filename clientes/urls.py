from django.urls import path

from . import views
from .medical_views import (
    AprobarSolicitudesAltaView,
    ImportarFichaMedicaView, RevisarFichaMedicaView, ResolverSolicitudAltaView, SolicitudesAltaView,
)

app_name = "clientes"

urlpatterns = [
    path("", views.ClienteListView.as_view(), name="list"),
    path("nueva/", views.ClienteCreateView.as_view(), name="create"),
    path("fichas-medicas/importar/", ImportarFichaMedicaView.as_view(), name="medical_import"),
    path("fichas-medicas/importaciones/<int:pk>/", RevisarFichaMedicaView.as_view(), name="medical_preview"),
    path("fichas-medicas/solicitudes/", SolicitudesAltaView.as_view(), name="medical_requests"),
    path("fichas-medicas/solicitudes/aprobar/", AprobarSolicitudesAltaView.as_view(), name="medical_requests_approve"),
    path("fichas-medicas/solicitudes/<int:pk>/", ResolverSolicitudAltaView.as_view(), name="medical_request_review"),
    path("<int:pk>/", views.ClienteDetailView.as_view(), name="detail"),
    path("<int:pk>/editar/", views.ClienteUpdateView.as_view(), name="update"),
    path("<int:pk>/estado/", views.ClienteSetStatusView.as_view(), name="set_status"),
]
