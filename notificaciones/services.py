import logging

from django.conf import settings
from django.db.models import F, IntegerField, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from mensualidades.models import ClientePlan
from pagos.models import Pago
from clientes.models import SolicitudAltaCliente

from .models import AvisoMorosidadEnviado
from .email_templates import enviar_correo_administracion

logger = logging.getLogger(__name__)


def correos_administracion():
    recipients = list(settings.NOTIFICATION_ADMIN_EMAILS)
    if recipients:
        return recipients

    from usuarios.models import Usuario

    return list(
        Usuario.objects.filter(is_staff=True, is_active=True)
        .exclude(email="")
        .values_list("email", flat=True)
        .distinct()
    )


def enviar_aviso_solicitud_alta(solicitud, url_revision):
    """Email staff about a new profile request without disclosing medical data."""
    recipients = correos_administracion()
    if not recipients:
        return {"enviado": False, "razon": "No hay correos de administración configurados."}

    mensaje = (
        "Llegó una nueva solicitud para crear un perfil de clienta y asociar su ficha médica.\n\n"
        f"Nombre informado: {solicitud.nombre_reportado}\n\n"
        "Por privacidad, los antecedentes de salud no se incluyen en este correo. "
        "Inicia sesión en Aledra para revisar la solicitud:\n"
        f"{url_revision}"
    )
    try:
        cantidad = enviar_correo_administracion(
            subject="Aledra Pilates: nueva solicitud de perfil",
            text_body=mensaje,
            recipient_list=recipients,
            notification_type="Nueva solicitud",
            heading="Hay un perfil por revisar",
            intro="Llegó una nueva solicitud para crear un perfil de clienta y asociar su ficha médica.",
            details=[{"label": "Nombre informado", "value": solicitud.nombre_reportado}],
            action_label="Revisar solicitud",
            action_url=url_revision,
            footer_note=(
                "Por privacidad, este correo no incluye antecedentes de salud. "
                "Inicia sesión para revisar la ficha de forma segura."
            ),
        )
    except Exception:
        logger.exception("No se pudo enviar el aviso de nueva solicitud de perfil.")
        return {"enviado": False, "razon": "No se pudo enviar el correo."}

    backend_consola = settings.EMAIL_BACKEND == "django.core.mail.backends.console.EmailBackend"
    return {
        "enviado": bool(cantidad and not backend_consola),
        "registrado_en_consola": bool(cantidad and backend_consola),
        "destinatarios": recipients,
    }


def mensualidades_morosas(hoy=None):
    hoy = hoy or timezone.localdate()
    if hoy.day < 7:
        return ClientePlan.objects.none()

    recibidos = Coalesce(
        Sum(
            "pagos__monto_clp",
            filter=Q(pagos__estado_pago__in=[Pago.EstadoPago.PAGADO, Pago.EstadoPago.PARCIAL]),
        ),
        Value(0),
        output_field=IntegerField(),
    )
    return (
        ClientePlan.objects.filter(
            periodo_anio=hoy.year,
            periodo_mes=hoy.month,
            estado=ClientePlan.Estado.VIGENTE,
        )
        .select_related("cliente", "plan")
        .annotate(total_recibido_aviso=recibidos)
        .annotate(saldo_aviso=F("precio_final_clp") - F("total_recibido_aviso"))
        .filter(saldo_aviso__gt=0)
        .order_by("cliente__apellidos", "cliente__nombres")
    )


def resumen_notificaciones(user, hoy=None):
    hoy = hoy or timezone.localdate()
    if not user.is_authenticated or not user.is_staff:
        return {
            "notification_count": 0,
            "notification_items": [],
            "notification_request_items": [],
            "notification_period": hoy,
            "notification_is_active": hoy.day >= 7,
        }
    items = list(mensualidades_morosas(hoy))
    requests = list(
        SolicitudAltaCliente.objects.filter(estado=SolicitudAltaCliente.Estado.PENDIENTE)
        .order_by("-creada_en")[:10]
    )
    request_count = SolicitudAltaCliente.objects.filter(
        estado=SolicitudAltaCliente.Estado.PENDIENTE,
    ).count()
    return {
        "notification_count": len(items) + request_count,
        "notification_items": items,
        "notification_request_items": requests,
        "notification_period": hoy,
        "notification_is_active": hoy.day >= 7,
    }


def enviar_aviso_morosidad(hoy=None):
    hoy = hoy or timezone.localdate()
    if hoy.day < 7:
        return {"enviado": False, "razon": "La alerta se activa desde el día 7."}

    mensualidades = list(mensualidades_morosas(hoy))
    if not mensualidades:
        return {"enviado": False, "razon": "No hay mensualidades impagas para este período."}

    ya_enviado = AvisoMorosidadEnviado.objects.filter(
        periodo_anio=hoy.year,
        periodo_mes=hoy.month,
    ).first()
    if ya_enviado:
        return {"enviado": False, "razon": "El aviso de este mes ya fue enviado."}

    recipients = correos_administracion()
    if not recipients:
        return {"enviado": False, "razon": "No hay correos de administración configurados."}

    periodo = f"{hoy.month:02d}/{hoy.year}"
    lineas = [
        "Estas mensualidades siguen con saldo pendiente al día 7 del período:",
        "",
    ]
    for mensualidad in mensualidades:
        lineas.append(
            f"- {mensualidad.cliente}: {mensualidad.plan} · {periodo} · "
            f"Saldo pendiente: ${mensualidad.saldo_aviso:,}".replace(",", ".")
        )
    lineas.extend(["", "Abre el panel administrativo para revisar cada mensualidad."])
    filas_correo = [
        {
            "client": str(mensualidad.cliente),
            "plan": str(mensualidad.plan),
            "period": periodo,
            "balance": "${:,}".format(mensualidad.saldo_aviso).replace(",", "."),
        }
        for mensualidad in mensualidades
    ]
    cantidad = enviar_correo_administracion(
        subject=f"Aledra Pilates: mensualidades pendientes {periodo}",
        text_body="\n".join(lineas),
        recipient_list=recipients,
        notification_type="Seguimiento de pagos",
        heading=f"Mensualidades pendientes · {periodo}",
        intro=f"Hay {len(mensualidades)} mensualidad(es) con saldo pendiente después del día 7.",
        rows=filas_correo,
        action_label="Revisar pagos pendientes",
        action_url=f"{settings.SITE_URL.rstrip('/')}/pagos/?estado=pendiente",
        footer_note="Los saldos consideran pagos recibidos y abonos parciales.",
    )
    backend_consola = settings.EMAIL_BACKEND == "django.core.mail.backends.console.EmailBackend"
    if cantidad and not backend_consola:
        AvisoMorosidadEnviado.objects.create(
            periodo_anio=hoy.year,
            periodo_mes=hoy.month,
            destinatarios=", ".join(recipients),
            clientas_informadas=len(mensualidades),
        )
    return {
        "enviado": bool(cantidad and not backend_consola),
        "registrado_en_consola": bool(cantidad and backend_consola),
        "cantidad": len(mensualidades),
        "destinatarios": recipients,
        "razon": (
            "Aviso enviado."
            if cantidad and not backend_consola
            else "El correo se imprimió en consola; configura SMTP para enviarlo de verdad."
            if cantidad
            else "El backend de correo no aceptó el envío."
        ),
    }
