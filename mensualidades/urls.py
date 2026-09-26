from django.urls import path

from . import views

app_name = "mensualidades"

urlpatterns = [
    path("", views.ClientePlanListView.as_view(), name="list"),
    path("nueva/", views.ClientePlanCreateView.as_view(), name="create"),
    path("<int:pk>/editar/", views.ClientePlanUpdateView.as_view(), name="update"),
    path("<int:pk>/estado/", views.ClientePlanSetStatusView.as_view(), name="set_status"),
]
