"""Branded HTML emails sent to Aledra Pilates administrators."""

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string


def enviar_correo_administracion(
    *,
    subject,
    text_body,
    heading,
    intro,
    notification_type,
    recipient_list,
    details=None,
    rows=None,
    action_label="Abrir Aledra Pilates",
    action_url="",
    footer_note="Este mensaje es automático. Puedes revisar el detalle al ingresar al sistema.",
):
    """Send a multipart email with a plain-text fallback and a branded HTML body."""
    html_body = render_to_string(
        "notificaciones/emails/admin_notification.html",
        {
            "heading": heading,
            "intro": intro,
            "notification_type": notification_type,
            "details": details or [],
            "rows": rows or [],
            "action_label": action_label,
            "action_url": action_url,
            "footer_note": footer_note,
        },
    )
    message = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=recipient_list,
    )
    message.attach_alternative(html_body, "text/html")
    return message.send(fail_silently=False)
