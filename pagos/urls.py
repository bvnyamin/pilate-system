from django.urls import path

from . import views

app_name = "pagos"

urlpatterns = [
    path("", views.PagoListView.as_view(), name="list"),
    path("nuevo/", views.PagoCreateView.as_view(), name="create"),
    path("<int:pk>/editar/", views.PagoUpdateView.as_view(), name="update"),
    path("<int:pk>/estado/", views.PagoSetStatusView.as_view(), name="set_status"),
]
