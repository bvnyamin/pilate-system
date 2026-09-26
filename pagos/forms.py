from django import forms
from django.db.models import Q, Sum

from mensualidades.models import ClientePlan

from .models import Pago


class ClientePlanSelect(forms.Select):
    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        instance = getattr(value, "instance", None)
        if instance is not None:
            recibido = getattr(instance, "total_pagado_form_preview", 0) or 0
            option["attrs"].update(
                {
                    "data-precio-acordado": instance.precio_final_clp,
                    "data-total-recibido": recibido,
                    "data-saldo-pendiente": max(instance.precio_final_clp - recibido, 0),
                    "data-cliente": str(instance.cliente),
                    "data-plan-periodo": f"{instance.plan.nombre} · {instance.periodo}",
                }
            )
        return option


class PagoForm(forms.ModelForm):
    class Meta:
        model = Pago
        fields = (
            "cliente_plan",
            "concepto",
            "monto_clp",
            "metodo_pago",
            "fecha_pago",
            "estado_pago",
            "observaciones",
        )
        widgets = {
            "cliente_plan": ClientePlanSelect(attrs={"data-payment-field": "mensualidad"}),
            "concepto": forms.TextInput(attrs={"placeholder": "Ej. Mensualidad octubre"}),
            "monto_clp": forms.NumberInput(attrs={"min": 1, "step": 1, "inputmode": "numeric", "placeholder": "Ej. 53820"}),
            "metodo_pago": forms.Select(),
            "fecha_pago": forms.DateInput(attrs={"type": "date"}),
            "estado_pago": forms.Select(),
            "observaciones": forms.Textarea(attrs={"rows": 3, "placeholder": "Referencia de transferencia u otra información"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["cliente_plan"].queryset = (
            ClientePlan.objects.select_related("cliente", "plan")
            .annotate(
                total_pagado_form_preview=Sum(
                    "pagos__monto_clp",
                    filter=Q(pagos__estado_pago__in=[Pago.EstadoPago.PAGADO, Pago.EstadoPago.PARCIAL]),
                )
            )
            .order_by("-periodo_anio", "-periodo_mes", "cliente__apellidos", "cliente__nombres")
            )
        if self.instance and self.instance.pk:
            counted = self.instance.estado_pago in (Pago.EstadoPago.PAGADO, Pago.EstadoPago.PARCIAL)
            self.fields["cliente_plan"].widget.attrs.update(
                {
                    "data-current-mensualidad": self.instance.cliente_plan_id,
                    "data-current-pago-monto": self.instance.monto_clp,
                    "data-current-pago-contabilizado": str(counted).lower(),
                }
            )
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"
        self.fields["observaciones"].required = False
        self.fields["monto_clp"].help_text = "Monto de este movimiento, no el total de la mensualidad."
