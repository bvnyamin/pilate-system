from datetime import datetime, time, timedelta

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from mensualidades.models import ClientePlan
from .horarios import es_hora_inicio_permitida


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
        if self.hora and not es_hora_inicio_permitida(self.hora):
            guardada = type(self).objects.filter(pk=self.pk).values("fecha", "hora").first() if self.pk else None
            if not guardada or guardada["fecha"] != self.fecha or guardada["hora"] != self.hora:
                from .horarios import descripcion_horarios

                raise ValidationError({"hora": f"Selecciona una hora de inicio dentro de los bloques configurados: {descripcion_horarios()}."})
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
        RECUPERACION = "recuperacion", "Recuperó (usar clase pendiente)"
        JUSTIFICADO = "justificado", "Justificado"

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
        max_length=12,
        choices=Estado.choices,
        default=Estado.PRESENTE,
        db_index=True,
    )
    observaciones = models.TextField("observaciones", blank=True)
    motivo_cancelacion = models.TextField("motivo de cancelación", blank=True)
    fecha_aviso_cancelacion = models.DateTimeField("fecha y hora del aviso", null=True, blank=True)
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
            if self._state.adding and self.cliente_plan.estado != ClientePlan.Estado.VIGENTE:
                raise ValidationError({"cliente_plan": "Solo se puede registrar una mensualidad vigente."})
            if self.sesion.fecha < self.cliente_plan.fecha_inicio or self.sesion.fecha > self.cliente_plan.fecha_fin:
                raise ValidationError({"cliente_plan": "La sesión debe estar dentro de la vigencia de la mensualidad."})
            if self.estado in (self.Estado.PRESENTE, self.Estado.AUSENTE, self.Estado.RECUPERACION):
                attended_same_day = type(self).objects.filter(
                    cliente_plan_id=self.cliente_plan_id,
                    sesion__fecha=self.sesion.fecha,
                    estado__in=(self.Estado.PRESENTE, self.Estado.AUSENTE, self.Estado.RECUPERACION),
                ).exclude(pk=self.pk)
                if attended_same_day.exists():
                    raise ValidationError({"estado": "La clienta ya tiene una asistencia registrada ese día."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    @property
    def genera_recuperacion(self):
        if self.estado != self.Estado.CANCELO or not self.fecha_aviso_cancelacion:
            return False
        inicio = timezone.make_aware(
            datetime.combine(self.sesion.fecha, self.sesion.hora), timezone.get_current_timezone()
        )
        aviso = self.fecha_aviso_cancelacion
        if timezone.is_naive(aviso):
            aviso = timezone.make_aware(aviso, timezone.get_current_timezone())
        return aviso <= inicio - timedelta(hours=4)

    def __str__(self):
        return f"{self.cliente_plan.cliente} · {self.sesion} · {self.get_estado_display()}"


class RecuperacionClase(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        UTILIZADA = "utilizada", "Utilizada"
        INVALIDADA = "invalidada", "Invalidada"

    asistencia_origen = models.OneToOneField(
        Asistencia, on_delete=models.PROTECT, related_name="recuperacion_generada",
        verbose_name="cancelación de origen",
    )
    asistencia_recuperacion = models.OneToOneField(
        Asistencia, on_delete=models.PROTECT, related_name="recuperacion_utilizada",
        verbose_name="sesión de recuperación", null=True, blank=True,
    )
    estado = models.CharField("estado", max_length=12, choices=Estado.choices, default=Estado.PENDIENTE)
    created_at = models.DateTimeField("creada", auto_now_add=True)

    class Meta:
        verbose_name = "recuperación de clase"
        verbose_name_plural = "recuperaciones de clases"

    def clean(self):
        super().clean()
        if self.asistencia_origen_id and not self.asistencia_origen.genera_recuperacion:
            raise ValidationError("La cancelación no cumple el aviso mínimo de cuatro horas.")
        if self.asistencia_origen_id and self.asistencia_recuperacion_id:
            origen = self.asistencia_origen
            destino = self.asistencia_recuperacion
            if destino.estado != Asistencia.Estado.RECUPERACION:
                raise ValidationError({"asistencia_recuperacion": "La sesión debe estar marcada como recuperación."})
            if destino.cliente_plan_id != origen.cliente_plan_id:
                raise ValidationError({"asistencia_recuperacion": "La recuperación debe corresponder a la misma mensualidad."})
            if (destino.sesion.fecha.year, destino.sesion.fecha.month) != (origen.sesion.fecha.year, origen.sesion.fecha.month):
                raise ValidationError({"asistencia_recuperacion": "La recuperación debe usarse dentro del mismo mes."})
        if self.estado == self.Estado.PENDIENTE and self.asistencia_recuperacion_id:
            raise ValidationError({"asistencia_recuperacion": "Una recuperación pendiente no puede tener una sesión asignada."})
        if self.estado == self.Estado.UTILIZADA and not self.asistencia_recuperacion_id:
            raise ValidationError({"asistencia_recuperacion": "Registra la sesión donde se utilizó la recuperación."})

    def __str__(self):
        return f"Recuperación · {self.asistencia_origen} · {self.get_estado_display()}"


class HorarioEstudio(models.Model):
    """Ventanas horarias del estudio; un único registro gobierna ambos bloques."""

    matutino_inicio = models.TimeField("inicio del bloque matutino", default=time(8, 0))
    matutino_fin = models.TimeField("término del bloque matutino", default=time(12, 0))
    vespertino_inicio = models.TimeField("inicio del bloque vespertino", default=time(17, 0))
    vespertino_fin = models.TimeField("término del bloque vespertino", default=time(21, 0))

    class Meta:
        verbose_name = "horario del estudio"
        verbose_name_plural = "horario del estudio"

    def clean(self):
        super().clean()
        errors = {}
        bloques = (
            ("matutino_inicio", "matutino_fin"),
            ("vespertino_inicio", "vespertino_fin"),
        )
        for inicio_field, fin_field in bloques:
            inicio = getattr(self, inicio_field)
            fin = getattr(self, fin_field)
            for field_name, hora in ((inicio_field, inicio), (fin_field, fin)):
                if hora and (hora.second or hora.microsecond or hora.minute not in (0, 30)):
                    errors[field_name] = "Usa intervalos de 30 minutos, por ejemplo 08:00 o 08:30."
            if inicio and fin and inicio >= fin:
                errors[fin_field] = "El término debe ser posterior al inicio."
        if all(getattr(self, field) for fields in bloques for field in fields):
            if self.matutino_inicio >= self.vespertino_inicio:
                errors["vespertino_inicio"] = "El bloque vespertino debe comenzar después del matutino."
            if self.matutino_inicio < self.vespertino_fin and self.vespertino_inicio < self.matutino_fin:
                errors["vespertino_inicio"] = "Los dos bloques no pueden superponerse."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.pk = 1
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("La configuración horaria única no se puede eliminar.")

    def __str__(self):
        return "Bloques horarios del estudio"
