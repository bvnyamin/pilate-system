from django.core.validators import MinValueValidator
from django.db import models
from django.db.models.functions import Lower


class Plan(models.Model):
    class Estado(models.TextChoices):
        ACTIVO = "activo", "Activo"
        INACTIVO = "inactivo", "Inactivo"

    nombre = models.CharField("nombre", max_length=80)
    clases_por_mes = models.PositiveSmallIntegerField(
        "clases por mes",
        validators=[MinValueValidator(1)],
    )
    precio_lista_clp = models.PositiveIntegerField(
        "precio de lista (CLP)",
        validators=[MinValueValidator(1)],
    )
    descripcion = models.TextField("descripción", blank=True)
    estado = models.CharField(
        "estado",
        max_length=10,
        choices=Estado.choices,
        default=Estado.ACTIVO,
        db_index=True,
    )
    created_at = models.DateTimeField("creado", auto_now_add=True)
    updated_at = models.DateTimeField("actualizado", auto_now=True)

    class Meta:
        ordering = ["precio_lista_clp", "nombre"]
        verbose_name = "plan"
        verbose_name_plural = "planes"
        constraints = [
            models.UniqueConstraint(
                Lower("nombre"),
                name="plan_nombre_ci_uniq",
            ),
        ]

    def clean(self):
        super().clean()
        if self.nombre:
            self.nombre = self.nombre.strip()

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.nombre
