from datetime import date

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum
from django.db.models.functions import ExtractMonth, ExtractYear
from django.shortcuts import render
from django.utils import timezone

from asistencias.models import Asistencia, Sesion
from clientes.models import Cliente
from pagos.models import Pago


MESES_CORTOS = ("Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic")


def meses_recientes(hoy, cantidad=6):
    indice_actual = hoy.year * 12 + hoy.month - 1
    meses = []
    for desplazamiento in range(cantidad - 1, -1, -1):
        indice = indice_actual - desplazamiento
        anio, mes_cero = divmod(indice, 12)
        meses.append((anio, mes_cero + 1))
    return meses


@login_required
def index(request):
    hoy = timezone.localdate()
    meses = meses_recientes(hoy)
    primer_mes = date(meses[0][0], meses[0][1], 1)
    indice_siguiente = hoy.year * 12 + hoy.month
    anio_siguiente, mes_siguiente_cero = divmod(indice_siguiente, 12)
    inicio_mes_siguiente = date(anio_siguiente, mes_siguiente_cero + 1, 1)
    estados_recibidos = [Pago.EstadoPago.PAGADO, Pago.EstadoPago.PARCIAL]

    ingresos = Pago.objects.filter(
        fecha_pago__gte=hoy.replace(day=1),
        fecha_pago__lt=inicio_mes_siguiente,
        estado_pago__in=estados_recibidos,
    ).aggregate(total=Sum("monto_clp"))["total"] or 0
    pagos_pendientes = Pago.objects.filter(estado_pago=Pago.EstadoPago.PENDIENTE)
    total_pendiente = pagos_pendientes.aggregate(total=Sum("monto_clp"))["total"] or 0

    ingresos_por_mes = {
        (fila["anio"], fila["mes"]): fila["total"]
        for fila in Pago.objects.filter(
            fecha_pago__gte=primer_mes,
            fecha_pago__lt=inicio_mes_siguiente,
            estado_pago__in=estados_recibidos,
        ).annotate(
            anio=ExtractYear("fecha_pago"),
            mes=ExtractMonth("fecha_pago"),
        ).values("anio", "mes").annotate(total=Sum("monto_clp"))
    }
    maximo_ingresos = max(ingresos_por_mes.values(), default=0)
    ingresos_mensuales = [
        {
            "label": MESES_CORTOS[mes - 1],
            "total": ingresos_por_mes.get((anio, mes), 0),
            "height": round(100 * ingresos_por_mes.get((anio, mes), 0) / maximo_ingresos) if maximo_ingresos else 0,
        }
        for anio, mes in meses
    ]

    asistencias_hoy = Asistencia.objects.filter(sesion__fecha=hoy)
    sesiones_hoy = Sesion.objects.filter(fecha=hoy).annotate(
        registradas=Count("asistencias", distinct=True),
        presentes=Count(
            "asistencias",
            filter=Q(asistencias__estado=Asistencia.Estado.PRESENTE),
            distinct=True,
        ),
    ).order_by("hora")

    context = {
        "page_title": "Dashboard",
        "fecha_hoy": hoy,
        "clientes_activas": Cliente.objects.filter(estado=Cliente.Estado.ACTIVA).count(),
        "ingresos_mes": ingresos,
        "pagos_pendientes_count": pagos_pendientes.count(),
        "pagos_pendientes_total": total_pendiente,
        "asistencias_hoy": asistencias_hoy.filter(estado=Asistencia.Estado.PRESENTE).count(),
        "registros_asistencia_hoy": asistencias_hoy.count(),
        "ingresos_mensuales": ingresos_mensuales,
        "sin_ingresos_grafico": maximo_ingresos == 0,
        "sesiones_hoy": sesiones_hoy,
        "pagos_recientes_pendientes": pagos_pendientes.select_related(
            "cliente", "cliente_plan__cliente", "cliente_plan__plan"
        ).order_by("fecha_pago", "created_at")[:5],
    }
    return render(request, "dashboard/index.html", context)
