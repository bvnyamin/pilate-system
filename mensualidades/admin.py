from django.contrib import admin

from .models import ClientePlan


@admin.register(ClientePlan)
class ClientePlanAdmin(admin.ModelAdmin):
    list_display = (
        "cliente",
        "plan",
        "periodo_anio",
        "periodo_mes",
        "precio_base_clp",
        "descuento_porcentaje",
        "precio_final_clp",
        "estado",
    )
    list_filter = ("estado", "periodo_anio", "periodo_mes", "plan")
    search_fields = ("cliente__nombres", "cliente__apellidos", "cliente__rut", "plan__nombre")
    date_hierarchy = "fecha_inicio"
    ordering = ("-periodo_anio", "-periodo_mes", "cliente__apellidos")
    readonly_fields = ("precio_final_clp", "created_at", "updated_at")
