from datetime import date

from django import forms
from django.db.models import Q
from django.utils import timezone

from clientes.models import Cliente
from planes.models import Plan

from .models import ClientePlan, calcular_fecha_fin_mensual


class PlanPriceSelect(forms.Select):
    precio_acordado = None

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        instance = getattr(value, "instance", None)
        if instance is not None:
            option["attrs"]["data-precio-clp"] = instance.precio_lista_clp
            if self.precio_acordado and instance.pk == self.precio_acordado[0]:
                option["attrs"]["data-precio-clp"] = self.precio_acordado[1]
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
            "fecha_inicio": forms.DateInput(
                format="%Y-%m-%d",
                attrs={"type": "date", "data-cliente-plan-field": "fecha-inicio"},
            ),
            "fecha_fin": forms.DateInput(
                format="%Y-%m-%d",
                attrs={
                    "type": "date",
                    "readonly": True,
                    "aria-describedby": "fecha-fin-help",
                }
            ),
            "descuento_porcentaje": forms.NumberInput(attrs={"min": 0, "max": 100, "step": "0.01", "data-cliente-plan-field": "descuento"}),
            "estado": forms.Select(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["cliente"].queryset = Cliente.objects.filter(estado=Cliente.Estado.ACTIVA).order_by("apellidos", "nombres")
        self.fields["fecha_fin"].required = False
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
            self.initial.setdefault("periodo_mes", today.month)
            self.initial.setdefault("periodo_anio", today.year)
            self.initial.setdefault("fecha_inicio", date(today.year, today.month, 1))
            fecha_inicio_inicial = self.fields["fecha_inicio"].to_python(
                self.initial["fecha_inicio"]
            )
            self.initial.setdefault(
                "fecha_fin",
                calcular_fecha_fin_mensual(fecha_inicio_inicial),
            )

        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"
        self.fields["estado"].widget.attrs["class"] = "form-select"
        self.fields["descuento_porcentaje"].widget.attrs["inputmode"] = "decimal"
        self.fields["plan"].help_text = "El precio base se toma del catálogo y queda guardado para este período."
        if self.instance.pk:
            self.fields["plan"].widget.precio_acordado = (self.instance.plan_id, self.instance.precio_base_clp)

    def clean(self):
        cleaned_data = super().clean()
        fecha_inicio = cleaned_data.get("fecha_inicio")
        if fecha_inicio:
            fecha_inicio_cambio = not self.instance.pk or fecha_inicio != self.instance.fecha_inicio
            if fecha_inicio_cambio:
                cleaned_data["fecha_fin"] = calcular_fecha_fin_mensual(fecha_inicio)
            elif not cleaned_data.get("fecha_fin"):
                cleaned_data["fecha_fin"] = self.instance.fecha_fin
        return cleaned_data
