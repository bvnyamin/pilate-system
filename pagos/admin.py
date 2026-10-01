from django.contrib import admin

from .models import Pago


@admin.register(Pago)
class PagoAdmin(admin.ModelAdmin):
    list_display = (
        "fecha_pago",
        "tipo_pago",
        "cliente_nombre",
        "mensualidad_periodo",
        "concepto",
        "monto_clp",
        "metodo_pago",
        "estado_pago",
    )
    list_filter = ("estado_pago", "metodo_pago", "fecha_pago")
    search_fields = (
        "concepto",
        "cliente__nombres",
        "cliente__apellidos",
        "cliente__rut",
        "cliente_plan__cliente__nombres",
        "cliente_plan__cliente__apellidos",
        "cliente_plan__cliente__rut",
        "cliente_plan__plan__nombre",
    )
    date_hierarchy = "fecha_pago"
    ordering = ("-fecha_pago", "-created_at")
    readonly_fields = ("created_at", "updated_at")
    actions = None

    @admin.display(description="Clienta")
    def cliente_nombre(self, pago):
        return pago.cliente_asociado

    @admin.display(description="Período")
    def mensualidad_periodo(self, pago):
        return pago.referencia_display

    def has_delete_permission(self, request, obj=None):
        return False
