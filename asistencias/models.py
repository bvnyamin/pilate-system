from django.core.exceptions import ValidationError
from django.db import models

from mensualidades.models import ClientePlan


class Sesion(models.Model):
    fecha = models.DateField("fecha")
    hora = models.TimeField("hora")
    nombre = models.CharField("nombre", max_length=100, default="Clase de Pilates")
    observaciones = models.TextField("observaciones", blank=True)
    created_at = models.DateTimeField("creada", auto_now_add=True)
    updated_at = models.DateTimeField("actualizada", auto_now=True)

    class Meta:
        ordering = ["-fecha", "-hora"]
        verbose_name = "sesión"
        verbose_name_plural = "sesiones"
        constraints = [
            models.UniqueConstraint(fields=["fecha", "hora"], name="sesion_fecha_hora_uniq"),
        ]

    def clean(self):
        super().clean()
        if self.nombre:
            self.nombre = self.nombre.strip()
            if not self.nombre:
                raise ValidationError({"nombre": "El nombre de la sesión no puede quedar vacío."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.nombre} · {self.fecha:%d/%m/%Y} {self.hora:%H:%M}"


class Asistencia(models.Model):
    class Estado(models.TextChoices):
        PRESENTE = "presente", "Presente"
        AUSENTE = "ausente", "Ausente"
        CANCELO = "cancelo", "Canceló"

    sesion = models.ForeignKey(
        Sesion,
        on_delete=models.PROTECT,
        related_name="asistencias",
        verbose_name="sesión",
    )
    cliente_plan = models.ForeignKey(
        ClientePlan,
        on_delete=models.PROTECT,
        related_name="asistencias",
        verbose_name="mensualidad",
    )
    estado = models.CharField(
        "estado",
        max_length=10,
        choices=Estado.choices,
        default=Estado.PRESENTE,
        db_index=True,
    )
    observaciones = models.TextField("observaciones", blank=True)
    created_at = models.DateTimeField("creada", auto_now_add=True)
    updated_at = models.DateTimeField("actualizada", auto_now=True)

    class Meta:
        ordering = ["cliente_plan__cliente__apellidos", "cliente_plan__cliente__nombres"]
        verbose_name = "asistencia"
        verbose_name_plural = "asistencias"
        constraints = [
            models.UniqueConstraint(
                fields=["sesion", "cliente_plan"],
                name="asistencia_sesion_cliente_plan_uniq",
            ),
        ]
        indexes = [models.Index(fields=["estado", "sesion"], name="asist_estado_sesion_idx")]

    def clean(self):
        super().clean()
        if self.sesion_id and self.cliente_plan_id:
            if self.cliente_plan.estado != ClientePlan.Estado.VIGENTE:
                raise ValidationError({"cliente_plan": "Solo se puede registrar una mensualidad vigente."})
            if self.sesion.fecha < self.cliente_plan.fecha_inicio or self.sesion.fecha > self.cliente_plan.fecha_fin:
                raise ValidationError({"cliente_plan": "La sesión debe estar dentro de la vigencia de la mensualidad."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.cliente_plan.cliente} · {self.sesion} · {self.get_estado_display()}"
