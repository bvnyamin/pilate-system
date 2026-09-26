from datetime import date
from decimal import Decimal

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.models import ProtectedError
from django.test import TestCase
from django.urls import reverse

from clientes.models import Cliente
from mensualidades.models import ClientePlan
from planes.models import Plan

from .admin import PagoAdmin
from .models import Pago


class PagoTests(TestCase):
    def setUp(self):
        cliente = Cliente.objects.create(
            nombres="María",
            apellidos="Soto",
            rut="12.345.678-5",
        )
        plan = Plan.objects.get(nombre="FLUYE")
        self.mensualidad = ClientePlan.objects.create(
            cliente=cliente,
            plan=plan,
            periodo_mes=5,
            periodo_anio=2026,
            descuento_porcentaje=Decimal("22"),
            fecha_inicio=date(2026, 5, 1),
            fecha_fin=date(2026, 5, 31),
        )

    def crear_pago(self, **overrides):
        values = {
            "cliente_plan": self.mensualidad,
            "concepto": "Mensualidad mayo 2026",
            "monto_clp": 30000,
            "metodo_pago": Pago.MetodoPago.TRANSFERENCIA,
            "fecha_pago": date(2026, 5, 2),
            "estado_pago": Pago.EstadoPago.PARCIAL,
        }
        values.update(overrides)
        return Pago.objects.create(**values)

    def test_catalog_choices_and_default_date_state(self):
        pago = self.crear_pago()

        self.assertEqual(set(Pago.MetodoPago.values), {"transferencia", "efectivo", "debito", "credito"})
        self.assertEqual(set(Pago.EstadoPago.values), {"pagado", "pendiente", "parcial", "anulado"})
        self.assertEqual(pago.estado_pago, Pago.EstadoPago.PARCIAL)
        self.assertEqual(str(pago), "Mensualidad mayo 2026 · $30.000 · 02/05/2026")

    def test_partial_payments_accumulate_balance_without_exceeding_agreement(self):
        self.crear_pago()
        self.assertEqual(self.mensualidad.total_pagado_clp, 30000)
        self.assertEqual(self.mensualidad.saldo_pendiente_clp, 23820)

        self.crear_pago(
            concepto="Saldo mensualidad mayo",
            monto_clp=23820,
            estado_pago=Pago.EstadoPago.PAGADO,
        )
        self.assertEqual(self.mensualidad.total_pagado_clp, 53820)
        self.assertEqual(self.mensualidad.saldo_pendiente_clp, 0)

    def test_pending_and_annulled_payments_do_not_count_as_received(self):
        self.crear_pago(estado_pago=Pago.EstadoPago.PENDIENTE)
        self.crear_pago(
            concepto="Pago anulado",
            monto_clp=5000,
            estado_pago=Pago.EstadoPago.ANULADO,
        )

        self.assertEqual(self.mensualidad.total_pagado_clp, 0)
        self.assertEqual(self.mensualidad.saldo_pendiente_clp, 53820)

    def test_cannot_receive_more_than_agreed_amount(self):
        self.crear_pago()

        with self.assertRaises(ValidationError) as error:
            self.crear_pago(
                monto_clp=23821,
                estado_pago=Pago.EstadoPago.PAGADO,
            )

        self.assertIn("monto_clp", error.exception.message_dict)
        self.assertEqual(Pago.objects.count(), 1)

    def test_annulling_payment_restores_the_outstanding_balance(self):
        pago = self.crear_pago()
        pago.estado_pago = Pago.EstadoPago.ANULADO
        pago.save()

        self.assertEqual(self.mensualidad.total_pagado_clp, 0)
        self.assertEqual(self.mensualidad.saldo_pendiente_clp, 53820)

    def test_rejects_zero_amount_and_protects_monthly_record(self):
        with self.assertRaises(ValidationError):
            self.crear_pago(monto_clp=0)

        pago = self.crear_pago()
        with self.assertRaises(ProtectedError):
            self.mensualidad.delete()
        self.assertTrue(Pago.objects.filter(pk=pago.pk).exists())

    def test_admin_is_registered_and_disables_physical_deletion(self):
        self.assertIsInstance(admin.site._registry[Pago], PagoAdmin)
        self.assertIsNone(PagoAdmin.actions)
        self.assertFalse(admin.site._registry[Pago].has_delete_permission(None))


class PagoViewsTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username="duena",
            email="duena@example.test",
            password="test-password-only",
        )
        self.client.force_login(self.usuario)
        cliente = Cliente.objects.create(
            nombres="María",
            apellidos="Soto",
            rut="12.345.678-5",
        )
        plan = Plan.objects.get(nombre="FLUYE")
        self.mensualidad = ClientePlan.objects.create(
            cliente=cliente,
            plan=plan,
            periodo_mes=6,
            periodo_anio=2026,
            descuento_porcentaje=Decimal("22"),
            fecha_inicio=date(2026, 6, 1),
            fecha_fin=date(2026, 6, 30),
        )

    def datos_formulario(self, **overrides):
        values = {
            "cliente_plan": self.mensualidad.pk,
            "concepto": "Abono mensualidad junio",
            "monto_clp": 20000,
            "metodo_pago": Pago.MetodoPago.TRANSFERENCIA,
            "fecha_pago": "2026-06-03",
            "estado_pago": Pago.EstadoPago.PARCIAL,
            "observaciones": "",
        }
        values.update(overrides)
        return values

    def crear_pago(self, **overrides):
        values = {
            "cliente_plan": self.mensualidad,
            "concepto": "Abono mensualidad junio",
            "monto_clp": 20000,
            "metodo_pago": Pago.MetodoPago.TRANSFERENCIA,
            "fecha_pago": date(2026, 6, 3),
            "estado_pago": Pago.EstadoPago.PARCIAL,
        }
        values.update(overrides)
        return Pago.objects.create(**values)

    def test_all_routes_require_authentication(self):
        pago = self.crear_pago()
        self.client.logout()
        routes = [
            reverse("pagos:list"),
            reverse("pagos:create"),
            reverse("pagos:update", kwargs={"pk": pago.pk}),
            reverse("pagos:set_status", kwargs={"pk": pago.pk}),
        ]

        for route in routes:
            with self.subTest(route=route):
                self.assertRedirects(self.client.get(route), f"{reverse('login')}?next={route}")

    def test_list_searches_and_filters_payment_status_and_method(self):
        self.crear_pago()
        response = self.client.get(
            reverse("pagos:list"),
            {"q": "María", "estado": "parcial", "metodo": "transferencia"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "$20.000")
        self.assertContains(response, "FLUYE")
        self.assertEqual(response.context["total_pagos"], 1)

        filtered = self.client.get(reverse("pagos:list"), {"estado": "anulado"})
        self.assertEqual(filtered.context["total_pagos"], 0)

    def test_create_partial_payment_updates_monthly_balance(self):
        response = self.client.post(reverse("pagos:create"), self.datos_formulario())

        pago = Pago.objects.get(cliente_plan=self.mensualidad)
        self.assertRedirects(response, reverse("pagos:list"))
        self.assertEqual(pago.monto_clp, 20000)
        self.assertEqual(self.mensualidad.total_pagado_clp, 20000)
        self.assertEqual(self.mensualidad.saldo_pendiente_clp, 33820)

    def test_form_exposes_monthly_balance_context(self):
        response = self.client.get(reverse("pagos:create"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "data-precio-acordado=\"53820\"")
        self.assertContains(response, "Saldo antes de este movimiento")

    def test_create_rejects_amount_over_remaining_agreement(self):
        self.crear_pago(monto_clp=50000, estado_pago=Pago.EstadoPago.PAGADO)

        response = self.client.post(
            reverse("pagos:create"),
            self.datos_formulario(monto_clp=4000, estado_pago=Pago.EstadoPago.PAGADO),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "superaría el precio acordado")
        self.assertEqual(Pago.objects.count(), 1)

    def test_update_payment(self):
        pago = self.crear_pago()

        response = self.client.post(
            reverse("pagos:update", kwargs={"pk": pago.pk}),
            self.datos_formulario(
                concepto="Abono corregido",
                monto_clp=25000,
                metodo_pago=Pago.MetodoPago.DEBITO,
            ),
        )

        pago.refresh_from_db()
        self.assertRedirects(response, reverse("pagos:list"))
        self.assertEqual(pago.concepto, "Abono corregido")
        self.assertEqual(pago.monto_clp, 25000)
        self.assertEqual(pago.metodo_pago, Pago.MetodoPago.DEBITO)

    def test_anulled_status_preserves_record_and_restores_balance(self):
        pago = self.crear_pago()
        route = reverse("pagos:set_status", kwargs={"pk": pago.pk})

        self.assertEqual(self.client.get(route).status_code, 405)
        response = self.client.post(route, {"estado": Pago.EstadoPago.ANULADO})

        pago.refresh_from_db()
        self.assertRedirects(response, reverse("pagos:list"))
        self.assertEqual(pago.estado_pago, Pago.EstadoPago.ANULADO)
        self.assertTrue(Pago.objects.filter(pk=pago.pk).exists())
        self.assertEqual(self.mensualidad.total_pagado_clp, 0)

        invalid = self.client.post(route, {"estado": "eliminado"})
        self.assertEqual(invalid.status_code, 400)
