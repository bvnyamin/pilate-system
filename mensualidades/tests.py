from datetime import date, time
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from asistencias.models import Asistencia, Sesion
from clientes.models import Cliente
from planes.models import Plan

from .models import ClientePlan, calcular_fecha_fin_mensual


class ClientePlanTests(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(
            nombres="María",
            apellidos="Soto",
            rut="12.345.678-5",
        )
        self.plan = Plan.objects.get(nombre="FLUYE")

    def crear_mensualidad(self, **overrides):
        values = {
            "cliente": self.cliente,
            "plan": self.plan,
            "periodo_mes": 5,
            "periodo_anio": 2026,
            "descuento_porcentaje": Decimal("0"),
            "fecha_inicio": date(2026, 5, 1),
            "fecha_fin": date(2026, 5, 31),
        }
        values.update(overrides)
        return ClientePlan.objects.create(**values)

    def test_snapshots_catalog_price_and_calculates_discounted_total(self):
        mensualidad = self.crear_mensualidad(descuento_porcentaje=Decimal("22"))

        self.assertEqual(mensualidad.precio_base_clp, 69000)
        self.assertEqual(mensualidad.precio_final_clp, 53820)
        self.assertEqual(mensualidad.estado, ClientePlan.Estado.VIGENTE)
        self.assertEqual(mensualidad.periodo, "05/2026")

    def test_catalog_price_changes_do_not_change_existing_agreement(self):
        mensualidad = self.crear_mensualidad(descuento_porcentaje=Decimal("10"))
        Plan.objects.filter(pk=self.plan.pk).update(precio_lista_clp=80000)

        mensualidad.estado = ClientePlan.Estado.FINALIZADO
        mensualidad.save()
        mensualidad.refresh_from_db()

        self.assertEqual(mensualidad.precio_base_clp, 69000)
        self.assertEqual(mensualidad.precio_final_clp, 62100)

    def test_calculates_end_date_as_one_month_from_start_less_one_day(self):
        mensualidad = self.crear_mensualidad(
            periodo_mes=11,
            periodo_anio=2026,
            fecha_inicio=date(2026, 11, 10),
            fecha_fin=date(2026, 11, 30),
        )

        self.assertEqual(mensualidad.fecha_fin, date(2026, 12, 9))

    def test_monthly_end_date_clamps_short_months(self):
        self.assertEqual(
            calcular_fecha_fin_mensual(date(2026, 1, 31)),
            date(2026, 2, 27),
        )
        self.assertEqual(
            calcular_fecha_fin_mensual(date(2024, 1, 31)),
            date(2024, 2, 28),
        )

    def test_changing_start_date_recalculates_end_date(self):
        mensualidad = self.crear_mensualidad()
        mensualidad.fecha_inicio = date(2026, 5, 10)
        mensualidad.save()

        self.assertEqual(mensualidad.fecha_fin, date(2026, 6, 9))

    def test_one_client_plan_per_calendar_month(self):
        self.crear_mensualidad()

        with self.assertRaises(ValidationError):
            self.crear_mensualidad(plan=Plan.objects.get(nombre="INICIAL"))

        other_month = self.crear_mensualidad(periodo_mes=6, fecha_inicio=date(2026, 6, 1), fecha_fin=date(2026, 6, 30))
        self.assertNotEqual(other_month.pk, None)

    def test_another_client_can_have_plan_in_same_period(self):
        self.crear_mensualidad()
        another_client = Cliente.objects.create(
            nombres="Carolina",
            apellidos="Pérez",
            rut="9.876.543-3",
        )

        another = self.crear_mensualidad(cliente=another_client)

        self.assertEqual(another.periodo_mes, 5)

    def test_rejects_discount_outside_zero_to_one_hundred(self):
        for discount in (Decimal("-1"), Decimal("100.01")):
            with self.subTest(discount=discount):
                with self.assertRaises(ValidationError):
                    self.crear_mensualidad(descuento_porcentaje=discount)

    def test_rejects_invalid_month_and_date_range(self):
        with self.assertRaises(ValidationError):
            self.crear_mensualidad(periodo_mes=13)

        mensualidad = self.crear_mensualidad()
        mensualidad.fecha_fin = date(2026, 4, 30)
        with self.assertRaises(ValidationError):
            mensualidad.save()

    def test_client_and_plan_are_protected_from_deletion(self):
        from django.db.models import ProtectedError

        self.crear_mensualidad()

        with self.assertRaises(ProtectedError):
            self.cliente.delete()
        with self.assertRaises(ProtectedError):
            self.plan.delete()


class ClientePlanViewsTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username="duena",
            email="duena@example.test",
            password="test-password-only",
        )
        self.client.force_login(self.usuario)
        self.cliente = Cliente.objects.create(
            nombres="María",
            apellidos="Soto",
            rut="12.345.678-5",
        )
        self.plan = Plan.objects.get(nombre="FLUYE")

    def datos_formulario(self, **overrides):
        today = timezone.localdate()
        values = {
            "cliente": self.cliente.pk,
            "plan": self.plan.pk,
            "periodo_mes": today.month,
            "periodo_anio": today.year,
            "fecha_inicio": date(today.year, today.month, 1).isoformat(),
            "fecha_fin": date(today.year, today.month, 28).isoformat(),
            "descuento_porcentaje": "22",
            "estado": ClientePlan.Estado.VIGENTE,
        }
        values.update(overrides)
        return values

    def test_all_routes_require_authentication(self):
        mensualidad = self.crear_mensualidad()
        self.client.logout()
        routes = [
            reverse("mensualidades:list"),
            reverse("mensualidades:create"),
            reverse("mensualidades:update", kwargs={"pk": mensualidad.pk}),
            reverse("mensualidades:set_status", kwargs={"pk": mensualidad.pk}),
        ]

        for route in routes:
            with self.subTest(route=route):
                self.assertRedirects(self.client.get(route), f"{reverse('login')}?next={route}")

    def crear_mensualidad(self):
        return ClientePlan.objects.create(
            cliente=self.cliente,
            plan=self.plan,
            periodo_mes=4,
            periodo_anio=2026,
            fecha_inicio=date(2026, 4, 1),
            fecha_fin=date(2026, 4, 30),
        )

    def test_list_searches_and_displays_agreed_total(self):
        self.crear_mensualidad()

        response = self.client.get(reverse("mensualidades:list"), {"q": "María", "mes": "4", "anio": "2026"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "$69.000")
        self.assertContains(response, "FLUYE")
        self.assertEqual(response.context["total_mensualidades"], 1)

    def test_list_displays_remaining_classes_using_attendance_usage(self):
        mensualidad = self.crear_mensualidad()
        Asistencia.objects.create(
            sesion=Sesion.objects.create(fecha=date(2026, 4, 6), hora=time(8, 0)),
            cliente_plan=mensualidad,
            estado=Asistencia.Estado.PRESENTE,
        )
        Asistencia.objects.create(
            sesion=Sesion.objects.create(fecha=date(2026, 4, 7), hora=time(8, 0)),
            cliente_plan=mensualidad,
            estado=Asistencia.Estado.CANCELO,
        )

        response = self.client.get(reverse("mensualidades:list"), {"q": "María", "mes": "4", "anio": "2026"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'aria-label="7 clases restantes de 8"')

    def test_create_snapshots_price_and_applies_discount(self):
        response = self.client.post(reverse("mensualidades:create"), self.datos_formulario())

        mensualidad = ClientePlan.objects.get(cliente=self.cliente)
        self.assertRedirects(response, reverse("mensualidades:list"))
        self.assertEqual(mensualidad.precio_base_clp, 69000)
        self.assertEqual(mensualidad.precio_final_clp, 53820)

    def test_create_calculates_end_date_from_the_start_date(self):
        response = self.client.post(
            reverse("mensualidades:create"),
            self.datos_formulario(
                periodo_mes=11,
                periodo_anio=2026,
                fecha_inicio="2026-11-10",
                fecha_fin="2026-11-30",
            ),
        )

        mensualidad = ClientePlan.objects.get(cliente=self.cliente)
        self.assertRedirects(response, reverse("mensualidades:list"))
        self.assertEqual(mensualidad.fecha_fin, date(2026, 12, 9))

    def test_form_shows_live_price_preview_seed(self):
        response = self.client.get(reverse("mensualidades:create"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Precio final")
        self.assertContains(response, 'data-precio-clp="69000"')
        self.assertContains(response, "Ingresa un porcentaje")
        self.assertContains(response, 'name="fecha_fin"')
        self.assertContains(response, 'readonly aria-describedby="fecha-fin-help"')
        self.assertContains(response, "un mes desde el inicio, menos un día")
        self.assertContains(response, 'src="/static/js/mensualidades.js?v=4"')
        primer_dia_mes = timezone.localdate().replace(day=1).isoformat()
        self.assertContains(response, f'name="fecha_inicio" value="{primer_dia_mes}"')

    def test_duplicate_client_and_period_is_rejected_by_form(self):
        first = self.datos_formulario(periodo_mes=4, periodo_anio=2026, fecha_inicio="2026-04-01", fecha_fin="2026-04-30")
        self.client.post(reverse("mensualidades:create"), first)

        duplicate = self.client.post(reverse("mensualidades:create"), first)

        self.assertEqual(duplicate.status_code, 200)
        self.assertEqual(ClientePlan.objects.filter(cliente=self.cliente, periodo_mes=4, periodo_anio=2026).count(), 1)

    def test_update_keeps_historical_base_price(self):
        mensualidad = self.crear_mensualidad()
        Plan.objects.filter(pk=self.plan.pk).update(precio_lista_clp=80000)
        values = self.datos_formulario(
            periodo_mes=4,
            periodo_anio=2026,
            fecha_inicio="2026-04-01",
            fecha_fin="2026-04-30",
            descuento_porcentaje="10",
        )

        response = self.client.post(
            reverse("mensualidades:update", kwargs={"pk": mensualidad.pk}),
            values,
        )

        mensualidad.refresh_from_db()
        self.assertRedirects(response, reverse("mensualidades:list"))
        self.assertEqual(mensualidad.precio_base_clp, 69000)
        self.assertEqual(mensualidad.precio_final_clp, 62100)

    def test_status_is_post_only_and_preserves_record(self):
        mensualidad = self.crear_mensualidad()
        route = reverse("mensualidades:set_status", kwargs={"pk": mensualidad.pk})

        self.assertEqual(self.client.get(route).status_code, 405)
        response = self.client.post(route, {"estado": ClientePlan.Estado.FINALIZADO})

        mensualidad.refresh_from_db()
        self.assertRedirects(response, reverse("mensualidades:list"))
        self.assertEqual(mensualidad.estado, ClientePlan.Estado.FINALIZADO)
        self.assertTrue(ClientePlan.objects.filter(pk=mensualidad.pk).exists())

        invalid = self.client.post(route, {"estado": "eliminada"})
        self.assertEqual(invalid.status_code, 400)
