from datetime import date

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Q, Sum
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, ListView, TemplateView, UpdateView

from asistencias.models import Asistencia
from clientes.models import Cliente
from pagos.models import Pago

from .forms import GastoForm
from .models import Gasto


MESES = ("Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic")


def anio_seleccionado(request):
    valor = request.GET.get("anio", "").strip()
    actual = timezone.localdate().year
    if valor.isdecimal() and 2000 <= int(valor) <= 9999:
        return int(valor)
    return actual


class ReporteView(LoginRequiredMixin, TemplateView):
    template_name = "reportes/index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        anio = anio_seleccionado(self.request)
        meses = []
        for numero, nombre in enumerate(MESES, 1):
            inicio = date(anio, numero, 1)
            fin = date(anio + (numero == 12), numero % 12 + 1, 1)
            ingresos = Pago.objects.filter(
                fecha_pago__gte=inicio,
                fecha_pago__lt=fin,
                estado_pago__in=[Pago.EstadoPago.PAGADO, Pago.EstadoPago.PARCIAL],
            ).aggregate(total=Sum("monto_clp"))["total"] or 0
            gastos = Gasto.objects.filter(fecha__gte=inicio, fecha__lt=fin).aggregate(
                total=Sum("monto_clp")
            )["total"] or 0
            meses.append({"nombre": nombre, "ingresos": ingresos, "gastos": gastos, "balance": ingresos - gastos})

        total_ingresos = sum(mes["ingresos"] for mes in meses)
        total_gastos = sum(mes["gastos"] for mes in meses)
        maximo = max((max(mes["ingresos"], mes["gastos"]) for mes in meses), default=0)
        for mes in meses:
            mes["ingresos_pct"] = round(mes["ingresos"] * 100 / maximo) if maximo else 0
            mes["gastos_pct"] = round(mes["gastos"] * 100 / maximo) if maximo else 0

        top_clientas = (
            Cliente.objects.annotate(
                asistencias_contadas=Count(
                    "contrataciones__asistencias",
                    filter=Q(
                        contrataciones__asistencias__sesion__fecha__year=anio,
                        contrataciones__asistencias__estado__in=[Asistencia.Estado.PRESENTE, Asistencia.Estado.RECUPERACION],
                    ),
                    distinct=True,
                )
            )
            .filter(asistencias_contadas__gt=0)
            .order_by("-asistencias_contadas", "apellidos", "nombres")[:5]
        )
        top_gastos = list(
            Gasto.objects.filter(fecha__year=anio)
            .values("categoria")
            .annotate(total=Sum("monto_clp"), cantidad=Count("pk"))
            .order_by("-total")
        )
        etiquetas_gasto = dict(Gasto.Categoria.choices)
        for gasto in top_gastos:
            gasto["etiqueta"] = etiquetas_gasto[gasto["categoria"]]
        clienta_antigua = Cliente.objects.order_by("fecha_incorporacion", "created_at").first()

        context.update({
            "page_title": "Reportes",
            "anio": anio,
            "anios": range(timezone.localdate().year - 4, timezone.localdate().year + 1),
            "meses": meses,
            "total_ingresos": total_ingresos,
            "total_gastos": total_gastos,
            "balance_anual": total_ingresos - total_gastos,
            "top_clientas": top_clientas,
            "top_gastos": top_gastos,
            "clienta_antigua": clienta_antigua,
            "cantidad_clientas": Cliente.objects.filter(estado=Cliente.Estado.ACTIVA).count(),
            "total_asistencias": Asistencia.objects.filter(
                sesion__fecha__year=anio,
                estado__in=[Asistencia.Estado.PRESENTE, Asistencia.Estado.RECUPERACION],
            ).count(),
            "gastos_recientes": Gasto.objects.order_by("-fecha", "-created_at")[:5],
        })
        return context


class GastoListView(LoginRequiredMixin, ListView):
    model = Gasto
    template_name = "reportes/gastos.html"
    context_object_name = "gastos"
    paginate_by = 15

    def get_queryset(self):
        queryset = Gasto.objects.all()
        anio = anio_seleccionado(self.request)
        categoria = self.request.GET.get("categoria", "").strip()
        queryset = queryset.filter(fecha__year=anio)
        if categoria in Gasto.Categoria.values:
            queryset = queryset.filter(categoria=categoria)
        self.anio = anio
        self.categoria = categoria
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            "page_title": "Gastos del estudio",
            "anio": self.anio,
            "categoria_seleccionada": self.categoria,
            "categorias": Gasto.Categoria.choices,
            "anios": range(timezone.localdate().year - 4, timezone.localdate().year + 1),
            "total_anual": self.get_queryset().aggregate(total=Sum("monto_clp"))["total"] or 0,
        })
        return context


class GastoCreateView(LoginRequiredMixin, CreateView):
    model = Gasto
    form_class = GastoForm
    template_name = "reportes/gasto_form.html"
    extra_context = {"page_title": "Registrar gasto", "form_title": "Registrar gasto del estudio"}
    success_url = reverse_lazy("reportes:gastos")

    def form_valid(self, form):
        messages.success(self.request, "El gasto quedó registrado en el seguimiento financiero.")
        return super().form_valid(form)


class GastoUpdateView(LoginRequiredMixin, UpdateView):
    model = Gasto
    form_class = GastoForm
    template_name = "reportes/gasto_form.html"
    extra_context = {"page_title": "Editar gasto", "form_title": "Editar gasto del estudio"}
    success_url = reverse_lazy("reportes:gastos")

    def form_valid(self, form):
        messages.success(self.request, "Se actualizó el registro del gasto.")
        return super().form_valid(form)
