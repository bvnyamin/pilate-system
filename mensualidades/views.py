from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import Count, Exists, F, OuterRef, Q
from django.db.models.functions import Greatest
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views import View
from django.views.generic import CreateView, ListView, UpdateView

from asistencias.models import Asistencia
from config.pagination import ListPaginator
from pagos.models import Cuota, Pago

from .forms import ClientePlanForm
from .models import ClientePlan


def url_lista_mensualidades(request):
    filtros = request.GET.copy()
    for clave in set(filtros) - {"q", "estado", "mes", "anio", "orden", "page"}:
        del filtros[clave]
    url = reverse("mensualidades:list")
    return f"{url}?{filtros.urlencode()}" if filtros else url


class ClientePlanListView(LoginRequiredMixin, ListView):
    model = ClientePlan
    template_name = "mensualidades/list.html"
    context_object_name = "mensualidades"
    paginate_by = 20
    paginator_class = ListPaginator
    orderings = {
        "periodo": ("-periodo_anio", "-periodo_mes", "cliente__apellidos", "cliente__nombres"),
        "clienta": ("cliente__apellidos", "cliente__nombres", "-periodo_anio", "-periodo_mes"),
        "restantes": ("remaining_count", "-periodo_anio", "-periodo_mes", "cliente__apellidos"),
    }

    def get_queryset(self):
        queryset = ClientePlan.objects.select_related("cliente", "plan").annotate(
            present_count=Count(
                "asistencias",
                filter=Q(asistencias__estado__in=("presente", "ausente")),
                distinct=True,
            )
        ).annotate(
            remaining_count=Greatest(F("plan__clases_por_mes") - F("present_count"), 0),
            tiene_movimientos=(
                Exists(Pago.objects.filter(cliente_plan_id=OuterRef("pk")))
                | Exists(Cuota.objects.filter(cliente_plan_id=OuterRef("pk")))
                | Exists(Asistencia.objects.filter(cliente_plan_id=OuterRef("pk")))
            ),
        )
        orden = self.orderings.get(self.request.GET.get("orden"), self.orderings["periodo"])
        queryset = queryset.order_by(*orden, "-pk")
        search = self.request.GET.get("q", "").strip()
        estado = self.request.GET.get("estado", "").strip()
        mes = self.request.GET.get("mes", "").strip()
        anio = self.request.GET.get("anio", "").strip()
        if search:
            queryset = queryset.filter(
                Q(cliente__nombres__icontains=search)
                | Q(cliente__apellidos__icontains=search)
                | Q(cliente__rut__icontains=search.replace(".", "").replace(" ", ""))
                | Q(plan__nombre__icontains=search)
            )
        if estado in ClientePlan.Estado.values:
            queryset = queryset.filter(estado=estado)
        if mes.isdigit() and 1 <= int(mes) <= 12:
            queryset = queryset.filter(periodo_mes=int(mes))
        if anio.isdigit() and 2000 <= int(anio) <= 32767:
            queryset = queryset.filter(periodo_anio=int(anio))
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "page_title": "Mensualidades",
                "search_query": self.request.GET.get("q", "").strip(),
                "selected_status": self.request.GET.get("estado", "").strip(),
                "selected_month": self.request.GET.get("mes", "").strip(),
                "selected_year": self.request.GET.get("anio", "").strip(),
                "orden": self.request.GET.get("orden", "periodo"),
                "total_mensualidades": context["paginator"].count,
                "paginas": context["paginator"].get_elided_page_range(context["page_obj"].number, on_each_side=1),
                "estado_choices": ClientePlan.Estado.choices,
                "month_choices": ClientePlanForm.MESES,
            }
        )
        return context


class ClientePlanCreateView(LoginRequiredMixin, CreateView):
    model = ClientePlan
    form_class = ClientePlanForm
    template_name = "mensualidades/form.html"
    extra_context = {"page_title": "Nueva mensualidad", "form_title": "Asignar plan mensual"}

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f"Se asignó {self.object.plan} a {self.object.cliente} por {self.object.periodo}.")
        return response

    def get_success_url(self):
        return reverse("mensualidades:list")


class ClientePlanUpdateView(LoginRequiredMixin, UpdateView):
    model = ClientePlan
    form_class = ClientePlanForm
    template_name = "mensualidades/form.html"
    context_object_name = "mensualidad"
    extra_context = {"page_title": "Editar mensualidad", "form_title": "Editar mensualidad"}

    def get_object(self, queryset=None):
        queryset = self.get_queryset() if queryset is None else queryset
        if self.request.method == "POST":
            queryset = queryset.select_for_update()
        return super().get_object(queryset)

    def get(self, request, *args, **kwargs):
        mensualidad = self.get_object()
        if self.tiene_movimientos(mensualidad):
            return self.edicion_bloqueada()
        return super().get(request, *args, **kwargs)

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        mensualidad = self.get_object()
        if self.tiene_movimientos(mensualidad):
            return self.edicion_bloqueada()
        return super().post(request, *args, **kwargs)

    @staticmethod
    def tiene_movimientos(mensualidad):
        return mensualidad.pagos.exists() or mensualidad.cuotas.exists() or mensualidad.asistencias.exists()

    def edicion_bloqueada(self):
        messages.warning(self.request, "Esta mensualidad ya tiene movimientos registrados. Para cambiar de plan, asigna uno en la mensualidad del próximo período.")
        return redirect(url_lista_mensualidades(self.request))

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f"Se actualizó la mensualidad de {self.object.cliente} para {self.object.periodo}.")
        return response

    def get_success_url(self):
        return url_lista_mensualidades(self.request)


class ClientePlanSetStatusView(LoginRequiredMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        mensualidad = get_object_or_404(ClientePlan, pk=pk)
        estado = request.POST.get("estado", "")
        if estado not in ClientePlan.Estado.values:
            return HttpResponseBadRequest("Estado de mensualidad no válido.")

        mensualidad.estado = estado
        mensualidad.save(update_fields=["estado", "updated_at"])
        messages.success(request, f"La mensualidad de {mensualidad.cliente} quedó {mensualidad.get_estado_display().lower()}.")
        return redirect(url_lista_mensualidades(request))
