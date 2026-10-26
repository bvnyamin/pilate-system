import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import redirect
from django.utils import timezone
from django.views import View
from django.views.generic import ListView

from .services import correos_administracion, mensualidades_morosas
from .email_templates import enviar_correo_administracion

logger = logging.getLogger(__name__)


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


class ProbarCorreoView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Send a harmless email only to the configured administration addresses."""

    def test_func(self):
        return self.request.user.is_staff

    def post(self, request, *args, **kwargs):
        if settings.EMAIL_BACKEND == "django.core.mail.backends.console.EmailBackend":
            messages.warning(request, "El correo está configurado en modo consola y no se envía desde el sistema.")
            return redirect("notificaciones:index")

        recipients = correos_administracion()
        if not recipients:
            messages.error(request, "No hay destinatarios de administración configurados.")
            return redirect("notificaciones:index")

        try:
            sent = enviar_correo_administracion(
                subject="Aledra Pilates: prueba de correo",
                text_body=(
                    "Este es un correo de prueba del sistema Aledra Pilates.\n\n"
                    "Confirma que el envío desde Render llegó correctamente."
                ),
                recipient_list=recipients,
                notification_type="Prueba de envío",
                heading="El correo de Aledra está listo",
                intro="Este mensaje confirma que el sistema puede enviar notificaciones a la administración.",
                details=[{"label": "Estado", "value": "Correo de prueba generado correctamente"}],
                action_label="Abrir notificaciones",
                action_url=request.build_absolute_uri("/notificaciones/"),
                footer_note="Este mensaje es solo una prueba; no requiere ninguna acción.",
            )
        except Exception:
            logger.exception("Falló el envío de prueba de correo a administración.")
            messages.error(request, "No se pudo enviar el correo de prueba. Revisa el registro del servicio.")
            return redirect("notificaciones:index")

        if sent:
            messages.success(request, "Correo de prueba enviado a administración.")
        else:
            messages.error(request, "El servicio de correo no aceptó el mensaje de prueba.")
        return redirect("notificaciones:index")
