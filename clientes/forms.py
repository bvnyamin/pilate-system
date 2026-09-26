from django import forms

from .models import Cliente


class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = (
            "nombres",
            "apellidos",
            "rut",
            "email",
            "telefono",
            "fecha_nacimiento",
            "fecha_incorporacion",
            "estado",
            "observaciones",
        )
        widgets = {
            "nombres": forms.TextInput(attrs={"placeholder": "Ej. María"}),
            "apellidos": forms.TextInput(attrs={"placeholder": "Ej. Soto Pérez"}),
            "rut": forms.TextInput(attrs={"placeholder": "12.345.678-5", "autocomplete": "off"}),
            "email": forms.EmailInput(attrs={"placeholder": "nombre@correo.cl"}),
            "telefono": forms.TextInput(attrs={"placeholder": "+56 9 1234 5678", "type": "tel"}),
            "fecha_nacimiento": forms.DateInput(attrs={"type": "date"}),
            "fecha_incorporacion": forms.DateInput(attrs={"type": "date"}),
            "estado": forms.Select(),
            "observaciones": forms.Textarea(attrs={"rows": 4, "placeholder": "Información relevante para la atención"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"
        self.fields["estado"].widget.attrs["class"] = "form-select"
        self.fields["observaciones"].required = False
