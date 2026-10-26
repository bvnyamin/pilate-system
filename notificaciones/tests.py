from datetime import date
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from clientes.models import Cliente, ImportacionFichaMedica, SolicitudAltaCliente
from mensualidades.models import ClientePlan
from pagos.models import Pago
from planes.models import Plan

from .models import AvisoMorosidadEnviado, NotificacionLeida
from .services import enviar_aviso_morosidad, mensualidades_morosas, resumen_notificaciones


class NotificacionesMorosidadTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_user(
            username="avisos-admin",
            email="admin@example.test",
            password="test-password-only",
            is_staff=True,
        )
        cls.cliente = Cliente.objects.create(
            nombres="María",
            apellidos="Soto",
            rut="12.345.678-5",
        )
        cls.mensualidad = ClientePlan.objects.create(
            cliente=cls.cliente,
            plan=Plan.objects.get(nombre="FLUYE"),
            periodo_mes=10,
            periodo_anio=2026,
            descuento_porcentaje=Decimal("0"),
            fecha_inicio=date(2026, 10, 1),
            fecha_fin=date(2026, 10, 31),
        )

    def test_alerta_se_activa_desde_el_dia_siete_y_cuenta_solo_saldo_no_recibido(self):
        self.assertEqual(mensualidades_morosas(date(2026, 10, 6)).count(), 0)
        self.assertEqual(mensualidades_morosas(date(2026, 10, 7)).count(), 1)

        Pago.objects.create(
            tipo_pago=Pago.TipoPago.MENSUALIDAD,
            cliente_plan=self.mensualidad,
            concepto="Abono mensualidad",
            monto_clp=10000,
            metodo_pago=Pago.MetodoPago.TRANSFERENCIA,
            fecha_pago=date(2026, 10, 7),
            estado_pago=Pago.EstadoPago.PARCIAL,
        )
        mensualidad = mensualidades_morosas(date(2026, 10, 7)).get()
        self.assertEqual(mensualidad.saldo_aviso, self.mensualidad.precio_final_clp - 10000)

    def test_campana_y_vista_muestran_solo_a_administracion(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("notificaciones:index"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["notification_count"], 1)
        self.assertEqual(len(response.context["notification_items"]), 1)
        self.assertContains(response, "María Soto")
        self.assertContains(response, "Saldo pendiente")
        self.assertContains(response, 'data-notification-trigger')
        self.assertContains(response, 'aria-haspopup="dialog"')

        client_user = get_user_model().objects.create_user(
            username="avisos-no-admin", password="test-password-only"
        )
        self.client.force_login(client_user)
        denied = self.client.get(reverse("notificaciones:index"))
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(resumen_notificaciones(client_user, date(2026, 10, 7))["notification_count"], 0)

    def test_solicitud_de_ficha_medica_aparece_en_campana_sin_detalles_de_salud(self):
        importacion = ImportacionFichaMedica.objects.create(
            archivo="Google Forms automático", creada_por=self.admin,
        )
        solicitud = SolicitudAltaCliente.objects.create(
            importacion=importacion,
            huella="a" * 64,
            nombre_reportado="Clienta de prueba",
            email_reportado="prueba@example.test",
            respondida_en="2026-10-22T12:00:00Z",
            respuestas=[{"pregunta": "Antecedentes", "respuesta": "DATO MÉDICO CONFIDENCIAL QA"}],
            creada_por=self.admin,
        )
        self.client.force_login(self.admin)
        response = self.client.get(reverse("notificaciones:index"))
        self.assertEqual(response.context["notification_count"], 2)
        self.assertEqual(len(response.context["notification_request_items"]), 1)
        self.assertContains(response, "Nueva solicitud de ficha médica")
        self.assertContains(response, reverse("notificaciones:marcar_leida"))
        self.assertContains(response, f'value="{solicitud.pk}"')
        self.assertNotContains(response, "DATO MÉDICO CONFIDENCIAL QA")

    def test_al_abrir_un_aviso_de_morosidad_se_marca_leido_y_baja_el_contador(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("notificaciones:marcar_leida"),
            {"tipo": "mensualidad", "id": self.mensualidad.pk},
        )

        self.assertRedirects(response, reverse("clientes:detail", args=[self.cliente.pk]))
        leida = NotificacionLeida.objects.get(usuario=self.admin)
        self.assertEqual(leida.clave, f"mensualidad:{self.mensualidad.pk}:2026-10")
        resumen = resumen_notificaciones(self.admin, date(2026, 10, 26))
        self.assertEqual(resumen["notification_count"], 0)
        self.assertTrue(resumen["notification_has_items"])
        self.assertTrue(resumen["notification_items"][0].notification_is_read)

        response = self.client.get(reverse("notificaciones:index"))
        self.assertContains(response, "Revisada")
        self.assertContains(response, "Ya revisaste todas estas notificaciones")

    def test_al_abrir_solicitud_se_marca_leida_solo_para_esa_administradora(self):
        importacion = ImportacionFichaMedica.objects.create(
            archivo="Google Forms automático", creada_por=self.admin,
        )
        solicitud = SolicitudAltaCliente.objects.create(
            importacion=importacion,
            huella="b" * 64,
            nombre_reportado="Clienta solicitud pendiente",
            email_reportado="solicitud@example.test",
            respondida_en="2026-10-22T12:00:00Z",
            respuestas=[],
            creada_por=self.admin,
        )
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("notificaciones:marcar_leida"),
            {"tipo": "solicitud", "id": solicitud.pk},
        )

        self.assertRedirects(response, reverse("clientes:medical_request_review", args=[solicitud.pk]))
        resumen_admin = resumen_notificaciones(self.admin, date(2026, 10, 26))
        self.assertTrue(resumen_admin["notification_request_items"][0].notification_is_read)

        otra_admin = get_user_model().objects.create_user(
            username="segunda-admin-avisos", password="test-password-only", is_staff=True,
        )
        resumen_otra_admin = resumen_notificaciones(otra_admin, date(2026, 10, 26))
        self.assertFalse(resumen_otra_admin["notification_request_items"][0].notification_is_read)
        self.assertEqual(resumen_otra_admin["notification_count"], 2)

    def test_no_se_puede_marcar_un_aviso_por_get_ni_una_mensualidad_ya_pagada(self):
        self.client.force_login(self.admin)
        response = self.client.get(
            reverse("notificaciones:marcar_leida"),
            {"tipo": "mensualidad", "id": self.mensualidad.pk},
        )
        self.assertEqual(response.status_code, 405)
        self.assertFalse(NotificacionLeida.objects.exists())

        Pago.objects.create(
            tipo_pago=Pago.TipoPago.MENSUALIDAD,
            cliente_plan=self.mensualidad,
            concepto="Pago completo",
            monto_clp=self.mensualidad.precio_final_clp,
            metodo_pago=Pago.MetodoPago.TRANSFERENCIA,
            fecha_pago=date(2026, 10, 26),
            estado_pago=Pago.EstadoPago.PAGADO,
        )
        response = self.client.post(
            reverse("notificaciones:marcar_leida"),
            {"tipo": "mensualidad", "id": self.mensualidad.pk},
        )
        self.assertEqual(response.status_code, 404)
        self.assertFalse(NotificacionLeida.objects.exists())

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        DEFAULT_FROM_EMAIL="Aledra Pilates <avisos@example.test>",
        NOTIFICATION_ADMIN_EMAILS=["admin@example.test"],
    )
    def test_boton_de_prueba_envia_correo_solo_a_administracion(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse("notificaciones:probar_correo"))

        self.assertRedirects(response, reverse("notificaciones:index"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["admin@example.test"])
        self.assertEqual(mail.outbox[0].subject, "Aledra Pilates: prueba de correo")
        self.assertEqual(len(mail.outbox[0].alternatives), 1)
        html = mail.outbox[0].alternatives[0][0]
        self.assertIn("El correo de Aledra está listo", html)
        self.assertIn("Abrir notificaciones", html)

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        DEFAULT_FROM_EMAIL="Aledra Pilates <avisos@example.test>",
        NOTIFICATION_ADMIN_EMAILS=["admin@example.test"],
    )
    def test_ejemplo_de_solicitud_usa_nombre_ficticio_y_no_incluye_datos_medicos(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse("notificaciones:probar_correo"), {"tipo": "solicitud"})

        self.assertRedirects(response, reverse("notificaciones:index"))
        message = mail.outbox[0]
        self.assertIn("EJEMPLO", message.subject)
        self.assertIn("Camila Ejemplo", message.body)
        self.assertIn("Camila Ejemplo", message.alternatives[0][0])
        self.assertIn("ficticios", message.alternatives[0][0])
        self.assertNotIn("hipertensión", message.alternatives[0][0].lower())
        self.assertEqual(message.to, ["admin@example.test"])

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        DEFAULT_FROM_EMAIL="Aledra Pilates <avisos@example.test>",
        NOTIFICATION_ADMIN_EMAILS=["admin@example.test"],
    )
    def test_ejemplo_de_morosidad_identifica_saldos_ficticios(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse("notificaciones:probar_correo"), {"tipo": "morosidad"})

        self.assertRedirects(response, reverse("notificaciones:index"))
        message = mail.outbox[0]
        html = message.alternatives[0][0]
        self.assertIn("EJEMPLO", message.subject)
        self.assertIn("Camila Ejemplo", html)
        self.assertIn("$69.000", html)
        self.assertIn("no corresponde a una deuda real", html)
        self.assertEqual(message.to, ["admin@example.test"])

    def test_boton_de_prueba_no_acepta_usuarios_no_administradores(self):
        user = get_user_model().objects.create_user(
            username="prueba-correo-no-admin", password="test-password-only"
        )
        self.client.force_login(user)

        response = self.client.post(reverse("notificaciones:probar_correo"))

        self.assertEqual(response.status_code, 403)

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        DEFAULT_FROM_EMAIL="Aledra Pilates <avisos@example.test>",
        NOTIFICATION_ADMIN_EMAILS=[],
    )
    @patch("notificaciones.services.timezone.localdate", return_value=date(2026, 10, 7))
    def test_comando_envia_un_solo_resumen_mensual_a_la_administracion(self, _today):
        call_command("enviar_aviso_morosidad", stdout=StringIO())
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["admin@example.test"])
        self.assertIn("María Soto", mail.outbox[0].body)
        self.assertTrue(AvisoMorosidadEnviado.objects.filter(periodo_anio=2026, periodo_mes=10).exists())

        resultado = enviar_aviso_morosidad(date(2026, 10, 7))
        self.assertFalse(resultado["enviado"])
        self.assertEqual(len(mail.outbox), 1)

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend",
        NOTIFICATION_ADMIN_EMAILS=["admin@example.test"],
    )
    def test_backend_de_consola_no_finge_haber_enviado_el_correo(self):
        resultado = enviar_aviso_morosidad(date(2026, 10, 7))
        self.assertFalse(resultado["enviado"])
        self.assertTrue(resultado["registrado_en_consola"])
        self.assertFalse(AvisoMorosidadEnviado.objects.exists())
