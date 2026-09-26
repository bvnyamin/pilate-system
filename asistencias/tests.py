from datetime import date, time

from django.core.exceptions import ValidationError
from django.test import TestCase

from asistencias.models import Asistencia, Sesion
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

    def test_rechaza_horario_duplicado(self):
        with self.assertRaises(ValidationError):
            Sesion.objects.create(fecha=self.sesion.fecha, hora=self.sesion.hora)
