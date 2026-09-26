from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views import View
from django.views.generic import CreateView, ListView, UpdateView

from .forms import PlanForm
from .models import Plan


class PlanListView(LoginRequiredMixin, ListView):
    model = Plan
    template_name = "planes/list.html"
    context_object_name = "planes"
    paginate_by = 12

    def get_queryset(self):
        queryset = Plan.objects.all()
        search = self.request.GET.get("q", "").strip()
        estado = self.request.GET.get("estado", "").strip()
        if search:
            queryset = queryset.filter(Q(nombre__icontains=search) | Q(descripcion__icontains=search))
        if estado in Plan.Estado.values:
            queryset = queryset.filter(estado=estado)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "page_title": "Planes",
                "search_query": self.request.GET.get("q", "").strip(),
                "selected_status": self.request.GET.get("estado", "").strip(),
                "total_planes": self.get_queryset().count(),
            }
        )
        return context


class PlanCreateView(LoginRequiredMixin, CreateView):
    model = Plan
    form_class = PlanForm
    template_name = "planes/form.html"
    extra_context = {"page_title": "Nuevo plan", "form_title": "Crear plan"}

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f"Se creó el plan {self.object.nombre}.")
        return response

    def get_success_url(self):
        return reverse("planes:list")


class PlanUpdateView(LoginRequiredMixin, UpdateView):
    model = Plan
    form_class = PlanForm
    template_name = "planes/form.html"
    context_object_name = "plan"
    extra_context = {"page_title": "Editar plan", "form_title": "Editar plan"}

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f"Se actualizaron los datos de {self.object.nombre}.")
        return response

    def get_success_url(self):
        return reverse("planes:list")


class PlanSetStatusView(LoginRequiredMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        plan = get_object_or_404(Plan, pk=pk)
        estado = request.POST.get("estado", "")
        if estado not in Plan.Estado.values:
            return HttpResponseBadRequest("Estado de plan no válido.")

        plan.estado = estado
        plan.save(update_fields=["estado", "updated_at"])
        messages.success(request, f"El plan {plan.nombre} quedó {plan.get_estado_display().lower()}.")
        return redirect("planes:list")
