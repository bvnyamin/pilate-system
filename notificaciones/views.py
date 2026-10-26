import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import redirect
from django.urls import reverse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views import View
from django.views.generic import ListView

from clientes.models import SolicitudAltaCliente
from mensualidades.models import ClientePlan

from .models import NotificacionLeida
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


class MarcarNotificacionLeidaView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Mark a current staff notification as read, then open its related record."""

    def test_func(self):
        return self.request.user.is_staff

    def post(self, request, *args, **kwargs):
        tipo = request.POST.get("tipo")
        if tipo == "solicitud":
            solicitud = get_object_or_404(
                SolicitudAltaCliente,
                pk=request.POST.get("id"),
                estado=SolicitudAltaCliente.Estado.PENDIENTE,
            )
            clave = f"solicitud:{solicitud.pk}"
            destino = reverse("clientes:medical_request_review", args=[solicitud.pk])
        elif tipo == "mensualidad":
            plan = get_object_or_404(
                mensualidades_morosas(),
                pk=request.POST.get("id"),
            )
            clave = f"mensualidad:{plan.pk}:{plan.periodo_anio}-{plan.periodo_mes:02d}"
            destino = reverse("clientes:detail", args=[plan.cliente_id])
        else:
            return redirect("notificaciones:index")

        NotificacionLeida.objects.get_or_create(usuario=request.user, clave=clave)
        return redirect(destino)


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

        tipo = request.POST.get("tipo", "prueba")
        if tipo == "solicitud":
            email = {
                "subject": "EJEMPLO · Aledra Pilates: nueva solicitud de perfil",
                "text_body": (
                    "Muestra ficticia de la notificación que llega al recibir una solicitud desde el formulario.\n\n"
                    "Nombre informado: Camila Ejemplo\n\n"
                    "No incluye respuestas ni antecedentes médicos."
                ),
                "notification_type": "EJEMPLO · solicitud de perfil",
                "heading": "Hay un perfil por revisar",
                "intro": "Muestra de una solicitud recibida desde el formulario; los datos son ficticios.",
                "details": [{"label": "Nombre informado", "value": "Camila Ejemplo"}],
                "action_label": "Ver solicitudes de perfil",
                "action_url": request.build_absolute_uri(reverse("clientes:medical_requests")),
                "footer_note": "Ejemplo con datos ficticios. Los antecedentes médicos no se incluyen en este correo.",
            }
        elif tipo == "morosidad":
            filas = [
                {"client": "Camila Ejemplo", "plan": "FLUYE", "period": "10/2026", "balance": "$69.000"},
                {"client": "Sofía Demo", "plan": "INICIAL", "period": "10/2026", "balance": "$48.000"},
            ]
            email = {
                "subject": "EJEMPLO · Aledra Pilates: mensualidades pendientes 10/2026",
                "text_body": (
                    "Muestra ficticia del aviso de mensualidades pendientes.\n\n"
                    "- Camila Ejemplo: FLUYE · 10/2026 · Saldo: $69.000\n"
                    "- Sofía Demo: INICIAL · 10/2026 · Saldo: $48.000\n\n"
                    "Los nombres y montos son ficticios; no representan deudas reales."
                ),
                "notification_type": "EJEMPLO · aviso de pagos",
                "heading": "Mensualidades pendientes · 10/2026",
                "intro": "Muestra de los saldos que se informan después del día 7; los datos son ficticios.",
                "rows": filas,
                "action_label": "Revisar pagos pendientes",
                "action_url": request.build_absolute_uri("/pagos/?estado=pendiente"),
                "footer_note": "Ejemplo con nombres y montos ficticios; no corresponde a una deuda real.",
            }
        elif tipo == "prueba":
            email = {
                "subject": "Aledra Pilates: prueba de correo",
                "text_body": (
                    "Este es un correo de prueba del sistema Aledra Pilates.\n\n"
                    "Confirma que el envío desde Render llegó correctamente."
                ),
                "notification_type": "Prueba de envío",
                "heading": "El correo de Aledra está listo",
                "intro": "Este mensaje confirma que el sistema puede enviar notificaciones a la administración.",
                "details": [{"label": "Estado", "value": "Correo de prueba generado correctamente"}],
                "action_label": "Abrir notificaciones",
                "action_url": request.build_absolute_uri("/notificaciones/"),
                "footer_note": "Este mensaje es solo una prueba; no requiere ninguna acción.",
            }
        else:
            messages.error(request, "Selecciona un tipo de correo de prueba válido.")
            return redirect("notificaciones:index")

        try:
            sent = enviar_correo_administracion(recipient_list=recipients, **email)
        except Exception:
            logger.exception("Falló el envío de prueba de correo a administración.")
            messages.error(request, "No se pudo enviar el correo de prueba. Revisa el registro del servicio.")
            return redirect("notificaciones:index")

        if sent:
            messages.success(request, "Correo de prueba enviado a administración.")
        else:
            messages.error(request, "El servicio de correo no aceptó el mensaje de prueba.")
        return redirect("notificaciones:index")
