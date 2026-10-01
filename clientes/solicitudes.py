"""Servicios para encolar altas desde importaciones o futuras integraciones."""

from django.utils.dateparse import parse_datetime

from .models import SolicitudAltaCliente


def crear_solicitud_alta(*, importacion, fila, solicitante):
    """Guarda una respuesta como alta pendiente; no crea cuenta ni activa acceso."""
    return SolicitudAltaCliente.objects.get_or_create(
        huella=fila["huella"],
        defaults={
            "importacion": importacion,
            "nombre_reportado": fila["nombre"][:240],
            "email_reportado": fila["correo"].strip().casefold(),
            "telefono_reportado": fila["telefono"][:30],
            "respondida_en": parse_datetime(fila["respondida_en"]),
            "respuestas": fila["respuestas"],
            "creada_por": solicitante,
        },
    )
