from django.urls import path

from . import views

app_name = "asistencias"

urlpatterns = [
    path("", views.SesionListView.as_view(), name="list"),
    path("horarios-disponibles/", views.HorariosDisponiblesView.as_view(), name="available_times"),
    path("horarios/", views.HorarioEstudioUpdateView.as_view(), name="schedule_settings"),
    path("nueva/", views.SesionCreateView.as_view(), name="create"),
    path("<int:pk>/", views.SesionRosterView.as_view(), name="roster"),
    path("<int:pk>/eliminar/", views.SesionDeleteView.as_view(), name="delete"),
]
