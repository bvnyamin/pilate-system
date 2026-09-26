from django.contrib import admin

from .models import Plan


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ("nombre", "clases_por_mes", "precio_lista_clp", "estado")
    list_filter = ("estado", "clases_por_mes")
    search_fields = ("nombre", "descripcion")
    ordering = ("precio_lista_clp", "nombre")
    readonly_fields = ("created_at", "updated_at")
