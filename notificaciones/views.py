from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.utils import timezone
from django.views.generic import ListView

from .services import mensualidades_morosas


class NotificacionesListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    template_name = "notificaciones/index.html"
    context_object_name = "mensualidades_morosas"

    def test_func(self):
        return self.request.user.is_staff

    def get_queryset(self):
        return mensualidades_morosas()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "page_title": "Notificaciones",
                "fecha_hoy": timezone.localdate(),
                "avisos_activos": context["mensualidades_morosas"].count(),
            }
        )
        return context
