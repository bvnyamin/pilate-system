from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from clientes.models import Cliente
from pagos.models import Pago

from .models import Gasto


class ReportesViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username="reportes-admin", password="Test-password-123")
        cls.cliente = Cliente.objects.create(
            nombres="Camila", apellidos="Reporte", rut="11.111.111-1",
            fecha_incorporacion=date(2021, 4, 5),
        )

    def setUp(self):
        self.client.force_login(self.user)

    def test_reportes_exige_inicio_de_sesion(self):
        self.client.logout()
        response = self.client.get(reverse("reportes:index"))
        self.assertEqual(response.status_code, 302)

    def test_formulario_gasto_habilita_formato_monetario_clp(self):
        response = self.client.get(reverse("reportes:gasto_create"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="monto_clp"')
        self.assertContains(response, 'data-input-format="clp"')
        self.assertContains(response, "los puntos se agregan automáticamente")

    def test_reporte_compara_ingresos_confirmados_y_gastos_por_anio(self):
        Pago.objects.create(
            tipo_pago=Pago.TipoPago.MATRICULA,
            cliente=self.cliente,
            concepto="Matrícula",
            monto_clp=Pago.MONTO_MATRICULA_CLP,
            metodo_pago=Pago.MetodoPago.EFECTIVO,
            fecha_pago=date(2026, 3, 4),
            estado_pago=Pago.EstadoPago.PAGADO,
        )
        Pago.objects.create(
            tipo_pago=Pago.TipoPago.MATRICULA,
            cliente=Cliente.objects.create(
                nombres="Sofia", apellidos="Pendiente", rut="22.222.222-2",
            ),
            concepto="Matrícula",
            monto_clp=Pago.MONTO_MATRICULA_CLP,
            metodo_pago=Pago.MetodoPago.EFECTIVO,
            fecha_pago=date(2026, 3, 5),
            estado_pago=Pago.EstadoPago.PENDIENTE,
        )
        Gasto.objects.create(
            categoria=Gasto.Categoria.ARRIENDO,
            descripcion="Arriendo marzo",
            monto_clp=300000,
            fecha=date(2026, 3, 3),
        )

        response = self.client.get(reverse("reportes:index"), {"anio": "2026"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_ingresos"], 25000)
        self.assertEqual(response.context["total_gastos"], 300000)
        self.assertEqual(response.context["balance_anual"], -275000)
        self.assertEqual(response.context["meses"][2]["ingresos"], 25000)
        self.assertEqual(response.context["meses"][2]["gastos"], 300000)

    def test_registrar_gasto_y_filtrar_categoria(self):
        response = self.client.post(reverse("reportes:gasto_create"), {
            "categoria": Gasto.Categoria.INTERNET,
            "descripcion": "Internet del estudio",
            "monto_clp": "25990",
            "fecha": "2026-10-01",
            "observaciones": "Boleta de prueba",
        })
        self.assertRedirects(response, reverse("reportes:gastos"))
        gasto = Gasto.objects.get()

        response = self.client.get(reverse("reportes:gastos"), {
            "anio": "2026", "categoria": Gasto.Categoria.INTERNET,
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["gastos"]), [gasto])
        self.assertEqual(response.context["total_anual"], 25990)

    def test_gasto_no_acepta_monto_cero(self):
        response = self.client.post(reverse("reportes:gasto_create"), {
            "categoria": Gasto.Categoria.AGUA,
            "descripcion": "Boleta inválida",
            "monto_clp": "0",
            "fecha": "2026-10-01",
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Gasto.objects.exists())


class ReporteNavigationTests(TestCase):
    def test_reportes_ya_no_figura_deshabilitado(self):
        usuario = get_user_model().objects.create_user(username="sidebar-reports", password="Test-password-123")
        self.client.force_login(usuario)
        response = self.client.get(reverse("dashboard:index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("reportes:index"))
        self.assertNotContains(response, 'aria-disabled="true"><i class="bi bi-bar-chart"')
