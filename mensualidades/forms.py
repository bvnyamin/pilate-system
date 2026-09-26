import calendar
from datetime import date

from django import forms
from django.db.models import Q
from django.utils import timezone

from clientes.models import Cliente
from planes.models import Plan

from .models import ClientePlan


class PlanPriceSelect(forms.Select):
    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        instance = getattr(value, "instance", None)
        if instance is not None:
            option["attrs"]["data-precio-clp"] = instance.precio_lista_clp
        return option


class ClientePlanForm(forms.ModelForm):
    MESES = (
        (1, "Enero"),
        (2, "Febrero"),
        (3, "Marzo"),
        (4, "Abril"),
        (5, "Mayo"),
        (6, "Junio"),
        (7, "Julio"),
        (8, "Agosto"),
        (9, "Septiembre"),
        (10, "Octubre"),
        (11, "Noviembre"),
        (12, "Diciembre"),
    )
    periodo_mes = forms.TypedChoiceField(
        label="Mes",
        coerce=int,
        choices=MESES,
    )

    class Meta:
        model = ClientePlan
        fields = (
            "cliente",
            "plan",
            "periodo_mes",
            "periodo_anio",
            "fecha_inicio",
            "fecha_fin",
            "descuento_porcentaje",
            "estado",
        )
        widgets = {
            "cliente": forms.Select(attrs={"data-cliente-plan-field": "cliente"}),
            "plan": PlanPriceSelect(attrs={"data-cliente-plan-field": "plan"}),
            "periodo_anio": forms.NumberInput(attrs={"min": 2000, "max": 32767, "step": 1}),
            "fecha_inicio": forms.DateInput(attrs={"type": "date"}),
            "fecha_fin": forms.DateInput(attrs={"type": "date"}),
            "descuento_porcentaje": forms.NumberInput(attrs={"min": 0, "max": 100, "step": "0.01", "data-cliente-plan-field": "descuento"}),
            "estado": forms.Select(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["cliente"].queryset = Cliente.objects.filter(estado=Cliente.Estado.ACTIVA).order_by("apellidos", "nombres")
        self.fields["plan"].queryset = Plan.objects.filter(estado=Plan.Estado.ACTIVO).order_by("precio_lista_clp", "nombre")
        if self.instance and self.instance.pk:
            self.fields["cliente"].queryset = Cliente.objects.filter(
                Q(estado=Cliente.Estado.ACTIVA) | Q(pk=self.instance.cliente_id)
            ).order_by("apellidos", "nombres")
            self.fields["plan"].queryset = Plan.objects.filter(
                Q(estado=Plan.Estado.ACTIVO) | Q(pk=self.instance.plan_id)
            ).order_by("precio_lista_clp", "nombre")

        today = timezone.localdate()
        if not self.instance.pk:
            last_day = calendar.monthrange(today.year, today.month)[1]
            self.initial.setdefault("periodo_mes", today.month)
            self.initial.setdefault("periodo_anio", today.year)
            self.initial.setdefault("fecha_inicio", date(today.year, today.month, 1))
            self.initial.setdefault("fecha_fin", date(today.year, today.month, last_day))

        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"
        self.fields["estado"].widget.attrs["class"] = "form-select"
        self.fields["descuento_porcentaje"].widget.attrs["inputmode"] = "decimal"
        self.fields["plan"].help_text = "El precio base se toma del catálogo y queda guardado para este período."
