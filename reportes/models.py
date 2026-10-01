from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class Gasto(models.Model):
    class Categoria(models.TextChoices):
        ARRIENDO = "arriendo", "Arriendo"
        ELECTRICIDAD = "electricidad", "Luz / electricidad"
        AGUA = "agua", "Agua"
        GAS = "gas", "Gas"
        INTERNET = "internet", "Internet"
        ASEO = "aseo", "Aseo e insumos"
        MANTENCION = "mantencion", "Mantención"
        OTRO = "otro", "Otro gasto"

    categoria = models.CharField("categoría", max_length=20, choices=Categoria.choices, db_index=True)
    descripcion = models.CharField("descripción", max_length=160)
    monto_clp = models.PositiveIntegerField("monto (CLP)", validators=[MinValueValidator(1)])
    fecha = models.DateField("fecha del gasto", default=timezone.localdate, db_index=True)
    observaciones = models.TextField("observaciones", blank=True)
    created_at = models.DateTimeField("registrado", auto_now_add=True)
    updated_at = models.DateTimeField("actualizado", auto_now=True)

    class Meta:
        ordering = ["-fecha", "-created_at"]
        verbose_name = "gasto del estudio"
        verbose_name_plural = "gastos del estudio"
        indexes = [models.Index(fields=["fecha", "categoria"], name="gasto_fecha_categoria_idx")]
        constraints = [models.CheckConstraint(condition=models.Q(monto_clp__gte=1), name="gasto_monto_positivo")]

    def __str__(self):
        return f"{self.get_categoria_display()} · {self.descripcion} · ${self.monto_clp:,}"
