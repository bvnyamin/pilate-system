from datetime import date, datetime, time

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from asistencias.models import Asistencia, HorarioEstudio, RecuperacionClase, Sesion
from clientes.models import Cliente
from mensualidades.models import ClientePlan
from planes.models import Plan


class AsistenciaModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cliente = Cliente.objects.create(
            nombres="Ana", apellidos="Prueba", rut="12345678-5", estado=Cliente.Estado.ACTIVA
        )
        cls.plan = Plan.objects.create(nombre="Plan Asistencia Test", clases_por_mes=8, precio_lista_clp=60000)
        cls.mensualidad = ClientePlan.objects.create(
            cliente=cls.cliente,
            plan=cls.plan,
            periodo_mes=9,
            periodo_anio=2026,
            fecha_inicio=date(2026, 9, 1),
            fecha_fin=date(2026, 9, 30),
        )
        cls.sesion = Sesion.objects.create(fecha=date(2026, 9, 10), hora=time(18, 0))

    def test_registra_asistencia_vigente_en_periodo(self):
        asistencia = Asistencia.objects.create(sesion=self.sesion, cliente_plan=self.mensualidad)
        self.assertEqual(asistencia.estado, Asistencia.Estado.PRESENTE)
        self.assertEqual(self.sesion.asistencias.count(), 1)

    def test_presente_y_ausente_consumen_clases_del_plan(self):
        Asistencia.objects.create(sesion=self.sesion, cliente_plan=self.mensualidad, estado=Asistencia.Estado.PRESENTE)
        sesion_ausente = Sesion.objects.create(fecha=date(2026, 9, 11), hora=time(18, 0))
        Asistencia.objects.create(sesion=sesion_ausente, cliente_plan=self.mensualidad, estado=Asistencia.Estado.AUSENTE)
        estados_no_consumibles = [
            Asistencia.Estado.CANCELO,
            Asistencia.Estado.JUSTIFICADO,
        ]
        for index, estado in enumerate(estados_no_consumibles, start=11):
            sesion = Sesion.objects.create(fecha=date(2026, 9, index + 10), hora=time(18, 0))
            Asistencia.objects.create(sesion=sesion, cliente_plan=self.mensualidad, estado=estado)

        self.mensualidad.refresh_from_db()
        self.assertEqual(self.mensualidad.clases_utilizadas, 2)
        self.assertEqual(self.mensualidad.clases_restantes, 6)

    def test_cancelacion_con_aviso_de_cuatro_horas_genera_recuperacion(self):
        asistencia = Asistencia.objects.create(
            sesion=self.sesion, cliente_plan=self.mensualidad,
            estado=Asistencia.Estado.CANCELO,
            fecha_aviso_cancelacion=timezone.make_aware(datetime(2026, 9, 10, 13, 59)),
            motivo_cancelacion="Imprevisto familiar",
        )
        self.assertTrue(asistencia.genera_recuperacion)
        self.assertEqual(RecuperacionClase.objects.create(asistencia_origen=asistencia).estado,
                         RecuperacionClase.Estado.PENDIENTE)

    def test_no_permite_sesion_fuera_de_vigencia(self):
        sesion = Sesion.objects.create(fecha=date(2026, 10, 1), hora=time(18, 0))
        with self.assertRaises(ValidationError):
            Asistencia.objects.create(sesion=sesion, cliente_plan=self.mensualidad)

    def test_no_permite_mensualidad_no_vigente(self):
        self.mensualidad.estado = ClientePlan.Estado.FINALIZADO
        self.mensualidad.save()
        with self.assertRaises(ValidationError):
            Asistencia.objects.create(sesion=self.sesion, cliente_plan=self.mensualidad)

    def test_no_permite_dos_registros_de_la_misma_mensualidad_en_sesion(self):
        Asistencia.objects.create(sesion=self.sesion, cliente_plan=self.mensualidad)
        with self.assertRaises(ValidationError):
            Asistencia.objects.create(sesion=self.sesion, cliente_plan=self.mensualidad)

    def test_no_permite_dos_asistencias_consumibles_en_el_mismo_dia(self):
        Asistencia.objects.create(sesion=self.sesion, cliente_plan=self.mensualidad)
        otra_sesion = Sesion.objects.create(fecha=self.sesion.fecha, hora=time(8, 0))
        with self.assertRaises(ValidationError):
            Asistencia.objects.create(
                sesion=otra_sesion, cliente_plan=self.mensualidad, estado=Asistencia.Estado.AUSENTE
            )

    def test_rechaza_horario_duplicado(self):
        with self.assertRaises(ValidationError):
            Sesion.objects.create(fecha=self.sesion.fecha, hora=self.sesion.hora)

    def test_solo_permite_inicios_dentro_de_bloques_del_estudio(self):
        Sesion.objects.create(fecha=date(2026, 9, 12), hora=time(8, 0))
        Sesion.objects.create(fecha=date(2026, 9, 13), hora=time(11, 30))
        Sesion.objects.create(fecha=date(2026, 9, 14), hora=time(17, 0))
        Sesion.objects.create(fecha=date(2026, 9, 16), hora=time(20, 30))

        for invalid_time in (time(7, 30), time(12, 0), time(16, 30), time(21, 0), time(18, 15)):
            with self.subTest(invalid_time=invalid_time):
                with self.assertRaises(ValidationError):
                    Sesion.objects.create(fecha=date(2026, 9, 20), hora=invalid_time)


class AsistenciaViewsTests(TestCase):
    def test_eliminar_sesion_devuelve_clase(self):
        asistencia = Asistencia.objects.create(
            sesion=self.sesion, cliente_plan=self.mensualidad, estado=Asistencia.Estado.PRESENTE,
        )
        restantes = self.mensualidad.clases_restantes
        url = reverse("asistencias:delete", args=[self.sesion.pk])
        self.assertEqual(self.client.post(url).status_code, 403)
        self.usuario.is_staff = True
        self.usuario.save(update_fields=["is_staff"])
        self.assertContains(self.client.get(url), "Eliminar sesión")
        self.assertTrue(Sesion.objects.filter(pk=self.sesion.pk).exists())
        filtros = "fecha=2026-09-15&q=Pilates"
        self.assertRedirects(
            self.client.post(url, {"filtros": filtros}),
            f"{reverse('asistencias:list')}?{filtros}",
        )
        self.assertFalse(Sesion.objects.filter(pk=self.sesion.pk).exists())
        self.assertFalse(Asistencia.objects.filter(pk=asistencia.pk).exists())
        self.mensualidad.refresh_from_db()
        self.assertEqual(self.mensualidad.clases_restantes, restantes + 1)

    @classmethod
    def setUpTestData(cls):
        cls.cliente = Cliente.objects.create(
            nombres="Rosa", apellidos="Sesión", rut="12345678-5", estado=Cliente.Estado.ACTIVA
        )
        cls.plan = Plan.objects.create(nombre="Plan Vistas Asistencia", clases_por_mes=8, precio_lista_clp=64000)
        cls.mensualidad = ClientePlan.objects.create(
            cliente=cls.cliente,
            plan=cls.plan,
            periodo_mes=9,
            periodo_anio=2026,
            fecha_inicio=date(2026, 9, 1),
            fecha_fin=date(2026, 9, 30),
        )
        cls.sesion = Sesion.objects.create(fecha=date(2026, 9, 15), hora=time(18, 0))

    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username="asistencia-ui",
            email="asistencia-ui@example.test",
            password="test-password-only",
        )
        self.client.force_login(self.usuario)

    def test_routes_require_authentication(self):
        self.client.logout()
        for route in [
            reverse("asistencias:list"),
            reverse("asistencias:create"),
            reverse("asistencias:roster", kwargs={"pk": self.sesion.pk}),
        ]:
            with self.subTest(route=route):
                response = self.client.get(route)
                self.assertRedirects(response, f"{reverse('login')}?next={route}")

    def test_list_defaults_to_today_and_supports_all_dates(self):
        response = self.client.get(reverse("asistencias:list"), {"fecha": "2026-09-15"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Control de asistencia")
        self.assertContains(response, "15")
        self.assertEqual(list(response.context["sesiones"]), [self.sesion])

        all_response = self.client.get(reverse("asistencias:list"), {"todas": "1"})
        self.assertEqual(all_response.context["sesiones"].count(), 1)

    def test_list_filters_sessions_by_client_status_and_time_block(self):
        morning = Sesion.objects.create(fecha=self.sesion.fecha, hora=time(8, 0))
        Asistencia.objects.create(
            sesion=self.sesion, cliente_plan=self.mensualidad, estado=Asistencia.Estado.AUSENTE
        )

        morning_response = self.client.get(reverse("asistencias:list"), {
            "todas": "1", "bloque": "matutino",
        })
        status_response = self.client.get(reverse("asistencias:list"), {
            "todas": "1", "estado": Asistencia.Estado.AUSENTE,
        })
        search_response = self.client.get(reverse("asistencias:list"), {
            "todas": "1", "q": "Rosa",
        })
        selected_date_response = self.client.get(reverse("asistencias:list"), {
            "todas": "1", "fecha": self.sesion.fecha.isoformat(),
        })

        self.assertEqual(list(morning_response.context["sesiones"]), [morning])
        self.assertEqual(list(status_response.context["sesiones"]), [self.sesion])
        self.assertEqual(list(search_response.context["sesiones"]), [self.sesion])
        self.assertEqual(list(selected_date_response.context["sesiones"]), [morning, self.sesion])

    def test_create_session_redirects_to_roster(self):
        response = self.client.post(reverse("asistencias:create"), {
            "fecha": "2026-09-16",
            "hora": "19:00",
            "nombre": "Pilates inicial",
            "observaciones": "Traer calcetines antideslizantes",
        })
        created = Sesion.objects.get(fecha=date(2026, 9, 16), hora=time(19, 0))
        self.assertRedirects(response, reverse("asistencias:roster", kwargs={"pk": created.pk}))

    def test_new_session_form_shows_schedule_blocks_and_available_slots(self):
        response = self.client.get(reverse("asistencias:create"), {"fecha": "2026-09-15"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Bloque matutino")
        self.assertContains(response, "Bloque vespertino")
        self.assertContains(response, "08:00 hrs")
        self.assertContains(response, "20:30 hrs")
        self.assertContains(response, 'data-session-time-picker')
        self.assertContains(response, 'class="attendance-time-option"')
        self.assertNotContains(response, '<select name="hora"')
        self.assertNotContains(response, 'value="12:00"')
        self.assertNotContains(response, 'value="21:00"')

        availability = self.client.get(
            reverse("asistencias:available_times"), {"fecha": "2026-09-15"}
        )
        self.assertEqual(availability.status_code, 200)
        slots = {
            slot["value"]: slot["available"]
            for group in availability.json()["groups"]
            for slot in group["slots"]
        }
        self.assertFalse(slots["18:00"])
        self.assertTrue(slots["08:00"])

    def test_available_times_api_requires_valid_date(self):
        response = self.client.get(reverse("asistencias:available_times"), {"fecha": "no-fecha"})

        self.assertEqual(response.status_code, 400)

    def test_roster_renders_monthly_client_and_saves_selected_status(self):
        url = reverse("asistencias:roster", kwargs={"pk": self.sesion.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Rosa Sesión")
        self.assertContains(response, "Plan Vistas Asistencia")
        self.assertContains(response, "8 clases restantes")
        self.assertContains(response, "Presente y Ausente descuentan una clase")
        self.assertContains(response, 'data-session-picker')
        self.assertContains(response, 'class="attendance-session-options"')
        self.assertContains(response, 'aria-current="page"')
        self.assertNotContains(response, '<select aria-label="Horario de la sesión"')
        self.assertContains(response, 'type="radio"')
        self.assertContains(response, "Presente")
        self.assertContains(response, "Ausente")
        self.assertContains(response, "Canceló")
        self.assertNotContains(response, "Justificado")

        response = self.client.post(url, {
            "form-TOTAL_FORMS": "1",
            "form-INITIAL_FORMS": "1",
            "form-0-cliente_plan": str(self.mensualidad.pk),
            "form-0-estado": Asistencia.Estado.CANCELO,
            "form-0-observaciones": "Avisó por mensaje",
            "form-0-motivo_cancelacion": "Imprevisto familiar",
            "form-0-fecha_aviso_cancelacion": "2026-09-15T13:00",
        })
        self.assertRedirects(response, url)
        asistencia = Asistencia.objects.get(sesion=self.sesion, cliente_plan=self.mensualidad)
        self.assertEqual(asistencia.estado, Asistencia.Estado.CANCELO)
        self.assertEqual(asistencia.observaciones, "Avisó por mensaje")
        self.assertTrue(asistencia.genera_recuperacion)
        self.assertEqual(asistencia.recuperacion_generada.estado, RecuperacionClase.Estado.PENDIENTE)
        self.assertEqual(self.mensualidad.asistencias.count(), 1)
        self.mensualidad.refresh_from_db()
        self.assertEqual(self.mensualidad.clases_utilizadas, 0)
        self.assertEqual(self.mensualidad.clases_restantes, 8)

    def test_usa_recuperacion_en_otro_bloque_sin_consumir_otra_clase(self):
        origen = Sesion.objects.create(fecha=date(2026, 9, 16), hora=time(8, 0))
        destino = Sesion.objects.create(fecha=date(2026, 9, 16), hora=time(17, 0))
        origen_url = reverse("asistencias:roster", kwargs={"pk": origen.pk})
        destino_url = reverse("asistencias:roster", kwargs={"pk": destino.pk})
        self.client.post(origen_url, {
            "form-TOTAL_FORMS": "1", "form-INITIAL_FORMS": "1",
            "form-0-cliente_plan": str(self.mensualidad.pk),
            "form-0-estado": Asistencia.Estado.CANCELO,
            "form-0-observaciones": "",
            "form-0-motivo_cancelacion": "Avisó a tiempo",
            "form-0-fecha_aviso_cancelacion": "2026-09-16T04:00",
        })

        target_page = self.client.get(destino_url)
        self.assertContains(target_page, "Recuperó (usar clase pendiente)")
        sesion_anterior = Sesion.objects.create(fecha=date(2026, 9, 14), hora=time(8, 0))
        anterior = Asistencia.objects.create(
            sesion=sesion_anterior, cliente_plan=self.mensualidad,
            estado=Asistencia.Estado.CANCELO, motivo_cancelacion="Avisó a tiempo",
            fecha_aviso_cancelacion=timezone.make_aware(datetime(2026, 9, 14, 3, 0)),
        )
        credito_anterior = RecuperacionClase.objects.create(asistencia_origen=anterior)
        response = self.client.post(destino_url, {
            "form-TOTAL_FORMS": "1", "form-INITIAL_FORMS": "1",
            "form-0-cliente_plan": str(self.mensualidad.pk),
            "form-0-estado": Asistencia.Estado.RECUPERACION,
            "form-0-observaciones": "",
            "form-0-motivo_cancelacion": "",
            "form-0-fecha_aviso_cancelacion": "",
        })

        self.assertRedirects(response, destino_url)
        usado = Asistencia.objects.get(sesion=destino, cliente_plan=self.mensualidad)
        self.assertEqual(usado.estado, Asistencia.Estado.RECUPERACION)
        self.assertEqual(usado.recuperacion_utilizada.estado, RecuperacionClase.Estado.UTILIZADA)
        self.assertEqual(usado.recuperacion_utilizada.pk, credito_anterior.pk)
        self.assertEqual(
            RecuperacionClase.objects.get(asistencia_origen__sesion=origen).estado,
            RecuperacionClase.Estado.PENDIENTE,
        )
        self.mensualidad.refresh_from_db()
        self.assertEqual(self.mensualidad.clases_utilizadas, 0)
        self.assertEqual(self.mensualidad.clases_restantes, 8)

    def test_no_permite_una_segunda_clase_asistida_en_el_mismo_dia(self):
        primera = Sesion.objects.create(fecha=date(2026, 9, 17), hora=time(8, 0))
        segunda = Sesion.objects.create(fecha=date(2026, 9, 17), hora=time(17, 0))
        Asistencia.objects.create(
            sesion=primera, cliente_plan=self.mensualidad, estado=Asistencia.Estado.PRESENTE
        )
        response = self.client.post(reverse("asistencias:roster", kwargs={"pk": segunda.pk}), {
            "form-TOTAL_FORMS": "1", "form-INITIAL_FORMS": "1",
            "form-0-cliente_plan": str(self.mensualidad.pk),
            "form-0-estado": Asistencia.Estado.PRESENTE,
            "form-0-observaciones": "",
            "form-0-motivo_cancelacion": "",
            "form-0-fecha_aviso_cancelacion": "",
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ya tiene una asistencia registrada ese día")
        self.assertFalse(Asistencia.objects.filter(sesion=segunda).exists())

    def test_segunda_sesion_no_muestra_a_quien_ya_asistio_antes_ese_dia(self):
        primera = Sesion.objects.create(fecha=date(2026, 9, 18), hora=time(8, 0))
        segunda = Sesion.objects.create(fecha=date(2026, 9, 18), hora=time(17, 0))
        Asistencia.objects.create(
            sesion=primera, cliente_plan=self.mensualidad, estado=Asistencia.Estado.PRESENTE
        )

        response = self.client.get(reverse("asistencias:roster", kwargs={"pk": segunda.pk}))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_alumnas"], 0)
        self.assertNotContains(response, "Rosa Sesión")

    def test_asistir_en_bloque_posterior_invalida_recuperacion_del_bloque_cancelado(self):
        fecha_clase = date(2026, 9, 19)
        primera = Sesion.objects.create(fecha=fecha_clase, hora=time(8, 0))
        segunda = Sesion.objects.create(fecha=fecha_clase, hora=time(17, 0))
        self.client.post(reverse("asistencias:roster", kwargs={"pk": primera.pk}), {
            "form-TOTAL_FORMS": "1", "form-INITIAL_FORMS": "1",
            "form-0-cliente_plan": str(self.mensualidad.pk),
            "form-0-estado": Asistencia.Estado.CANCELO,
            "form-0-observaciones": "",
            "form-0-motivo_cancelacion": "Cambio al bloque de la tarde",
            "form-0-fecha_aviso_cancelacion": "2026-09-19T03:00",
        })

        response = self.client.post(reverse("asistencias:roster", kwargs={"pk": segunda.pk}), {
            "form-TOTAL_FORMS": "1", "form-INITIAL_FORMS": "1",
            "form-0-cliente_plan": str(self.mensualidad.pk),
            "form-0-estado": Asistencia.Estado.PRESENTE,
            "form-0-observaciones": "",
            "form-0-motivo_cancelacion": "",
            "form-0-fecha_aviso_cancelacion": "",
        })

        self.assertEqual(response.status_code, 302)
        origen = Asistencia.objects.get(sesion=primera, cliente_plan=self.mensualidad)
        destino = Asistencia.objects.get(sesion=segunda, cliente_plan=self.mensualidad)
        self.assertEqual(destino.estado, Asistencia.Estado.PRESENTE)
        self.assertEqual(origen.recuperacion_generada.estado, RecuperacionClase.Estado.INVALIDADA)
        self.mensualidad.refresh_from_db()
        self.assertEqual(self.mensualidad.clases_utilizadas, 1)


class HorarioEstudioTests(TestCase):
    def setUp(self):
        self.staff = get_user_model().objects.create_user(
            username="horarios-admin", email="horarios-admin@example.test",
            password="test-password-only", is_staff=True,
        )
        self.usuario = get_user_model().objects.create_user(
            username="horarios-operadora", email="horarios-user@example.test",
            password="test-password-only",
        )

    def test_configuracion_solo_esta_disponible_para_staff(self):
        url = reverse("asistencias:schedule_settings")
        self.client.force_login(self.usuario)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

        self.client.force_login(self.staff)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="matutino_inicio" value="08:00:00"')
        self.assertContains(response, 'name="vespertino_inicio" value="17:00:00"')
        self.assertContains(response, 'data-time-control', count=4)
        self.assertContains(response, 'data-time-trigger', count=4)

    def test_cambio_de_bloques_actualiza_selector_api_y_validacion(self):
        self.client.force_login(self.staff)
        response = self.client.post(reverse("asistencias:schedule_settings"), {
            "matutino_inicio": "09:00",
            "matutino_fin": "12:30",
            "vespertino_inicio": "17:30",
            "vespertino_fin": "20:30",
        })
        self.assertRedirects(response, reverse("asistencias:schedule_settings"))
        horario = HorarioEstudio.objects.get(pk=1)
        self.assertEqual(horario.matutino_inicio, time(9, 0))

        form_page = self.client.get(reverse("asistencias:create"), {"fecha": "2026-09-25"})
        self.assertContains(form_page, "Bloque matutino · 09:00 a 12:30 hrs")
        self.assertContains(form_page, 'value="09:00"')
        self.assertNotContains(form_page, 'value="08:00"')

        availability = self.client.get(
            reverse("asistencias:available_times"), {"fecha": "2026-09-25"}
        ).json()
        slots = {
            slot["value"]
            for group in availability["groups"]
            for slot in group["slots"]
        }
        self.assertIn("12:00", slots)
        self.assertIn("17:30", slots)
        self.assertNotIn("12:30", slots)
        self.assertNotIn("21:00", slots)

        with self.assertRaises(ValidationError):
            Sesion.objects.create(fecha=date(2026, 9, 25), hora=time(8, 0))
        Sesion.objects.create(fecha=date(2026, 9, 25), hora=time(9, 0))

    def test_rechaza_bloques_superpuestos_y_horas_fuera_de_intervalos(self):
        self.client.force_login(self.staff)
        response = self.client.post(reverse("asistencias:schedule_settings"), {
            "matutino_inicio": "08:00",
            "matutino_fin": "18:00",
            "vespertino_inicio": "17:00",
            "vespertino_fin": "21:00",
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Los dos bloques no pueden superponerse.")
        self.assertEqual(HorarioEstudio.objects.get(pk=1).matutino_fin, time(12, 0))

        response = self.client.post(reverse("asistencias:schedule_settings"), {
            "matutino_inicio": "08:15",
            "matutino_fin": "12:00",
            "vespertino_inicio": "17:00",
            "vespertino_fin": "21:00",
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Usa intervalos de 30 minutos")
