import csv
import io
import json

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from .fichas_medicas import buscar_coincidencia, leer_csv, normalizar_telefono
from .models import Cliente, FichaMedica, ImportacionFichaMedica, SolicitudAltaCliente


def archivo_csv(email="ANA@example.test", telefono="+56 9 1234 5678", timestamp="27/09/2026 18:00:00", **kwargs):
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, delimiter=kwargs.get("delimiter", ","))
    writer.writerow([
        "Marca temporal", "Nombre completo", "Correo electronico", "Telefono de contacto",
        "Antecedentes", " Nombre de contacto de emergencia ", " Teléfono de contacto ",
    ])
    writer.writerow([timestamp, "Ana Ficticia", email, telefono, "ANTECEDENTE FICTICIO QA", "Contacto ficticio", "987654321"])
    return SimpleUploadedFile("fichas.csv", buffer.getvalue().encode("utf-8-sig"), content_type="text/csv")


class FichaMedicaImportTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="medical-qa", email="medical-qa@example.test", is_staff=True)
        self.client.force_login(self.user)
        self.cliente = Cliente.objects.create(nombres="Ana", apellidos="Ficticia", rut="12345678-5", email="ana@example.test", telefono="912345678")

    def preview(self, **kwargs):
        response = self.client.post(reverse("clientes:medical_import"), {"archivo": archivo_csv(**kwargs)})
        self.assertEqual(response.status_code, 302)
        lote = ImportacionFichaMedica.objects.latest("pk")
        return lote, self.client.get(response.url)

    def confirm(self, lote, **kwargs):
        data = {"accion": "confirmar", "cliente_2": str(self.cliente.pk)}
        data.update(kwargs)
        return self.client.post(reverse("clientes:medical_preview", args=[lote.pk]), data)

    def test_reads_bom_accents_semicolon_and_correct_phone(self):
        rows = leer_csv(archivo_csv(delimiter=";"))
        self.assertEqual(rows[0]["telefono"], "+56 9 1234 5678")
        self.assertEqual(rows[0]["respuestas"][-1]["pregunta"], "Teléfono de contacto de emergencia")
        self.assertEqual(normalizar_telefono(rows[0]["telefono"]), "912345678")
        self.assertEqual(normalizar_telefono("000000000"), "")
        self.assertEqual(normalizar_telefono("9abc12345678"), "")

    def test_reads_google_spanish_timestamp_with_gmt_and_no_break_space(self):
        rows = leer_csv(archivo_csv(timestamp="2025/11/06 10:23:14 p.\u202fm. GMT-3"))
        self.assertEqual(rows[0]["respondida_en"], "2025-11-06T22:23:14-03:00")
        midnight = leer_csv(archivo_csv(timestamp="2025/11/06 12:23:14 a. m. GMT-3"))
        self.assertEqual(midnight[0]["respondida_en"], "2025-11-06T00:23:14-03:00")

    def test_preview_does_not_create_profile_ficha_and_confirmation_does(self):
        lote, response = self.preview()
        self.assertEqual(FichaMedica.objects.count(), 0)
        self.assertContains(response, "Correo y teléfono")
        self.assertContains(response, "ANTECEDENTE FICTICIO QA")
        self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(self.confirm(lote).status_code, 302)
        ficha = FichaMedica.objects.get()
        self.assertEqual(ficha.cliente, self.cliente)
        self.assertEqual(ficha.criterio_asociacion, "Correo y teléfono")
        lote.refresh_from_db()
        self.assertEqual(lote.filas_pendientes, [])


    def test_csv_can_queue_new_client_account_for_administrator_review(self):
        lote, _ = self.preview(email="nueva@example.test", telefono="+56 9 7654 3210")
        response = self.confirm(lote, cliente_2="", solicitud_2="1")
        self.assertEqual(response.status_code, 302)
        solicitud = SolicitudAltaCliente.objects.get()
        self.assertEqual(solicitud.estado, SolicitudAltaCliente.Estado.PENDIENTE)
        self.assertEqual(solicitud.email_reportado, "nueva@example.test")
        self.assertEqual(solicitud.respuestas[0]["respuesta"], "27/09/2026 18:00:00")
        self.assertEqual(Cliente.objects.count(), 1)
        self.assertEqual(FichaMedica.objects.count(), 0)
        self.assertEqual(self.client.get(reverse("clientes:medical_requests")).status_code, 200)

    def test_admin_approval_creates_only_client_and_medical_profiles(self):
        lote, _ = self.preview(email="nueva@example.test", telefono="+56 9 7654 3210")
        self.confirm(lote, cliente_2="", solicitud_2="1")
        solicitud = SolicitudAltaCliente.objects.get()
        review_url = reverse("clientes:medical_request_review", args=[solicitud.pk])
        review_page = self.client.get(review_url)
        self.assertContains(review_page, 'data-input-format="rut"')
        self.assertContains(review_page, 'data-input-format="telefono"')
        users_before = get_user_model().objects.count()
        response = self.client.post(review_url, {
            "accion": "aprobar", "cliente_existente": "", "nombres": "Beatriz",
            "apellidos": "Nueva", "rut": "76595582-3", "email": "nueva@example.test",
            "telefono": "+56 9 7654 3210", "motivo_vinculo": "", "resolucion": "",
        })
        self.assertEqual(response.status_code, 302)
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, SolicitudAltaCliente.Estado.APROBADA)
        self.assertEqual(solicitud.cliente.rut, "76595582-3")
        self.assertEqual(solicitud.cliente.fichas_medicas.count(), 1)
        self.assertEqual(get_user_model().objects.count(), users_before)
        self.assertEqual(FichaMedica.objects.get().criterio_asociacion, "Solicitud aprobada")
        self.assertEqual(solicitud.resolucion, "Perfil creado y ficha médica vinculada.")

    def test_admin_can_reject_without_creating_profile_or_account(self):
        lote, _ = self.preview(email="nueva@example.test")
        self.confirm(lote, cliente_2="", solicitud_2="1")
        solicitud = SolicitudAltaCliente.objects.get()
        response = self.client.post(reverse("clientes:medical_request_review", args=[solicitud.pk]), {
            "accion": "rechazar", "resolucion": "No se pudo verificar la identidad.",
        })
        self.assertEqual(response.status_code, 302)
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, SolicitudAltaCliente.Estado.RECHAZADA)
        self.assertEqual(Cliente.objects.count(), 1)
        self.assertEqual(FichaMedica.objects.count(), 0)
        self.assertFalse(get_user_model().objects.filter(email="nueva@example.test").exists())

    def test_approval_is_restricted_to_staff(self):
        lote, _ = self.preview(email="nueva@example.test")
        self.confirm(lote, cliente_2="", solicitud_2="1")
        solicitud = SolicitudAltaCliente.objects.get()
        ordinary = get_user_model().objects.create_user(username="medical-ordinary", email="ordinary@example.test")
        self.client.force_login(ordinary)
        response = self.client.get(reverse("clientes:medical_request_review", args=[solicitud.pk]))
        self.assertEqual(response.status_code, 403)

    def test_match_by_each_contact_and_conflict_is_unassigned(self):
        row = leer_csv(archivo_csv())[0]
        self.cliente.telefono = ""
        self.assertEqual(buscar_coincidencia(row, [self.cliente]), (self.cliente.pk, "Solo correo"))
        self.cliente.email = "different@example.test"
        self.cliente.telefono = "912345678"
        self.assertEqual(buscar_coincidencia(row, [self.cliente]), (self.cliente.pk, "Solo teléfono"))
        other = Cliente.objects.create(nombres="Otra", apellidos="Ficticia", rut="76595582-3", email="ana@example.test")
        selected, criterion = buscar_coincidencia(row, [self.cliente, other])
        self.assertIsNone(selected)
        self.assertIn("distintas", criterion)

    def test_shared_contact_and_emergency_number_never_choose_client(self):
        other = Cliente.objects.create(nombres="Otra", apellidos="Ficticia", rut="76595582-3", email="ana@example.test")
        row = leer_csv(archivo_csv())[0]
        self.assertIsNone(buscar_coincidencia(row, [self.cliente, other])[0])
        row = leer_csv(archivo_csv(email="unknown@example.test", telefono=""))[0]
        other.telefono = "987654321"
        self.assertIsNone(buscar_coincidencia(row, [self.cliente, other])[0])

    def test_manual_match_requires_reason_and_keeps_pending_until_confirmed(self):
        lote, _ = self.preview(email="unknown@example.test", telefono="")
        self.assertEqual(self.confirm(lote).status_code, 200)
        self.assertEqual(FichaMedica.objects.count(), 0)
        self.assertEqual(self.confirm(lote, motivo_2="Contacto anterior confirmado").status_code, 302)
        self.assertEqual(FichaMedica.objects.get().criterio_asociacion, "Manual")

    def test_contacts_are_rechecked_on_confirmation(self):
        lote, _ = self.preview()
        self.cliente.email = "changed@example.test"
        self.cliente.telefono = ""
        self.cliente.save()
        response = self.confirm(lote)
        self.assertContains(response, "asociación manual")
        self.assertEqual(FichaMedica.objects.count(), 0)

    def test_repeated_csv_does_not_duplicate_or_reassign_response(self):
        lote, _ = self.preview()
        self.confirm(lote)
        next_lote, response = self.preview()
        self.assertContains(response, "ya importada")
        self.confirm(next_lote)
        self.assertEqual(FichaMedica.objects.count(), 1)

    def test_new_response_preserves_history_and_latest_response_is_first(self):
        newer, _ = self.preview(timestamp="28/09/2026 18:00:00")
        self.confirm(newer)
        older, _ = self.preview(timestamp="27/09/2026 18:00:00")
        self.confirm(older)
        response = self.client.get(reverse("clientes:detail", args=[self.cliente.pk]))
        fichas = list(response.context["fichas_medicas"])
        self.assertEqual(len(fichas), 2)
        self.assertGreater(fichas[0].respondida_en, fichas[1].respondida_en)
        self.assertContains(response, "Ficha vigente")

    def test_rejects_wrong_headers_invalid_dates_and_non_csv(self):
        for file in [SimpleUploadedFile("wrong.csv", b"a,b\n1,2"), archivo_csv(timestamp="invalid"), SimpleUploadedFile("wrong.exe", b"x")]:
            response = self.client.post(reverse("clientes:medical_import"), {"archivo": file})
            self.assertEqual(response.status_code, 200)
        self.assertEqual(ImportacionFichaMedica.objects.count(), 0)

    def test_ordinary_user_cannot_read_imports_or_medical_profile(self):
        lote, _ = self.preview()
        self.confirm(lote)
        ordinary = get_user_model().objects.create_user(username="medical-denied", email="denied@example.test")
        self.client.force_login(ordinary)
        self.assertEqual(self.client.get(reverse("clientes:medical_import")).status_code, 403)
        self.assertEqual(self.client.get(reverse("clientes:medical_preview", args=[lote.pk])).status_code, 403)
        response = self.client.get(reverse("clientes:detail", args=[self.cliente.pk]))
        self.assertNotContains(response, "ANTECEDENTE FICTICIO QA")

    def test_import_batch_is_scoped_to_uploader_and_requires_login(self):
        lote, _ = self.preview()
        other = get_user_model().objects.create_user(username="medical-other", email="other@example.test", is_staff=True)
        self.client.force_login(other)
        self.assertEqual(self.client.get(reverse("clientes:medical_preview", args=[lote.pk])).status_code, 404)
        self.client.logout()
        self.assertEqual(self.client.get(reverse("clientes:medical_import")).status_code, 302)

    def test_invalid_selection_does_not_partially_import(self):
        lote, _ = self.preview()
        self.assertEqual(self.confirm(lote, cliente_2="999999").status_code, 200)
        self.assertEqual(FichaMedica.objects.count(), 0)


@override_settings(
    GOOGLE_FORMS_WEBHOOK_SECRET="test-webhook-secret",
    GOOGLE_LOGIN_ALLOWED_EMAILS=["admin@example.test"],
)
class GoogleFormsWebhookTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_user(
            username="forms-admin", email="admin@example.test", is_staff=True, is_active=True,
        )
        self.payload = {
            "headers": [
                "Marca temporal", "Nombre completo", "Correo electronico",
                "Telefono de contacto", "Antecedentes",
            ],
            "values": [
                "2026-10-22T10:35:00.000Z", "Clienta Ficticia",
                "nueva@example.test", "+56912345678", "ANTECEDENTE FICTICIO QA",
            ],
        }

    def submit(self, payload=None, secret="test-webhook-secret"):
        return self.client.post(
            reverse("google_forms_medical_webhook"),
            data=json.dumps(payload or self.payload),
            content_type="application/json",
            HTTP_X_ALEDRA_FORMS_SECRET=secret,
        )

    def test_form_submission_creates_pending_request_for_admin_without_account(self):
        user_count = get_user_model().objects.count()
        response = self.submit()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["estado"], "pendiente")
        request = SolicitudAltaCliente.objects.get()
        self.assertEqual(request.estado, SolicitudAltaCliente.Estado.PENDIENTE)
        self.assertEqual(request.creada_por, self.admin)
        self.assertEqual(request.email_reportado, "nueva@example.test")
        self.assertEqual(request.respuestas[-1]["respuesta"], "ANTECEDENTE FICTICIO QA")
        self.assertEqual(Cliente.objects.count(), 0)
        self.assertEqual(get_user_model().objects.count(), user_count)

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        DEFAULT_FROM_EMAIL="Aledra Pilates <avisos@example.test>",
        NOTIFICATION_ADMIN_EMAILS=["admin@example.test"],
    )
    def test_new_request_sends_admin_email_without_medical_details(self):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.submit()

        self.assertEqual(response.status_code, 201)
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ["admin@example.test"])
        self.assertIn("nueva solicitud de perfil", message.subject)
        self.assertIn("Clienta Ficticia", message.body)
        self.assertIn(
            reverse("clientes:medical_request_review", args=[response.json()["solicitud"]]),
            message.body,
        )
        self.assertEqual(message.alternatives[0][1], "text/html")
        self.assertIn("Revisar solicitud", message.alternatives[0][0])
        self.assertIn("Por privacidad", message.alternatives[0][0])
        self.assertNotIn("ANTECEDENTE FICTICIO QA", message.body)
        self.assertNotIn("ANTECEDENTE FICTICIO QA", message.alternatives[0][0])

    def test_repeated_form_submission_is_idempotent(self):
        first = self.submit()
        repeated = self.submit()
        self.assertEqual(first.status_code, 201)
        self.assertEqual(repeated.status_code, 200)
        self.assertEqual(repeated.json()["estado"], "duplicada")
        self.assertEqual(SolicitudAltaCliente.objects.count(), 1)
        self.assertEqual(ImportacionFichaMedica.objects.count(), 1)

    def test_wrong_secret_is_rejected_without_storing_medical_data(self):
        response = self.submit(secret="wrong-secret")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(SolicitudAltaCliente.objects.count(), 0)
        self.assertEqual(ImportacionFichaMedica.objects.count(), 0)

    def test_form_submission_requires_email_and_expected_columns(self):
        values = list(self.payload["values"])
        values[2] = ""
        response = self.submit({**self.payload, "values": values})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(SolicitudAltaCliente.objects.count(), 0)
