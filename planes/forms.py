from django import forms

from .models import Plan


class PlanForm(forms.ModelForm):
    class Meta:
        model = Plan
        fields = ("nombre", "clases_por_mes", "precio_lista_clp", "descripcion", "estado")
        widgets = {
            "nombre": forms.TextInput(attrs={"placeholder": "Ej. FLUYE"}),
            "clases_por_mes": forms.NumberInput(attrs={"min": 1, "step": 1}),
            "precio_lista_clp": forms.TextInput(attrs={"inputmode": "numeric", "data-input-format": "clp", "autocomplete": "off"}),
            "descripcion": forms.Textarea(attrs={"rows": 4, "placeholder": "Describe brevemente a quién está dirigido este plan"}),
            "estado": forms.Select(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"
        self.fields["estado"].widget.attrs["class"] = "form-select"
        self.fields["descripcion"].required = False
        self.fields["precio_lista_clp"].help_text = "Ingresa pesos chilenos; los puntos se agregan automáticamente."
