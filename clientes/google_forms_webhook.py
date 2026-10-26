"""Webhook for queuing Google Forms medical responses for administrator review."""

import csv
import hmac
import io
import json

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.validators import validate_email
from django.db import transaction
from django.http import JsonResponse
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .fichas_medicas import leer_csv
from .models import FichaMedica, ImportacionFichaMedica, SolicitudAltaCliente
from .solicitudes import crear_solicitud_alta
from notificaciones.services import enviar_aviso_solicitud_alta


MAX_WEBHOOK_BYTES = 256 * 1024
MAX_FORM_COLUMNS = 100


def _csv_de_respuesta(payload):
    headers = payload.get("headers")
    values = payload.get("values")
    if (
        not isinstance(headers, list)
        or not headers
        or len(headers) > MAX_FORM_COLUMNS
        or not isinstance(values, list)
        or len(values) != len(headers)
        or any(not isinstance(value, (str, int, float, bool)) for value in headers + values)
    ):
        raise ValueError("La respuesta debe incluir encabezados y una fila válida del formulario.")

    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow([str(value) for value in headers])
    writer.writerow([str(value) for value in values])
    return SimpleUploadedFile(
        "respuesta-google-forms.csv",
        buffer.getvalue().encode("utf-8-sig"),
        content_type="text/csv",
    )


@csrf_exempt
@never_cache
@require_POST
def recibir_respuesta_ficha_medica(request):
    """Accept one Sheets form-submit event and enqueue it for staff approval."""
    expected_secret = settings.GOOGLE_FORMS_WEBHOOK_SECRET
    if not expected_secret:
        return JsonResponse({"error": "La integración no está configurada."}, status=503)

    supplied_secret = request.headers.get("X-Aledra-Forms-Secret", "")
    if not hmac.compare_digest(supplied_secret, expected_secret):
        return JsonResponse({"error": "No autorizado."}, status=403)

    try:
        content_length = int(request.META.get("CONTENT_LENGTH") or 0)
    except ValueError:
        content_length = MAX_WEBHOOK_BYTES + 1
    if content_length > MAX_WEBHOOK_BYTES:
        return JsonResponse({"error": "La respuesta supera el tamaño permitido."}, status=413)
    body = request.body
    if len(body) > MAX_WEBHOOK_BYTES:
        return JsonResponse({"error": "La respuesta supera el tamaño permitido."}, status=413)
    try:
        payload = json.loads(body)
        row = leer_csv(_csv_de_respuesta(payload))[0]
        validate_email(row["correo"])
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError, ValidationError, KeyError, TypeError) as exc:
        return JsonResponse({"error": str(exc) or "La respuesta del formulario no es válida."}, status=400)

    admin_emails = settings.GOOGLE_LOGIN_ALLOWED_EMAILS
    if not admin_emails:
        return JsonResponse({"error": "No hay una administradora configurada para recibir solicitudes."}, status=503)
    User = get_user_model()
    admin_user = User.objects.filter(
        is_active=True, is_staff=True, email__in=admin_emails,
    ).order_by("pk").first()
    if admin_user is None:
        return JsonResponse({"error": "No se encontró la cuenta administradora configurada."}, status=503)

    with transaction.atomic():
        if (
            SolicitudAltaCliente.objects.filter(huella=row["huella"]).exists()
            or FichaMedica.objects.filter(huella=row["huella"]).exists()
        ):
            return JsonResponse({"estado": "duplicada"}, status=200)

        importacion = ImportacionFichaMedica.objects.create(
            archivo="Google Forms automático",
            creada_por=admin_user,
            filas_pendientes=[],
        )
        solicitud, creada = crear_solicitud_alta(
            importacion=importacion,
            fila=row,
            solicitante=admin_user,
        )
        if creada:
            url_revision = request.build_absolute_uri(
                reverse("clientes:medical_request_review", args=[solicitud.pk])
            )
            transaction.on_commit(
                lambda: enviar_aviso_solicitud_alta(solicitud, url_revision)
            )

    return JsonResponse(
        {"estado": "pendiente" if creada else "duplicada", "solicitud": solicitud.pk},
        status=201 if creada else 200,
    )
