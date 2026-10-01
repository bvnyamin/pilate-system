from datetime import date, time

from django import forms
from django.forms import formset_factory
from django.urls import reverse

from mensualidades.models import ClientePlan

from .models import Asistencia, HorarioEstudio, Sesion
from .horarios import horas_inicio_permitidas, periodos_clases


class SesionForm(forms.ModelForm):
    hora = forms.TypedChoiceField(
        choices=(),
        coerce=time.fromisoformat,
        empty_value=None,
        label="Hora de inicio",
    )

    class Meta:
        model = Sesion
        fields = ["fecha", "hora", "nombre", "observaciones"]
        widgets = {
            "fecha": forms.DateInput(attrs={"type": "date", "data-session-date": "true"}),
            "hora": forms.Select(attrs={"data-session-time": "true"}),
            "observaciones": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["fecha"].widget.attrs["data-available-times-url"] = reverse(
            "asistencias:available_times"
        )
        selected_date = self.data.get("fecha") if self.is_bound else self.initial.get("fecha")
        if not selected_date and self.instance and self.instance.pk:
            selected_date = self.instance.fecha
        if isinstance(selected_date, date):
            selected_date = selected_date.isoformat()
        try:
            selected_date = date.fromisoformat(str(selected_date)) if selected_date else None
        except ValueError:
            selected_date = None
        occupied = set()
        if selected_date:
            occupied = set(
                Sesion.objects.filter(fecha=selected_date)
                .exclude(pk=self.instance.pk)
                .values_list("hora", flat=True)
            )
        time_choices = []
        self.horarios_grupos = []
        allowed = set(horas_inicio_permitidas())
        for label, start, end in periodos_clases():
            slots = [
                {
                    "value": hour.isoformat(timespec="minutes"),
                    "label": f"{hour:%H:%M} hrs",
                    "available": hour not in occupied,
                }
                for hour in sorted(allowed)
                if start <= hour < end
            ]
            self.horarios_grupos.append({"label": label, "slots": slots})
            time_choices.append((label, [(slot["value"], slot["label"]) for slot in slots]))
        self.fields["hora"].choices = time_choices
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"

    def clean_hora(self):
        hora = self.cleaned_data["hora"]
        fecha = self.cleaned_data.get("fecha")
        if fecha and Sesion.objects.filter(fecha=fecha, hora=hora).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Ese horario ya está ocupado para la fecha seleccionada.")
        return hora


class HorarioEstudioForm(forms.ModelForm):
    class Meta:
        model = HorarioEstudio
        fields = [
            "matutino_inicio", "matutino_fin",
            "vespertino_inicio", "vespertino_fin",
        ]
        widgets = {
            "matutino_inicio": forms.TimeInput(attrs={"type": "time", "step": 1800, "class": "form-control attendance-time-native-field", "data-time-input": ""}),
            "matutino_fin": forms.TimeInput(attrs={"type": "time", "step": 1800, "class": "form-control attendance-time-native-field", "data-time-input": ""}),
            "vespertino_inicio": forms.TimeInput(attrs={"type": "time", "step": 1800, "class": "form-control attendance-time-native-field", "data-time-input": ""}),
            "vespertino_fin": forms.TimeInput(attrs={"type": "time", "step": 1800, "class": "form-control attendance-time-native-field", "data-time-input": ""}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in ("matutino_inicio", "vespertino_inicio"):
            self.fields[field_name].label = "Desde"
        for field_name in ("matutino_fin", "vespertino_fin"):
            self.fields[field_name].label = "Hasta"
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control attendance-time-native-field"


class AsistenciaRowForm(forms.Form):
    cliente_plan = forms.ModelChoiceField(
        queryset=ClientePlan.objects.none(),
        widget=forms.HiddenInput,
    )
    estado = forms.ChoiceField(choices=Asistencia.Estado.choices)
    observaciones = forms.CharField(required=False, widget=forms.TextInput())
    motivo_cancelacion = forms.CharField(required=False, widget=forms.TextInput())
    fecha_aviso_cancelacion = forms.DateTimeField(
        required=False,
        input_formats=["%Y-%m-%dT%H:%M"],
        widget=forms.DateTimeInput(format="%Y-%m-%dT%H:%M", attrs={"type": "datetime-local"}),
    )

    def __init__(self, *args, cliente_planes=None, sesion=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.sesion = sesion
        if cliente_planes is not None:
            self.fields["cliente_plan"].queryset = ClientePlan.objects.filter(
                pk__in=[subscription.pk for subscription in cliente_planes]
            )
        self.fields["estado"].widget.attrs.update({"class": "form-select attendance-state-select"})
        self.fields["observaciones"].widget.attrs.update({
            "class": "form-control attendance-note-input",
            "placeholder": "Nota opcional",
        })
        self.fields["motivo_cancelacion"].widget.attrs.update({
            "class": "form-control attendance-cancel-reason",
            "placeholder": "Motivo informado por la clienta",
        })
        self.fields["fecha_aviso_cancelacion"].widget.attrs.update({
            "class": "form-control attendance-cancel-notice",
        })

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("estado") == Asistencia.Estado.CANCELO:
            if not cleaned.get("motivo_cancelacion", "").strip():
                self.add_error("motivo_cancelacion", "Indica el motivo de la cancelación.")
            if not cleaned.get("fecha_aviso_cancelacion"):
                self.add_error("fecha_aviso_cancelacion", "Indica cuándo avisó la clienta.")
        return cleaned


AsistenciaFormSet = formset_factory(AsistenciaRowForm, extra=0)
