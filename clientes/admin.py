from django.contrib import admin

from .models import Cliente


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = (
        "apellidos",
        "nombres",
        "rut",
        "telefono",
        "estado",
        "fecha_incorporacion",
    )
    list_filter = ("estado", "fecha_incorporacion")
    search_fields = ("nombres", "apellidos", "rut", "email", "telefono")
    date_hierarchy = "fecha_incorporacion"
    ordering = ("apellidos", "nombres")
    readonly_fields = ("created_at", "updated_at")
