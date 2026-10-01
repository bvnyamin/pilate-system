from django import forms

from .models import Gasto


class GastoForm(forms.ModelForm):
    class Meta:
        model = Gasto
        fields = ["categoria", "descripcion", "monto_clp", "fecha", "observaciones"]
        widgets = {
            "categoria": forms.Select(attrs={"class": "form-select"}),
            "descripcion": forms.TextInput(attrs={"class": "form-control", "maxlength": 160}),
            "monto_clp": forms.NumberInput(attrs={"class": "form-control", "min": 1, "step": 1, "inputmode": "numeric"}),
            "fecha": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "observaciones": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

    def clean_descripcion(self):
        descripcion = self.cleaned_data["descripcion"].strip()
        if not descripcion:
            raise forms.ValidationError("Ingresa una descripción para identificar el gasto.")
        return descripcion
