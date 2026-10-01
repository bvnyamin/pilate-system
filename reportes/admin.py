from django.contrib import admin

from .models import Gasto


@admin.register(Gasto)
class GastoAdmin(admin.ModelAdmin):
    list_display = ("fecha", "categoria", "descripcion", "monto_clp")
    list_filter = ("categoria", "fecha")
    search_fields = ("descripcion", "observaciones")
    date_hierarchy = "fecha"
