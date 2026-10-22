import calendar
import csv
from datetime import date

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Prefetch, Q, Sum
from django.db.models.functions import Coalesce
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View
from django.views.generic import CreateView, FormView, ListView, UpdateView

from clientes.models import Cliente
from mensualidades.models import ClientePlan

from .forms import PagoForm, ProgramarCuotasForm
from .models import Cuota, Pago


def vencimiento_mensual(fecha_inicial, indice):
    indice_mes = fecha_inicial.month - 1 + indice
    anio = fecha_inicial.year + indice_mes // 12
    mes = indice_mes % 12 + 1
    dia = min(fecha_inicial.day, calendar.monthrange(anio, mes)[1])
    return date(anio, mes, dia)


class CuotasListView(LoginRequiredMixin, ListView):
    model = ClientePlan
    template_name = "pagos/cuotas_list.html"
    context_object_name = "planes_cuotas"
    paginate_by = 12

    def get_queryset(self):
        cuotas = Cuota.objects.annotate(
            recibido_anotado=Sum(
                "pagos__monto_clp",
                filter=Q(pagos__estado_pago__in=[Pago.EstadoPago.PAGADO, Pago.EstadoPago.PARCIAL]),
            )
        ).order_by("numero")
        queryset = ClientePlan.objects.filter(cuotas__isnull=False).select_related(
            "cliente", "plan"
        ).prefetch_related(Prefetch("cuotas", queryset=cuotas)).distinct()
        search = self.request.GET.get("q", "").strip()
        if search:
            queryset = queryset.filter(
                Q(cliente__nombres__icontains=search)
                | Q(cliente__apellidos__icontains=search)
                | Q(cliente__rut__icontains=search.replace(".", "").replace(" ", ""))
                | Q(plan__nombre__icontains=search)
            )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Cuotas"
        for mensualidad in context["planes_cuotas"]:
            cuotas = list(mensualidad.cuotas.all())
            mensualidad.cuotas_programadas = cuotas
            mensualidad.cuotas_pendientes = sum(cuota.saldo_pendiente_clp > 0 for cuota in cuotas)
            mensualidad.saldo_cuotas_clp = sum(cuota.saldo_pendiente_clp for cuota in cuotas)
        context["search_query"] = self.request.GET.get("q", "").strip()
        context["return_to_url"] = self.request.get_full_path()
        return context


class CuotasCreateView(LoginRequiredMixin, FormView):
    template_name = "pagos/cuotas_form.html"
    form_class = ProgramarCuotasForm
    extra_context = {"page_title": "Programar cuotas"}

    def get_initial(self):
        initial = super().get_initial()
        mensualidad_id = self.request.GET.get("cliente_plan")
        if mensualidad_id and mensualidad_id.isdecimal() and ClientePlan.objects.filter(pk=mensualidad_id).exists():
            initial["cliente_plan"] = mensualidad_id
        return initial

    def form_valid(self, form):
        mensualidad_id = form.cleaned_data["cliente_plan"].pk
        cantidad = form.cleaned_data["cantidad"]
        fecha_inicial = form.cleaned_data["fecha_primera_cuota"]
        with transaction.atomic():
            mensualidad = ClientePlan.objects.select_for_update().get(pk=mensualidad_id)
            if mensualidad.cuotas.exists():
                form.add_error("cliente_plan", "Esta mensualidad ya tiene cuotas programadas.")
                return self.form_invalid(form)
            if mensualidad.pagos.filter(estado_pago=Pago.EstadoPago.PENDIENTE).exists():
                form.add_error("cliente_plan", "Resuelve o anula los movimientos pendientes antes de programar cuotas.")
                return self.form_invalid(form)
            saldo = mensualidad.saldo_pendiente_clp
            if saldo < cantidad:
                form.add_error("cantidad", "El saldo debe permitir al menos $1 CLP por cuota.")
                return self.form_invalid(form)
            monto_base, resto = divmod(saldo, cantidad)
            for indice in range(cantidad):
                Cuota.objects.create(
                    cliente_plan=mensualidad,
                    numero=indice + 1,
                    monto_clp=monto_base + (resto if indice == cantidad - 1 else 0),
                    fecha_vencimiento=vencimiento_mensual(fecha_inicial, indice),
                )
        messages.success(self.request, f"Se programaron {cantidad} cuotas para {mensualidad.cliente}.")
        return redirect("pagos:cuotas")


def filtered_payments(request):
    queryset = Pago.objects.select_related(
        "cliente",
        "cuota",
        "cliente_plan__cliente",
        "cliente_plan__plan",
    )
    search = request.GET.get("q", "").strip()
    estado = request.GET.get("estado", "").strip()
    metodo = request.GET.get("metodo", "").strip()
    tipo = request.GET.get("tipo", "").strip()
    month = request.GET.get("mes", "").strip()
    date_from = parse_filter_date(request.GET.get("desde", ""))
    date_to = parse_filter_date(request.GET.get("hasta", ""))
    valid_date_range = not (date_from and date_to and date_from > date_to)
    if search:
        rut_search = search.replace(".", "").replace(" ", "")
        queryset = queryset.filter(
            Q(concepto__icontains=search)
            | Q(cliente__nombres__icontains=search)
            | Q(cliente__apellidos__icontains=search)
            | Q(cliente__rut__icontains=rut_search)
            | Q(cliente_plan__cliente__nombres__icontains=search)
            | Q(cliente_plan__cliente__apellidos__icontains=search)
            | Q(cliente_plan__cliente__rut__icontains=rut_search)
            | Q(cliente_plan__plan__nombre__icontains=search)
        )
    if estado in Pago.EstadoPago.values:
        queryset = queryset.filter(estado_pago=estado)
    if metodo in Pago.MetodoPago.values:
        queryset = queryset.filter(metodo_pago=metodo)
    if tipo in Pago.TipoPago.values:
        queryset = queryset.filter(tipo_pago=tipo)
    try:
        year, month_number = (int(part) for part in month.split("-", maxsplit=1))
        if 1 <= month_number <= 12 and 1 <= year <= 9999:
            queryset = queryset.filter(fecha_pago__year=year, fecha_pago__month=month_number)
    except (ValueError, TypeError):
        month = ""
    if valid_date_range and date_from:
        queryset = queryset.filter(fecha_pago__gte=date_from)
    if valid_date_range and date_to:
        queryset = queryset.filter(fecha_pago__lte=date_to)
    sort_key = request.GET.get("orden", "").strip()
    direction = request.GET.get("direccion", "").strip()
    sort_fields = {
        "fecha": ("fecha_pago", "created_at", "pk"),
        "cliente": ("_sort_client_last_name", "_sort_client_first_name", "fecha_pago", "pk"),
        "periodo": ("cliente_plan__periodo_anio", "cliente_plan__periodo_mes", "fecha_pago", "pk"),
        "concepto": ("concepto", "fecha_pago", "pk"),
        "monto": ("monto_clp", "fecha_pago", "pk"),
        "metodo": ("metodo_pago", "fecha_pago", "pk"),
        "estado": ("estado_pago", "fecha_pago", "pk"),
    }
    if sort_key in sort_fields and direction in {"asc", "desc"}:
        if sort_key == "cliente":
            queryset = queryset.annotate(
                _sort_client_last_name=Coalesce("cliente__apellidos", "cliente_plan__cliente__apellidos"),
                _sort_client_first_name=Coalesce("cliente__nombres", "cliente_plan__cliente__nombres"),
            )
        fields = sort_fields[sort_key]
        if direction == "desc":
            fields = tuple(f"-{field}" for field in fields)
        queryset = queryset.order_by(*fields)
    return queryset


def parse_filter_date(value):
    try:
        return date.fromisoformat(value) if value else None
    except (TypeError, ValueError):
        return None


def csv_safe_text(value):
    value = str(value or "")
    if value.lstrip(" \t\r\n").startswith(("=", "+", "-", "@")):
        return f"'{value}"
    return value


class PagoListView(LoginRequiredMixin, ListView):
    model = Pago
    template_name = "pagos/list.html"
    context_object_name = "pagos"
    paginate_by = 12

    def get_queryset(self):
        return filtered_payments(self.request)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        hoy = timezone.localdate()
        inicio_mes = hoy.replace(day=1)
        fin_mes = date(hoy.year + (hoy.month == 12), hoy.month % 12 + 1, 1)
        pagos_activos = Q(
            estado_pago__in=[
                Pago.EstadoPago.PAGADO,
                Pago.EstadoPago.PARCIAL,
                Pago.EstadoPago.PENDIENTE,
            ]
        )
        resumen = Pago.objects.aggregate(
            ingresos_mes=Sum(
                "monto_clp",
                filter=Q(
                    fecha_pago__gte=inicio_mes,
                    fecha_pago__lt=fin_mes,
                    estado_pago__in=[Pago.EstadoPago.PAGADO, Pago.EstadoPago.PARCIAL],
                ),
            ),
            pendientes_count=Count("pk", filter=Q(estado_pago=Pago.EstadoPago.PENDIENTE)),
            pendientes_total=Sum(
                "monto_clp",
                filter=Q(estado_pago=Pago.EstadoPago.PENDIENTE),
            ),
            realizados_count=Count("pk", filter=Q(estado_pago=Pago.EstadoPago.PAGADO)),
            movimientos_activos=Count("pk", filter=pagos_activos),
        )
        realizados_count = resumen["realizados_count"]
        movimientos_activos = resumen["movimientos_activos"]
        context.update(
            {
                "page_title": "Pagos",
                "current_year": hoy.year,
                "search_query": self.request.GET.get("q", "").strip(),
                "selected_status": self.request.GET.get("estado", "").strip(),
                "selected_method": self.request.GET.get("metodo", "").strip(),
                "selected_type": self.request.GET.get("tipo", "").strip(),
                "selected_month": self.request.GET.get("mes", "").strip(),
                "selected_date_from": self.request.GET.get("desde", "").strip(),
                "selected_date_to": self.request.GET.get("hasta", "").strip(),
                "invalid_date_range": bool(
                    parse_filter_date(self.request.GET.get("desde", ""))
                    and parse_filter_date(self.request.GET.get("hasta", ""))
                    and parse_filter_date(self.request.GET.get("desde", ""))
                    > parse_filter_date(self.request.GET.get("hasta", ""))
                ),
                "total_pagos": self.get_queryset().count(),
                "status_choices": Pago.EstadoPago.choices,
                "method_choices": Pago.MetodoPago.choices,
                "type_choices": Pago.TipoPago.choices,
                "ingresos_mes": resumen["ingresos_mes"] or 0,
                "pagos_pendientes_count": resumen["pendientes_count"],
                "pagos_pendientes_total": resumen["pendientes_total"] or 0,
                "pagos_realizados_count": realizados_count,
                "movimientos_activos_count": movimientos_activos,
                "pagos_realizados_porcentaje": round(realizados_count * 100 / movimientos_activos) if movimientos_activos else 0,
            }
        )
        requested_sort = self.request.GET.get("orden", "").strip()
        requested_direction = self.request.GET.get("direccion", "").strip()
        valid_sort_keys = {"fecha", "cliente", "periodo", "concepto", "monto", "metodo", "estado"}
        context["payment_sort_key"] = requested_sort if requested_sort in valid_sort_keys else ""
        context["payment_sort_direction"] = requested_direction if requested_direction in {"asc", "desc"} else ""
        sort_urls = {}
        for key in valid_sort_keys:
            params = self.request.GET.copy()
            params.pop("page", None)
            if requested_sort == key and requested_direction in {"asc", "desc"}:
                next_direction = "asc" if requested_direction == "desc" else "desc"
            else:
                next_direction = "desc" if key in {"fecha", "monto"} else "asc"
            params["orden"] = key
            params["direccion"] = next_direction
            sort_urls[key] = params.urlencode()
        context["payment_sort_urls"] = sort_urls
        mobile_sort_urls = {}
        for label, direction in (("recent", "desc"), ("oldest", "asc")):
            params = self.request.GET.copy()
            params.pop("page", None)
            params["orden"] = "fecha"
            params["direccion"] = direction
            mobile_sort_urls[label] = params.urlencode()
        context["payment_mobile_sort_urls"] = mobile_sort_urls
        pagination_params = self.request.GET.copy()
        pagination_params.pop("page", None)
        context["pagination_query"] = pagination_params.urlencode()
        return context


class PagoExportView(LoginRequiredMixin, View):
    def get(self, request):
        response = HttpResponse(content_type="text/csv; charset=utf-8-sig")
        response["Content-Disposition"] = f'attachment; filename="pagos-{timezone.localdate():%Y-%m}.csv"'
        response.write("\ufeff")
        writer = csv.writer(response)
        writer.writerow(["Cliente", "Tipo", "Período", "Cuota", "Concepto", "Monto CLP", "Método", "Fecha", "Estado"])
        for pago in filtered_payments(request).iterator():
            writer.writerow(
                [
                    csv_safe_text(pago.cliente_asociado),
                    csv_safe_text(pago.get_tipo_pago_display()),
                    csv_safe_text(pago.referencia_display),
                    pago.cuota.numero if pago.cuota_id else "",
                    csv_safe_text(pago.concepto),
                    pago.monto_clp,
                    csv_safe_text(pago.get_metodo_pago_display()),
                    pago.fecha_pago.isoformat(),
                    csv_safe_text(pago.get_estado_pago_display()),
                ]
            )
        return response


class PagoCreateView(LoginRequiredMixin, CreateView):
    model = Pago
    form_class = PagoForm
    template_name = "pagos/form.html"
    extra_context = {"page_title": "Nuevo pago", "form_title": "Registrar pago"}

    def get_initial(self):
        initial = super().get_initial()
        cuota_id = self.request.GET.get("cuota")
        cuota = (
            Cuota.objects.select_related("cliente_plan").filter(pk=cuota_id).first()
            if cuota_id and cuota_id.isdecimal() else None
        )
        if cuota and cuota.saldo_pendiente_clp:
            initial.update(
                {
                    "tipo_pago": Pago.TipoPago.MENSUALIDAD,
                    "cliente_plan": cuota.cliente_plan_id,
                    "cuota": cuota.pk,
                    "concepto": f"Cuota {cuota.numero} · {cuota.cliente_plan.periodo}",
                    "monto_clp": cuota.saldo_pendiente_clp,
                }
            )
            return initial
        mensualidad_id = self.request.GET.get("cliente_plan")
        if mensualidad_id and mensualidad_id.isdecimal() and ClientePlan.objects.filter(pk=mensualidad_id).exists():
            initial["cliente_plan"] = mensualidad_id
        tipo_pago = self.request.GET.get("tipo_pago")
        if tipo_pago == Pago.TipoPago.MATRICULA:
            initial["tipo_pago"] = tipo_pago
            initial["concepto"] = "Matrícula"
            initial["monto_clp"] = Pago.MONTO_MATRICULA_CLP
            cliente_id = self.request.GET.get("cliente")
            if cliente_id and Cliente.objects.filter(
                pk=cliente_id,
                estado=Cliente.Estado.ACTIVA,
            ).exists():
                initial["cliente"] = cliente_id
        return initial

    def get_cancel_url(self):
        candidate = self.request.POST.get("return_to") or self.request.GET.get("return_to", "")
        if (
            candidate
            and url_has_allowed_host_and_scheme(
                candidate,
                allowed_hosts={self.request.get_host()},
                require_https=self.request.is_secure(),
            )
            and candidate.split("?", 1)[0] == reverse("pagos:cuotas")
        ):
            return candidate

        cuota_id = self.request.POST.get("cuota") or self.request.GET.get("cuota", "")
        if cuota_id.isdecimal() and Cuota.objects.filter(pk=cuota_id).exists():
            return reverse("pagos:cuotas")
        return reverse("pagos:list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["cancel_url"] = self.get_cancel_url()
        context["cancel_label"] = (
            "Volver a cuotas"
            if context["cancel_url"].split("?", 1)[0] == reverse("pagos:cuotas")
            else "Volver a pagos"
        )
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f"Se registró el movimiento por ${self.object.monto_clp:,} CLP.")
        return response

    def get_success_url(self):
        return reverse("pagos:list")


class PagoUpdateView(LoginRequiredMixin, UpdateView):
    model = Pago
    form_class = PagoForm
    template_name = "pagos/form.html"
    context_object_name = "pago"
    extra_context = {"page_title": "Editar pago", "form_title": "Editar movimiento"}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["cancel_url"] = reverse("pagos:list")
        context["cancel_label"] = "Volver a pagos"
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Se actualizó el movimiento de pago.")
        return response

    def get_success_url(self):
        return reverse("pagos:list")


class PagoSetStatusView(LoginRequiredMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        pago = get_object_or_404(Pago, pk=pk)
        estado = request.POST.get("estado", "")
        if estado not in Pago.EstadoPago.values:
            return HttpResponseBadRequest("Estado de pago no válido.")

        pago.estado_pago = estado
        try:
            pago.save(update_fields=["estado_pago", "updated_at"])
        except ValidationError as error:
            messages.error(request, "; ".join(error.messages))
            return redirect("pagos:list")
        messages.success(request, f"El movimiento quedó {pago.get_estado_pago_display().lower()}.")
        return redirect("pagos:list")
