from calendar import monthrange
from datetime import time

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from asistencias.models import Asistencia, Sesion
from clientes.models import Cliente
from mensualidades.models import ClientePlan
from pagos.models import Pago
from planes.models import Plan


class DashboardAuthenticationTests(TestCase):
    def setUp(self):
        self.password = "test-password-only"
        self.usuario = get_user_model().objects.create_user(
            username="duena",
            email="duena@example.test",
            password=self.password,
        )

    def test_dashboard_redirects_anonymous_users_to_login(self):
        response = self.client.get(reverse("dashboard:index"))

        expected_url = f"{reverse('login')}?next={reverse('dashboard:index')}"
        self.assertRedirects(response, expected_url)

    def test_authenticated_user_can_open_dashboard(self):
        self.client.login(username=self.usuario.username, password=self.password)

        response = self.client.get(reverse("dashboard:index"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Bienvenida")

    def test_dashboard_metrics_and_activity_use_real_records(self):
        self.client.force_login(self.usuario)
        today = timezone.localdate()
        last_day = today.replace(day=monthrange(today.year, today.month)[1])
        client = Cliente.objects.create(
            nombres="Carla", apellidos="Panel", rut="12345678-5", estado=Cliente.Estado.ACTIVA
        )
        plan = Plan.objects.create(nombre="Plan Dashboard Test", clases_por_mes=8, precio_lista_clp=60000)
        monthly_plan = ClientePlan.objects.create(
            cliente=client,
            plan=plan,
            periodo_mes=today.month,
            periodo_anio=today.year,
            fecha_inicio=today.replace(day=1),
            fecha_fin=last_day,
        )
        Pago.objects.create(
            cliente_plan=monthly_plan, concepto="Abono recibido", monto_clp=10000,
            metodo_pago=Pago.MetodoPago.TRANSFERENCIA, fecha_pago=today,
            estado_pago=Pago.EstadoPago.PAGADO,
        )
        Pago.objects.create(
            cliente_plan=monthly_plan, concepto="Abono parcial", monto_clp=3000,
            metodo_pago=Pago.MetodoPago.EFECTIVO, fecha_pago=today,
            estado_pago=Pago.EstadoPago.PARCIAL,
        )
        Pago.objects.create(
            cliente_plan=monthly_plan, concepto="Pago por confirmar", monto_clp=2000,
            metodo_pago=Pago.MetodoPago.DEBITO, fecha_pago=today,
            estado_pago=Pago.EstadoPago.PENDIENTE,
        )
        Pago.objects.create(
            cliente_plan=monthly_plan, concepto="Movimiento anulado", monto_clp=5000,
            metodo_pago=Pago.MetodoPago.CREDITO, fecha_pago=today,
            estado_pago=Pago.EstadoPago.ANULADO,
        )
        session_present = Sesion.objects.create(fecha=today, hora=time(18, 0), nombre="Pilates tarde")
        session_justified = Sesion.objects.create(fecha=today, hora=time(19, 0), nombre="Pilates noche")
        Asistencia.objects.create(
            sesion=session_present, cliente_plan=monthly_plan, estado=Asistencia.Estado.PRESENTE
        )
        Asistencia.objects.create(
            sesion=session_justified, cliente_plan=monthly_plan, estado=Asistencia.Estado.JUSTIFICADO
        )

        response = self.client.get(reverse("dashboard:index"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["clientes_activas"], 1)
        self.assertEqual(response.context["ingresos_mes"], 13000)
        self.assertEqual(response.context["pagos_pendientes_count"], 1)
        self.assertEqual(response.context["pagos_pendientes_total"], 2000)
        self.assertEqual(response.context["asistencias_hoy"], 1)
        self.assertEqual(response.context["registros_asistencia_hoy"], 2)
        self.assertEqual(len(response.context["ingresos_mensuales"]), 6)
        self.assertContains(response, "Pilates tarde")
        self.assertContains(response, "Carla Panel")

    def test_dashboard_shows_empty_revenue_state_without_fabricated_values(self):
        self.client.force_login(self.usuario)

        response = self.client.get(reverse("dashboard:index"))

        self.assertTrue(response.context["sin_ingresos_grafico"])
        self.assertContains(response, "Aún no hay ingresos registrados para este período.")
        self.assertNotContains(response, "$2.45M")

    def test_logout_closes_the_session(self):
        self.client.login(username=self.usuario.username, password=self.password)

        response = self.client.post(reverse("logout"))

        self.assertRedirects(response, reverse("login"))
        dashboard_response = self.client.get(reverse("dashboard:index"))
        self.assertEqual(dashboard_response.status_code, 302)
