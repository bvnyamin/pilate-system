from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, UpdateView
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache

from asistencias.models import Asistencia
from mensualidades.models import ClientePlan
from pagos.models import Pago

from .forms import ClienteForm
from .models import Cliente, SolicitudAltaCliente
from .medical_views import puede_importar, puede_ver


class ClienteListView(LoginRequiredMixin, ListView):
    model = Cliente
    template_name = "clientes/list.html"
    context_object_name = "clientes"
    paginate_by = 12

    def get_queryset(self):
        queryset = Cliente.objects.all()
        search = self.request.GET.get("q", "").strip()
        estado = self.request.GET.get("estado", "").strip()

        if search:
            rut_search = search.replace(".", "").replace(" ", "")
            queryset = queryset.filter(
                Q(nombres__icontains=search)
                | Q(apellidos__icontains=search)
                | Q(rut__icontains=rut_search)
                | Q(email__icontains=search)
                | Q(telefono__icontains=search)
            )
        if estado in Cliente.Estado.values:
            queryset = queryset.filter(estado=estado)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "page_title": "Clientes",
                "search_query": self.request.GET.get("q", "").strip(),
                "selected_status": self.request.GET.get("estado", "").strip(),
                "total_clientes": self.get_queryset().count(),
                "puede_importar_fichas": puede_importar(self.request.user),
                "solicitudes_altas_pendientes": SolicitudAltaCliente.objects.filter(
                    estado=SolicitudAltaCliente.Estado.PENDIENTE
                ).count() if puede_importar(self.request.user) else 0,
            }
        )
        return context


class ClienteCreateView(LoginRequiredMixin, CreateView):
    model = Cliente
    form_class = ClienteForm
    template_name = "clientes/form.html"
    extra_context = {"page_title": "Nueva clienta", "form_title": "Agregar clienta"}

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f"Se agregó a {self.object}.")
        return response

    def get_success_url(self):
        return reverse("clientes:detail", kwargs={"pk": self.object.pk})


class ClienteUpdateView(LoginRequiredMixin, UpdateView):
    model = Cliente
    form_class = ClienteForm
    template_name = "clientes/form.html"
    extra_context = {"page_title": "Editar clienta", "form_title": "Editar datos de clienta"}

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f"Se actualizaron los datos de {self.object}.")
        return response

    def get_success_url(self):
        return reverse("clientes:detail", kwargs={"pk": self.object.pk})


@method_decorator(never_cache, name="dispatch")
class ClienteDetailView(LoginRequiredMixin, DetailView):
    model = Cliente
    template_name = "clientes/detail.html"
    context_object_name = "cliente"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = self.object.nombres
        context["puede_ver_fichas"] = puede_ver(self.request.user)
        context["puede_importar_fichas"] = puede_importar(self.request.user)
        if context["puede_ver_fichas"]:
            context["fichas_medicas"] = self.object.fichas_medicas.select_related("importacion", "asociada_por")
        context["planes_cliente"] = ClientePlan.objects.filter(
            cliente=self.object
        ).select_related("plan")
        context["pagos_cliente"] = Pago.objects.filter(
            Q(cliente=self.object) | Q(cliente_plan__cliente=self.object)
        ).select_related("cliente", "cliente_plan__plan")
        context["matricula_cliente"] = Pago.objects.filter(
            cliente=self.object,
            tipo_pago=Pago.TipoPago.MATRICULA,
        ).first()
        context["asistencias_cliente"] = Asistencia.objects.filter(
            cliente_plan__cliente=self.object
        ).select_related("sesion", "cliente_plan__plan")
        return context


class ClienteSetStatusView(LoginRequiredMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        cliente = get_object_or_404(Cliente, pk=pk)
        estado = request.POST.get("estado", "")
        if estado not in Cliente.Estado.values:
            return HttpResponseBadRequest("Estado de cliente no válido.")

        cliente.estado = estado
        cliente.save(update_fields=["estado", "updated_at"])
        estado_label = cliente.get_estado_display().lower()
        messages.success(request, f"{cliente} quedó {estado_label}.")
        return redirect(reverse("clientes:detail", kwargs={"pk": cliente.pk}))
