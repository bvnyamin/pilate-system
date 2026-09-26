from django.core.exceptions import ValidationError
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
        validators=[RutChilenoValidator()],
        help_text="Puedes ingresarlo con puntos y guion; se guardará normalizado.",
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
        if self.rut:
            try:
                self.rut = normalize_rut(self.rut)
            except ValidationError as exc:
                raise ValidationError({"rut": exc.messages}) from exc

    def save(self, *args, **kwargs):
        if self.rut:
            try:
                self.rut = normalize_rut(self.rut)
            except ValidationError as exc:
                raise ValidationError({"rut": exc.messages}) from exc
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.nombres} {self.apellidos}"
