from django.urls import path

from . import views

app_name = "reportes"

urlpatterns = [
    path("", views.ReporteView.as_view(), name="index"),
    path("gastos/", views.GastoListView.as_view(), name="gastos"),
    path("gastos/nuevo/", views.GastoCreateView.as_view(), name="gasto_create"),
    path("gastos/<int:pk>/editar/", views.GastoUpdateView.as_view(), name="gasto_update"),
]
