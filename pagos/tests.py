from datetime import date
from decimal import Decimal

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.models import ProtectedError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from clientes.models import Cliente
from mensualidades.models import ClientePlan
from planes.models import Plan

from .admin import PagoAdmin
from .models import Cuota, Pago


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

    def test_matricula_is_a_fixed_one_time_client_charge(self):
        pago = self.crear_pago(
            tipo_pago=Pago.TipoPago.MATRICULA,
            cliente=self.mensualidad.cliente,
            cliente_plan=None,
            concepto="Matrícula",
            monto_clp=Pago.MONTO_MATRICULA_CLP,
            estado_pago=Pago.EstadoPago.PAGADO,
        )

        self.assertEqual(pago.cliente_asociado, self.mensualidad.cliente)
        self.assertEqual(pago.referencia_display, "Matrícula única")
        self.assertEqual(self.mensualidad.total_pagado_clp, 0)
        with self.assertRaises(ValidationError):
            self.crear_pago(
                tipo_pago=Pago.TipoPago.MATRICULA,
                cliente=self.mensualidad.cliente,
                cliente_plan=None,
                monto_clp=Pago.MONTO_MATRICULA_CLP,
                estado_pago=Pago.EstadoPago.PENDIENTE,
            )
        pago.estado_pago = Pago.EstadoPago.ANULADO
        pago.save()
        with self.assertRaises(ValidationError):
            self.crear_pago(
                tipo_pago=Pago.TipoPago.MATRICULA,
                cliente=self.mensualidad.cliente,
                cliente_plan=None,
                monto_clp=Pago.MONTO_MATRICULA_CLP,
            )

    def test_matricula_rejects_custom_amount_and_partial_state(self):
        base = {
            "tipo_pago": Pago.TipoPago.MATRICULA,
            "cliente": self.mensualidad.cliente,
            "cliente_plan": None,
            "concepto": "Matrícula",
        }
        with self.assertRaises(ValidationError):
            self.crear_pago(**base, monto_clp=10000)
        with self.assertRaises(ValidationError):
            self.crear_pago(
                **base,
                monto_clp=Pago.MONTO_MATRICULA_CLP,
                estado_pago=Pago.EstadoPago.PARCIAL,
            )

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
            "tipo_pago": Pago.TipoPago.MENSUALIDAD,
            "cliente_plan": self.mensualidad.pk,
            "cliente": "",
            "concepto": "Abono mensualidad junio",
            "monto_clp": 20000,
            "metodo_pago": Pago.MetodoPago.TRANSFERENCIA,
            "fecha_pago": "2026-06-03",
            "estado_pago": Pago.EstadoPago.PARCIAL,
            "observaciones": "",
        }
        values.update(overrides)
        return values

    def datos_formulario_matricula(self, **overrides):
        values = {
            "tipo_pago": Pago.TipoPago.MATRICULA,
            "cliente_plan": "",
            "cliente": self.mensualidad.cliente.pk,
            "concepto": "",
            "monto_clp": "",
            "metodo_pago": Pago.MetodoPago.TRANSFERENCIA,
            "fecha_pago": "2026-06-03",
            "estado_pago": Pago.EstadoPago.PAGADO,
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
            reverse("pagos:export"),
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

    def test_list_filters_by_payment_type_month_and_custom_date_range(self):
        self.crear_pago()
        self.client.post(reverse("pagos:create"), self.datos_formulario_matricula())
        self.crear_pago(fecha_pago=date(2026, 5, 31), estado_pago=Pago.EstadoPago.PENDIENTE)

        matriculas = self.client.get(reverse("pagos:list"), {"tipo": Pago.TipoPago.MATRICULA})
        self.assertEqual(matriculas.context["total_pagos"], 1)
        self.assertContains(matriculas, "Matrícula única")

        may_payments = self.client.get(reverse("pagos:list"), {"mes": "2026-05"})
        self.assertEqual(may_payments.context["total_pagos"], 1)
        self.assertEqual(may_payments.context["selected_month"], "2026-05")

        june_range = self.client.get(
            reverse("pagos:list"),
            {"desde": "2026-06-03", "hasta": "2026-06-03"},
        )
        self.assertEqual(june_range.context["total_pagos"], 2)

    def test_list_sorts_payments_by_date_in_both_directions_and_keeps_filters(self):
        older = self.crear_pago(
            concepto="Movimiento más antiguo",
            monto_clp=1000,
            fecha_pago=date(2026, 6, 1),
            estado_pago=Pago.EstadoPago.PENDIENTE,
        )
        newer = self.crear_pago(
            concepto="Movimiento más reciente",
            monto_clp=1000,
            fecha_pago=date(2026, 6, 5),
            estado_pago=Pago.EstadoPago.PENDIENTE,
        )

        recientes = self.client.get(
            reverse("pagos:list"),
            {"estado": Pago.EstadoPago.PENDIENTE, "orden": "fecha", "direccion": "desc"},
        )
        antiguos = self.client.get(
            reverse("pagos:list"),
            {"estado": Pago.EstadoPago.PENDIENTE, "orden": "fecha", "direccion": "asc"},
        )

        self.assertEqual(list(recientes.context["pagos"]), [newer, older])
        self.assertEqual(list(antiguos.context["pagos"]), [older, newer])
        self.assertContains(recientes, 'aria-sort="descending"')
        self.assertContains(recientes, "Más recientes")
        self.assertContains(recientes, "Más antiguos")
        self.assertContains(recientes, "estado=pendiente")

    def test_payment_csv_respects_month_and_matricula_type_filters(self):
        self.client.post(reverse("pagos:create"), self.datos_formulario_matricula())
        self.crear_pago()
        response = self.client.get(
            reverse("pagos:export"),
            {"tipo": Pago.TipoPago.MATRICULA, "mes": "2026-06"},
        )
        contents = response.content.decode("utf-8-sig")

        self.assertIn("Matrícula única", contents)
        self.assertNotIn("Abono mensualidad junio", contents)

    def test_list_shows_real_monthly_payment_summary(self):
        hoy = timezone.localdate()
        self.crear_pago(
            concepto="Abono recibido este mes",
            monto_clp=10000,
            fecha_pago=hoy,
            estado_pago=Pago.EstadoPago.PAGADO,
        )
        self.crear_pago(
            concepto="Pendiente de confirmar",
            monto_clp=5000,
            fecha_pago=hoy,
            estado_pago=Pago.EstadoPago.PENDIENTE,
        )
        self.crear_pago(
            concepto="Movimiento anulado",
            monto_clp=7000,
            fecha_pago=hoy,
            estado_pago=Pago.EstadoPago.ANULADO,
        )

        response = self.client.get(reverse("pagos:list"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["ingresos_mes"], 10000)
        self.assertEqual(response.context["pagos_pendientes_count"], 1)
        self.assertEqual(response.context["pagos_pendientes_total"], 5000)
        self.assertEqual(response.context["pagos_realizados_count"], 1)
        self.assertEqual(response.context["movimientos_activos_count"], 2)
        self.assertEqual(response.context["pagos_realizados_porcentaje"], 50)
        self.assertContains(response, "Ingresos del mes")
        self.assertContains(response, "Historial de pagos")
        self.assertContains(response, 'data-month-picker')
        self.assertContains(response, 'data-month-number="9"')
        self.assertNotContains(response, 'type="month"')

    def test_csv_export_is_filtered_and_neutralizes_formula_cells(self):
        self.crear_pago(concepto="=1+1", estado_pago=Pago.EstadoPago.PAGADO)
        self.crear_pago(concepto="Otro movimiento", estado_pago=Pago.EstadoPago.PENDIENTE)

        response = self.client.get(reverse("pagos:export"), {"estado": "pagado"})
        contenido = response.content.decode("utf-8-sig")

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response["Content-Type"])
        self.assertIn("'=1+1", contenido)
        self.assertNotIn("Otro movimiento", contenido)

    def test_create_partial_payment_updates_monthly_balance(self):
        response = self.client.post(reverse("pagos:create"), self.datos_formulario())

        pago = Pago.objects.get(cliente_plan=self.mensualidad)
        self.assertRedirects(response, reverse("pagos:list"))
        self.assertEqual(pago.monto_clp, 20000)
        self.assertEqual(self.mensualidad.total_pagado_clp, 20000)
        self.assertEqual(self.mensualidad.saldo_pendiente_clp, 33820)

    def test_create_matricula_is_once_and_does_not_reduce_monthly_balance(self):
        response = self.client.post(
            reverse("pagos:create"), self.datos_formulario_matricula()
        )

        pago = Pago.objects.get(tipo_pago=Pago.TipoPago.MATRICULA)
        self.assertRedirects(response, reverse("pagos:list"))
        self.assertEqual(pago.monto_clp, Pago.MONTO_MATRICULA_CLP)
        self.assertEqual(pago.cliente, self.mensualidad.cliente)
        self.assertIsNone(pago.cliente_plan)
        self.assertEqual(self.mensualidad.total_pagado_clp, 0)

        duplicate = self.client.post(
            reverse("pagos:create"), self.datos_formulario_matricula()
        )
        self.assertEqual(duplicate.status_code, 200)
        self.assertContains(duplicate, "ya tiene un registro de matrícula")
        self.assertEqual(Pago.objects.filter(tipo_pago=Pago.TipoPago.MATRICULA).count(), 1)

    def test_matricula_prefill_and_payment_list_render(self):
        response = self.client.get(
            reverse("pagos:create"),
            {"tipo_pago": "matricula", "cliente": self.mensualidad.cliente.pk},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Matrícula única")
        self.assertContains(response, 'data-input-format="clp"')
        self.assertContains(response, 'name="monto_clp" value="25000"')

        self.client.post(reverse("pagos:create"), self.datos_formulario_matricula())
        listing = self.client.get(reverse("pagos:list"))
        self.assertContains(listing, "Matrícula única")
        self.assertContains(listing, "María Soto")

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
        editing = self.client.get(reverse("pagos:update", kwargs={"pk": pago.pk}))
        self.assertContains(editing, f'href="{reverse("pagos:list")}"')

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


class CuotasTests(TestCase):
    def setUp(self):
        usuario = get_user_model().objects.create_user(
            username="admin-cuotas", email="cuotas@example.test", password="test-password-only"
        )
        self.client.force_login(usuario)
        cliente = Cliente.objects.create(nombres="María", apellidos="Soto", rut="12.345.678-5")
        self.mensualidad = ClientePlan.objects.create(
            cliente=cliente,
            plan=Plan.objects.get(nombre="FLUYE"),
            periodo_mes=6,
            periodo_anio=2026,
            descuento_porcentaje=Decimal("22"),
            fecha_inicio=date(2026, 6, 1),
            fecha_fin=date(2026, 6, 30),
        )

    def datos_formulario(self, **overrides):
        values = {
            "tipo_pago": Pago.TipoPago.MENSUALIDAD,
            "cliente_plan": self.mensualidad.pk,
            "cliente": "",
            "concepto": "Abono cuota",
            "monto_clp": 10000,
            "metodo_pago": Pago.MetodoPago.TRANSFERENCIA,
            "fecha_pago": "2026-06-10",
            "estado_pago": Pago.EstadoPago.PARCIAL,
            "observaciones": "",
        }
        values.update(overrides)
        return values

    def crear_pago(self, **overrides):
        values = {
            "cliente_plan": self.mensualidad,
            "concepto": "Abono anterior",
            "monto_clp": 10000,
            "metodo_pago": Pago.MetodoPago.TRANSFERENCIA,
            "estado_pago": Pago.EstadoPago.PAGADO,
        }
        values.update(overrides)
        return Pago.objects.create(**values)

    def test_programacion_reparte_saldo_y_respeta_dia_del_mes(self):
        self.crear_pago(monto_clp=10000, estado_pago=Pago.EstadoPago.PAGADO)

        response = self.client.post(
            reverse("pagos:cuotas_create"),
            {"cliente_plan": self.mensualidad.pk, "cantidad": 3, "fecha_primera_cuota": "2026-01-31"},
        )

        self.assertRedirects(response, reverse("pagos:cuotas"))
        cuotas = list(Cuota.objects.filter(cliente_plan=self.mensualidad))
        self.assertEqual([cuota.monto_clp for cuota in cuotas], [14606, 14606, 14608])
        self.assertEqual(
            [cuota.fecha_vencimiento for cuota in cuotas],
            [date(2026, 1, 31), date(2026, 2, 28), date(2026, 3, 31)],
        )
        self.assertEqual(self.mensualidad.saldo_pendiente_clp, 43820)

        listing = self.client.get(reverse("pagos:cuotas"))
        self.assertContains(listing, "3 de 3 pendientes")
        self.assertContains(listing, "$43.820")

    def test_abonos_de_cuota_actualizan_saldo_y_no_permiten_exceso(self):
        self.client.post(
            reverse("pagos:cuotas_create"),
            {"cliente_plan": self.mensualidad.pk, "cantidad": 2, "fecha_primera_cuota": "2026-06-10"},
        )
        cuota = Cuota.objects.get(cliente_plan=self.mensualidad, numero=1)
        self.assertEqual(self.mensualidad.saldo_pendiente_clp, 53820)

        partial = self.client.post(
            reverse("pagos:create"),
            self.datos_formulario(cuota=cuota.pk, monto_clp=10000),
        )
        self.assertRedirects(partial, reverse("pagos:list"))
        self.assertEqual(cuota.saldo_pendiente_clp, 16910)

        excess = self.client.post(
            reverse("pagos:create"),
            self.datos_formulario(cuota=cuota.pk, monto_clp=16911),
        )
        self.assertEqual(excess.status_code, 200)
        self.assertContains(excess, "superaría el monto de esta cuota")

        final = self.client.post(
            reverse("pagos:create"),
            self.datos_formulario(cuota=cuota.pk, monto_clp=16910, estado_pago=Pago.EstadoPago.PAGADO),
        )
        self.assertRedirects(final, reverse("pagos:list"))
        self.assertEqual(cuota.saldo_pendiente_clp, 0)
        self.assertEqual(self.mensualidad.saldo_pendiente_clp, 26910)
        listing = self.client.get(reverse("pagos:cuotas"))
        self.assertContains(listing, "1 de 2 pendientes")

    def test_cancel_payment_from_installment_returns_to_its_list(self):
        self.crear_pago()
        self.client.post(
            reverse("pagos:cuotas_create"),
            {"cliente_plan": self.mensualidad.pk, "cantidad": 2, "fecha_primera_cuota": "2026-06-10"},
        )
        cuota = Cuota.objects.get(cliente_plan=self.mensualidad, numero=1)
        return_to = f"{reverse('pagos:cuotas')}?q=Maria&page=1"

        response = self.client.get(
            reverse("pagos:create"),
            {"cuota": cuota.pk, "return_to": return_to},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["cancel_url"], return_to)
        self.assertContains(response, f'href="{reverse("pagos:cuotas")}?q=Maria&amp;page=1"')

        invalid = self.client.post(
            reverse("pagos:create"),
            {"cuota": cuota.pk, "return_to": return_to},
        )
        self.assertEqual(invalid.status_code, 200)
        self.assertEqual(invalid.context["cancel_url"], return_to)

        unsafe = self.client.get(
            reverse("pagos:create"),
            {"cuota": cuota.pk, "return_to": "https://example.com/"},
        )
        self.assertEqual(unsafe.context["cancel_url"], reverse("pagos:cuotas"))

    def test_no_duplica_acuerdo_ni_programa_sobre_movimiento_pendiente(self):
        pendiente = self.crear_pago(estado_pago=Pago.EstadoPago.PENDIENTE)
        payload = {"cliente_plan": self.mensualidad.pk, "cantidad": 2, "fecha_primera_cuota": "2026-06-10"}
        first = self.client.post(reverse("pagos:cuotas_create"), payload)
        self.assertContains(first, "Resuelve o anula los movimientos pendientes")
        self.assertFalse(Cuota.objects.exists())

        pendiente.estado_pago = Pago.EstadoPago.ANULADO
        pendiente.save()
        self.assertRedirects(self.client.post(reverse("pagos:cuotas_create"), payload), reverse("pagos:cuotas"))
        duplicate = self.client.post(reverse("pagos:cuotas_create"), payload)
        self.assertContains(duplicate, "ya tiene cuotas programadas")
        self.assertEqual(Cuota.objects.count(), 2)

    def test_pago_de_otro_periodo_y_cambio_de_precio_se_rechazan(self):
        self.client.post(
            reverse("pagos:cuotas_create"),
            {"cliente_plan": self.mensualidad.pk, "cantidad": 2, "fecha_primera_cuota": "2026-06-10"},
        )
        cuota = Cuota.objects.get(cliente_plan=self.mensualidad, numero=1)
        otro_periodo = ClientePlan.objects.create(
            cliente=self.mensualidad.cliente,
            plan=self.mensualidad.plan,
            periodo_mes=7,
            periodo_anio=2026,
            descuento_porcentaje=Decimal("22"),
            fecha_inicio=date(2026, 7, 1),
            fecha_fin=date(2026, 7, 31),
        )
        with self.assertRaises(ValidationError):
            Pago.objects.create(
                cliente_plan=otro_periodo,
                cuota=cuota,
                concepto="Cuota equivocada",
                monto_clp=10000,
                metodo_pago=Pago.MetodoPago.EFECTIVO,
                estado_pago=Pago.EstadoPago.PAGADO,
            )
        self.mensualidad.descuento_porcentaje = Decimal("10")
        with self.assertRaises(ValidationError):
            self.mensualidad.save()

    def test_anular_abono_reabre_la_cuota_y_conserva_el_movimiento(self):
        self.client.post(
            reverse("pagos:cuotas_create"),
            {"cliente_plan": self.mensualidad.pk, "cantidad": 2, "fecha_primera_cuota": "2026-06-10"},
        )
        cuota = Cuota.objects.get(cliente_plan=self.mensualidad, numero=1)
        pago = self.crear_pago(cuota=cuota, monto_clp=cuota.monto_clp)
        self.assertEqual(cuota.saldo_pendiente_clp, 0)

        pago.estado_pago = Pago.EstadoPago.ANULADO
        pago.save()

        self.assertTrue(Pago.objects.filter(pk=pago.pk).exists())
        self.assertEqual(cuota.saldo_pendiente_clp, cuota.monto_clp)
        self.assertEqual(self.mensualidad.saldo_pendiente_clp, 53820)

    def test_abono_previo_no_puede_cambiar_el_saldo_base_del_acuerdo(self):
        pago_previo = self.crear_pago(monto_clp=10000)
        self.client.post(
            reverse("pagos:cuotas_create"),
            {"cliente_plan": self.mensualidad.pk, "cantidad": 2, "fecha_primera_cuota": "2026-06-10"},
        )
        pago_previo.observaciones = "Referencia corregida"
        pago_previo.save()
        pago_previo.monto_clp = 9000
        with self.assertRaises(ValidationError):
            pago_previo.save()

    def test_rutas_de_cuotas_exigen_sesion_y_prefill(self):
        self.client.post(
            reverse("pagos:cuotas_create"),
            {"cliente_plan": self.mensualidad.pk, "cantidad": 2, "fecha_primera_cuota": "2026-06-10"},
        )
        cuota = Cuota.objects.get(cliente_plan=self.mensualidad, numero=1)
        response = self.client.get(reverse("pagos:create"), {"cuota": cuota.pk})
        self.assertContains(response, f'name="cuota"')
        self.assertContains(response, "Cuota 1")

        self.client.logout()
        for route in (reverse("pagos:cuotas"), reverse("pagos:cuotas_create")):
            with self.subTest(route=route):
                self.assertRedirects(self.client.get(route), f"{reverse('login')}?next={route}")
