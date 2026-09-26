from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.db.models import Q, Sum
from django.utils import timezone

from mensualidades.models import ClientePlan


class Pago(models.Model):
    class MetodoPago(models.TextChoices):
        TRANSFERENCIA = "transferencia", "Transferencia"
        EFECTIVO = "efectivo", "Efectivo"
        DEBITO = "debito", "Débito"
        CREDITO = "credito", "Crédito"

    class EstadoPago(models.TextChoices):
        PAGADO = "pagado", "Pagado"
        PENDIENTE = "pendiente", "Pendiente"
        PARCIAL = "parcial", "Pago parcial"
        ANULADO = "anulado", "Anulado"

    cliente_plan = models.ForeignKey(
        ClientePlan,
        on_delete=models.PROTECT,
        related_name="pagos",
        verbose_name="mensualidad",
    )
    concepto = models.CharField("concepto", max_length=150)
    monto_clp = models.PositiveIntegerField(
        "monto (CLP)",
        validators=[MinValueValidator(1)],
    )
    metodo_pago = models.CharField(
        "método de pago",
        max_length=16,
        choices=MetodoPago.choices,
    )
    fecha_pago = models.DateField("fecha de pago", default=timezone.localdate)
    estado_pago = models.CharField(
        "estado de pago",
        max_length=10,
        choices=EstadoPago.choices,
        default=EstadoPago.PAGADO,
        db_index=True,
    )
    observaciones = models.TextField("observaciones", blank=True)
    created_at = models.DateTimeField("creado", auto_now_add=True)
    updated_at = models.DateTimeField("actualizado", auto_now=True)

    class Meta:
        ordering = ["-fecha_pago", "-created_at"]
        verbose_name = "pago"
        verbose_name_plural = "pagos"
        constraints = [
            models.CheckConstraint(
                condition=Q(monto_clp__gte=1),
                name="pago_monto_positivo",
            ),
        ]
        indexes = [
            models.Index(fields=["estado_pago", "fecha_pago"], name="pago_estado_fecha_idx"),
        ]

    def clean(self):
        super().clean()
        if (
            self.cliente_plan_id
            and self.monto_clp
            and self.estado_pago in (self.EstadoPago.PAGADO, self.EstadoPago.PARCIAL)
        ):
            otros_pagos = Pago.objects.filter(
                cliente_plan_id=self.cliente_plan_id,
                estado_pago__in=[self.EstadoPago.PAGADO, self.EstadoPago.PARCIAL],
            ).exclude(pk=self.pk)
            total_existente = otros_pagos.aggregate(total=Sum("monto_clp"))["total"] or 0
            precio_acordado = self.cliente_plan.precio_final_clp
            if total_existente + self.monto_clp > precio_acordado:
                raise ValidationError(
                    {
                        "monto_clp": (
                            "El total de pagos recibidos superaría el precio acordado "
                            f"({precio_acordado:,} CLP)."
                        )
                    }
                )

    def save(self, *args, **kwargs):
        with transaction.atomic():
            if self.cliente_plan_id:
                ClientePlan.objects.select_for_update().get(pk=self.cliente_plan_id)
            self.full_clean()
            return super().save(*args, **kwargs)

    def __str__(self):
        monto_formateado = f"${self.monto_clp:,}".replace(",", ".")
        return f"{self.concepto} · {monto_formateado} · {self.fecha_pago:%d/%m/%Y}"
