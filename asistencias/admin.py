from django.contrib import admin

from .models import Asistencia, HorarioEstudio, Sesion


class AsistenciaInline(admin.TabularInline):
    model = Asistencia
    extra = 0
    autocomplete_fields = ["cliente_plan"]


@admin.register(Sesion)
class SesionAdmin(admin.ModelAdmin):
    list_display = ["fecha", "hora", "nombre", "total_asistencias"]
    list_filter = ["fecha"]
    search_fields = ["nombre"]
    date_hierarchy = "fecha"
    inlines = [AsistenciaInline]

    @admin.display(description="Alumnas")
    def total_asistencias(self, obj):
        return obj.asistencias.count()


@admin.register(Asistencia)
class AsistenciaAdmin(admin.ModelAdmin):
    list_display = ["cliente_plan", "sesion", "estado"]
    list_filter = ["estado", "sesion__fecha"]
    search_fields = ["cliente_plan__cliente__nombres", "cliente_plan__cliente__apellidos", "cliente_plan__cliente__rut"]
    autocomplete_fields = ["sesion", "cliente_plan"]


@admin.register(HorarioEstudio)
class HorarioEstudioAdmin(admin.ModelAdmin):
    fieldsets = (
        ("Bloque matutino", {"fields": ("matutino_inicio", "matutino_fin")}),
        ("Bloque vespertino", {"fields": ("vespertino_inicio", "vespertino_fin")}),
    )

    def has_add_permission(self, request):
        return not HorarioEstudio.objects.exists() and super().has_add_permission(request)

    def has_delete_permission(self, request, obj=None):
        return False
