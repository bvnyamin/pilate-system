from django import forms
from django.db.models import Q, Sum
from django.utils import timezone

from clientes.models import Cliente
from mensualidades.models import ClientePlan

from .models import Cuota, Pago


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


class CuotaSelect(forms.Select):
    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        instance = getattr(value, "instance", None)
        if instance is not None:
            option["attrs"]["data-plan-id"] = instance.cliente_plan_id
            option["attrs"]["data-saldo-cuota"] = instance.saldo_pendiente_clp
        return option


class ProgramarCuotasForm(forms.Form):
    cliente_plan = forms.ModelChoiceField(
        label="Mensualidad",
        queryset=ClientePlan.objects.none(),
        widget=ClientePlanSelect(attrs={"class": "form-select"}),
    )
    cantidad = forms.IntegerField(
        label="Cantidad de cuotas",
        min_value=2,
        max_value=12,
        widget=forms.NumberInput(attrs={"class": "form-control", "min": 2, "max": 12, "inputmode": "numeric"}),
    )
    fecha_primera_cuota = forms.DateField(
        label="Primer vencimiento",
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"class": "form-control", "type": "date"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["cliente_plan"].queryset = ClientePlan.objects.select_related(
            "cliente", "plan"
        ).annotate(
            total_pagado_form_preview=Sum(
                "pagos__monto_clp",
                filter=Q(pagos__estado_pago__in=[Pago.EstadoPago.PAGADO, Pago.EstadoPago.PARCIAL]),
            )
        ).order_by("-periodo_anio", "-periodo_mes", "cliente__apellidos")
        if not self.is_bound:
            self.initial.setdefault("fecha_primera_cuota", timezone.localdate())

    def clean(self):
        cleaned = super().clean()
        mensualidad = cleaned.get("cliente_plan")
        cantidad = cleaned.get("cantidad")
        primera_fecha = cleaned.get("fecha_primera_cuota")
        if primera_fecha and cantidad and primera_fecha.year == 9999 and primera_fecha.month + cantidad - 1 > 12:
            self.add_error("fecha_primera_cuota", "El último vencimiento excedería el año 9999.")
        if not mensualidad:
            return cleaned
        if mensualidad.cuotas.exists():
            self.add_error("cliente_plan", "Esta mensualidad ya tiene cuotas programadas.")
        if mensualidad.pagos.filter(estado_pago=Pago.EstadoPago.PENDIENTE).exists():
            self.add_error(
                "cliente_plan",
                "Resuelve o anula los movimientos pendientes antes de programar cuotas.",
            )
        saldo = mensualidad.saldo_pendiente_clp
        if saldo == 0:
            self.add_error("cliente_plan", "Esta mensualidad ya está pagada.")
        elif cantidad and cantidad > saldo:
            self.add_error("cantidad", "Cada cuota debe ser de al menos $1 CLP.")
        return cleaned


class PagoForm(forms.ModelForm):
    class Meta:
        model = Pago
        fields = (
            "tipo_pago",
            "cliente_plan",
            "cuota",
            "cliente",
            "concepto",
            "monto_clp",
            "metodo_pago",
            "fecha_pago",
            "estado_pago",
            "observaciones",
        )
        widgets = {
            "tipo_pago": forms.Select(attrs={"data-payment-field": "tipo"}),
            "cliente_plan": ClientePlanSelect(attrs={"data-payment-field": "mensualidad"}),
            "cuota": CuotaSelect(attrs={"data-payment-field": "cuota"}),
            "cliente": forms.Select(attrs={"data-payment-field": "cliente"}),
            "concepto": forms.TextInput(attrs={"placeholder": "Ej. Mensualidad octubre"}),
            "monto_clp": forms.NumberInput(attrs={"min": 1, "step": 1, "inputmode": "numeric", "placeholder": "Ej. 53820"}),
            "metodo_pago": forms.Select(),
            "fecha_pago": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
            "estado_pago": forms.Select(),
            "observaciones": forms.Textarea(attrs={"rows": 3, "placeholder": "Referencia de transferencia u otra información"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        tipo_seleccionado = (
            self.data.get(self.add_prefix("tipo_pago"))
            if self.is_bound
            else self.initial.get(
                "tipo_pago",
                self.instance.tipo_pago if self.instance.pk else Pago.TipoPago.MENSUALIDAD,
            )
        )
        clientes = Cliente.objects.filter(estado=Cliente.Estado.ACTIVA)
        if self.instance.pk and self.instance.cliente_id:
            clientes = clientes | Cliente.objects.filter(pk=self.instance.cliente_id)
        self.fields["cliente"].queryset = clientes.order_by("apellidos", "nombres")
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
        self.fields["cuota"].queryset = Cuota.objects.select_related(
            "cliente_plan__cliente", "cliente_plan__plan"
        ).annotate(
            recibido_anotado=Sum(
                "pagos__monto_clp",
                filter=Q(pagos__estado_pago__in=[Pago.EstadoPago.PAGADO, Pago.EstadoPago.PARCIAL]),
            )
        ).order_by("-cliente_plan__periodo_anio", "-cliente_plan__periodo_mes", "cliente_plan_id", "numero")
        self.fields["cuota"].label_from_instance = (
            lambda cuota: f"Cuota {cuota.numero} · falta ${cuota.saldo_pendiente_clp:,}".replace(",", ".")
        )
        self.fields["cuota"].help_text = "Si esta mensualidad está en cuotas, elige la cuota que estás cobrando."
        if tipo_seleccionado == Pago.TipoPago.MATRICULA:
            self.fields["estado_pago"].choices = [
                choice
                for choice in Pago.EstadoPago.choices
                if choice[0] != Pago.EstadoPago.PARCIAL
            ]
            if not self.is_bound:
                self.initial.setdefault("concepto", "Matrícula")
                self.initial.setdefault("monto_clp", Pago.MONTO_MATRICULA_CLP)
        if self.instance and self.instance.pk:
            if self.instance.cliente_plan_id:
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
        self.fields["concepto"].required = False
        self.fields["monto_clp"].required = False
        self.fields["monto_clp"].help_text = "Monto de este movimiento, no el total de la mensualidad."

    def clean(self):
        cleaned_data = super().clean()
        tipo_pago = cleaned_data.get("tipo_pago")
        if tipo_pago == Pago.TipoPago.MATRICULA:
            cliente = cleaned_data.get("cliente")
            cleaned_data["cliente_plan"] = None
            cleaned_data["cuota"] = None
            cleaned_data["concepto"] = "Matrícula"
            cleaned_data["monto_clp"] = Pago.MONTO_MATRICULA_CLP
            if not cliente:
                self.add_error("cliente", "Selecciona la clienta a quien corresponde la matrícula.")
            elif Pago.objects.filter(
                tipo_pago=Pago.TipoPago.MATRICULA,
                cliente=cliente,
            ).exclude(pk=self.instance.pk).exists():
                self.add_error(
                    "cliente",
                    "Esta clienta ya tiene un registro de matrícula. Edita ese movimiento.",
                )
        elif tipo_pago == Pago.TipoPago.MENSUALIDAD:
            cleaned_data["cliente"] = None
            if not cleaned_data.get("cliente_plan"):
                self.add_error("cliente_plan", "Selecciona la mensualidad asociada al pago.")
            if not cleaned_data.get("concepto"):
                self.add_error("concepto", "Ingresa el concepto de este pago.")
            if not cleaned_data.get("monto_clp"):
                self.add_error("monto_clp", "Ingresa el monto de este pago.")
            mensualidad = cleaned_data.get("cliente_plan")
            cuota = cleaned_data.get("cuota")
            if mensualidad and mensualidad.cuotas.exists() and not cuota and not self.instance.pk:
                self.add_error("cuota", "Selecciona la cuota que corresponde a este pago.")
            if mensualidad and cuota and cuota.cliente_plan_id != mensualidad.pk:
                self.add_error("cuota", "La cuota debe corresponder a la mensualidad seleccionada.")
        return cleaned_data
