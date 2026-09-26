from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views import View
from django.views.generic import CreateView, ListView, UpdateView

from .forms import PagoForm
from .models import Pago


class PagoListView(LoginRequiredMixin, ListView):
    model = Pago
    template_name = "pagos/list.html"
    context_object_name = "pagos"
    paginate_by = 12

    def get_queryset(self):
        queryset = Pago.objects.select_related(
            "cliente_plan__cliente",
            "cliente_plan__plan",
        )
        search = self.request.GET.get("q", "").strip()
        estado = self.request.GET.get("estado", "").strip()
        metodo = self.request.GET.get("metodo", "").strip()
        if search:
            rut_search = search.replace(".", "").replace(" ", "")
            queryset = queryset.filter(
                Q(concepto__icontains=search)
                | Q(cliente_plan__cliente__nombres__icontains=search)
                | Q(cliente_plan__cliente__apellidos__icontains=search)
                | Q(cliente_plan__cliente__rut__icontains=rut_search)
                | Q(cliente_plan__plan__nombre__icontains=search)
            )
        if estado in Pago.EstadoPago.values:
            queryset = queryset.filter(estado_pago=estado)
        if metodo in Pago.MetodoPago.values:
            queryset = queryset.filter(metodo_pago=metodo)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "page_title": "Pagos",
                "search_query": self.request.GET.get("q", "").strip(),
                "selected_status": self.request.GET.get("estado", "").strip(),
                "selected_method": self.request.GET.get("metodo", "").strip(),
                "total_pagos": self.get_queryset().count(),
                "status_choices": Pago.EstadoPago.choices,
                "method_choices": Pago.MetodoPago.choices,
            }
        )
        return context


class PagoCreateView(LoginRequiredMixin, CreateView):
    model = Pago
    form_class = PagoForm
    template_name = "pagos/form.html"
    extra_context = {"page_title": "Nuevo pago", "form_title": "Registrar pago"}

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
        pago.save(update_fields=["estado_pago", "updated_at"])
        messages.success(request, f"El movimiento quedó {pago.get_estado_pago_display().lower()}.")
        return redirect("pagos:list")
