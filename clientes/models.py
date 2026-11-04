from django.core.exceptions import ValidationError
from django.conf import settings
from django.db import models
from django.utils import timezone

from .validators import RutChilenoValidator, normalize_rut


class Cliente(models.Model):
    class Estado(models.TextChoices):
        ACTIVA = "activa", "Activa"
        INACTIVA = "inactiva", "Inactiva"

    nombres = models.CharField("nombres", max_length=120)
    apellidos = models.CharField("apellidos", max_length=120)
    rut = models.CharField(
        "RUT",
        max_length=12,
        unique=True,
        blank=True,
        null=True,
        validators=[RutChilenoValidator()],
        help_text="Opcional. Puedes completarlo después.",
    )
    email = models.EmailField("correo electrónico", blank=True)
    telefono = models.CharField("teléfono", max_length=30, blank=True)
    fecha_nacimiento = models.DateField("fecha de nacimiento", null=True, blank=True)
    fecha_incorporacion = models.DateField(
        "fecha de incorporación",
        default=timezone.localdate,
    )
    estado = models.CharField(
        "estado",
        max_length=10,
        choices=Estado.choices,
        default=Estado.ACTIVA,
        db_index=True,
    )
    observaciones = models.TextField("observaciones", blank=True)
    created_at = models.DateTimeField("creado", auto_now_add=True)
    updated_at = models.DateTimeField("actualizado", auto_now=True)

    class Meta:
        ordering = ["apellidos", "nombres"]
        verbose_name = "cliente"
        verbose_name_plural = "clientes"
        indexes = [
            models.Index(fields=["estado", "apellidos"], name="cliente_estado_apellido_idx"),
        ]

    def clean(self):
        super().clean()
        self.rut = (self.rut or "").strip() or None
        if self.rut:
            try:
                self.rut = normalize_rut(self.rut)
            except ValidationError as exc:
                raise ValidationError({"rut": exc.messages}) from exc

    def save(self, *args, **kwargs):
        self.rut = (self.rut or "").strip() or None
        if self.rut:
            try:
                self.rut = normalize_rut(self.rut)
            except ValidationError as exc:
                raise ValidationError({"rut": exc.messages}) from exc
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.nombres} {self.apellidos}"


class ImportacionFichaMedica(models.Model):
    archivo = models.CharField(max_length=255)
    creada_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    filas_pendientes = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "importación de fichas médicas"
        verbose_name_plural = "importaciones de fichas médicas"


class FichaMedica(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name="fichas_medicas")
    importacion = models.ForeignKey(ImportacionFichaMedica, on_delete=models.PROTECT, related_name="fichas")
    respuestas = models.JSONField(default=list)
    respondida_en = models.DateTimeField(db_index=True)
    huella = models.CharField(max_length=64, unique=True)
    asociada_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    criterio_asociacion = models.CharField(max_length=30)
    motivo_asociacion = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-respondida_en", "-created_at"]
        verbose_name = "ficha médica"
        verbose_name_plural = "fichas médicas"


class SolicitudAltaCliente(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente de aprobación"
        APROBADA = "aprobada", "Aprobada"
        RECHAZADA = "rechazada", "Rechazada"

    importacion = models.ForeignKey(ImportacionFichaMedica, on_delete=models.PROTECT, related_name="solicitudes")
    huella = models.CharField(max_length=64, unique=True)
    nombre_reportado = models.CharField(max_length=240)
    email_reportado = models.EmailField()
    telefono_reportado = models.CharField(max_length=30, blank=True)
    respondida_en = models.DateTimeField()
    respuestas = models.JSONField(default=list)
    estado = models.CharField(max_length=12, choices=Estado.choices, default=Estado.PENDIENTE, db_index=True)
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name="solicitudes_alta", null=True, blank=True)
    creada_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="solicitudes_alta_creadas")
    revisada_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="solicitudes_alta_revisadas", null=True, blank=True)
    resolucion = models.TextField(blank=True)
    creada_en = models.DateTimeField(auto_now_add=True)
    revisada_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["estado", "-creada_en"]
        verbose_name = "solicitud de alta de clienta"
        verbose_name_plural = "solicitudes de alta de clientas"

    def __str__(self):
        return f"{self.nombre_reportado} · {self.get_estado_display()}"
