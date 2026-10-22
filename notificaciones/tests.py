from datetime import date
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from clientes.models import Cliente
from mensualidades.models import ClientePlan
from pagos.models import Pago
from planes.models import Plan

from .models import AvisoMorosidadEnviado
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
