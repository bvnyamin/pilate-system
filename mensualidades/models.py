import calendar
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import F, Q, Sum

from clientes.models import Cliente
from planes.models import Plan


def calcular_fecha_fin_mensual(fecha_inicio):
    """Devuelve el día anterior al aniversario mensual de la fecha de inicio."""
    if not fecha_inicio:
        return None

    siguiente_mes = fecha_inicio.replace(day=28) + timedelta(days=4)
    dia_aniversario = min(
        fecha_inicio.day,
        calendar.monthrange(siguiente_mes.year, siguiente_mes.month)[1],
    )
    aniversario = siguiente_mes.replace(day=dia_aniversario)
    return aniversario - timedelta(days=1)


class ClientePlan(models.Model):
    class Estado(models.TextChoices):
        VIGENTE = "vigente", "Vigente"
        FINALIZADO = "finalizado", "Finalizado"
        CANCELADO = "cancelado", "Cancelado"

    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.PROTECT,
        related_name="contrataciones",
        verbose_name="clienta",
    )
    plan = models.ForeignKey(
        Plan,
        on_delete=models.PROTECT,
        related_name="contrataciones",
        verbose_name="plan",
    )
    periodo_mes = models.PositiveSmallIntegerField(
        "mes",
        validators=[MinValueValidator(1), MaxValueValidator(12)],
    )
    periodo_anio = models.PositiveSmallIntegerField(
        "año",
        validators=[MinValueValidator(2000)],
    )
    descuento_porcentaje = models.DecimalField(
        "descuento (%)",
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))],
    )
    precio_base_clp = models.PositiveIntegerField(
        "precio base acordado (CLP)",
        blank=True,
        help_text="Snapshot del precio del plan al contratar.",
    )
    precio_final_clp = models.PositiveIntegerField(
        "precio final (CLP)",
        blank=True,
        editable=False,
    )
    fecha_inicio = models.DateField("fecha de inicio")
    fecha_fin = models.DateField("fecha de término")
    estado = models.CharField(
        "estado",
        max_length=12,
        choices=Estado.choices,
        default=Estado.VIGENTE,
        db_index=True,
    )
    created_at = models.DateTimeField("creado", auto_now_add=True)
    updated_at = models.DateTimeField("actualizado", auto_now=True)

    class Meta:
        ordering = ["-periodo_anio", "-periodo_mes", "cliente__apellidos", "cliente__nombres"]
        verbose_name = "mensualidad"
        verbose_name_plural = "mensualidades"
        constraints = [
            models.UniqueConstraint(
                fields=["cliente", "periodo_anio", "periodo_mes"],
                name="cliente_plan_periodo_uniq",
            ),
            models.CheckConstraint(
                condition=Q(periodo_mes__gte=1) & Q(periodo_mes__lte=12),
                name="cliente_plan_mes_range",
            ),
            models.CheckConstraint(
                condition=Q(descuento_porcentaje__gte=0) & Q(descuento_porcentaje__lte=100),
                name="cliente_plan_descuento_range",
            ),
            models.CheckConstraint(
                condition=Q(fecha_fin__gte=F("fecha_inicio")),
                name="cliente_plan_fechas_validas",
            ),
        ]
        indexes = [
            models.Index(
                fields=["periodo_anio", "periodo_mes", "estado"],
                name="cp_periodo_estado_idx",
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}
        fecha_inicio_cambio = self._state.adding
        plan_cambio = False
        if self.pk and not fecha_inicio_cambio:
            anterior = type(self).objects.filter(pk=self.pk).values("fecha_inicio", "plan_id").first()
            if anterior:
                fecha_inicio_cambio = anterior["fecha_inicio"] != self.fecha_inicio
                plan_cambio = anterior["plan_id"] != self.plan_id

        if self.fecha_inicio and fecha_inicio_cambio:
            self.fecha_fin = calcular_fecha_fin_mensual(self.fecha_inicio)

        if self.fecha_inicio and self.fecha_fin and self.fecha_fin < self.fecha_inicio:
            errors["fecha_fin"] = "La fecha de término no puede ser anterior al inicio."

        if self.plan_id and (plan_cambio or (self._state.adding and not self.precio_base_clp)):
            plan = Plan.objects.filter(pk=self.plan_id).only("precio_lista_clp").first()
            if plan:
                self.precio_base_clp = plan.precio_lista_clp

        if self.precio_base_clp is not None and self.descuento_porcentaje is not None:
            descuento = Decimal(self.descuento_porcentaje)
            factor = (Decimal("100") - descuento) / Decimal("100")
            self.precio_final_clp = int(
                (Decimal(self.precio_base_clp) * factor).quantize(
                    Decimal("1"),
                    rounding=ROUND_HALF_UP,
                )
            )

        if self.pk and self.cuotas.exists():
            precio_anterior = type(self).objects.filter(pk=self.pk).values_list(
                "precio_final_clp", flat=True
            ).first()
            if precio_anterior != self.precio_final_clp:
                errors["descuento_porcentaje"] = (
                    "Esta mensualidad tiene cuotas programadas. Conserva el precio acordado."
                )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    @property
    def periodo(self):
        return f"{self.periodo_mes:02d}/{self.periodo_anio}"

    @property
    def total_pagado_clp(self):
        total = self.pagos.filter(estado_pago__in=["pagado", "parcial"]).aggregate(
            total=Sum("monto_clp")
        )["total"]
        return total or 0

    @property
    def saldo_pendiente_clp(self):
        return max(self.precio_final_clp - self.total_pagado_clp, 0)

    @property
    def clases_utilizadas(self):
        anotadas = getattr(self, "present_count", None)
        if anotadas is not None:
            return anotadas
        return self.asistencias.filter(estado__in=["presente", "ausente"]).count()

    @property
    def clases_restantes(self):
        return max(self.plan.clases_por_mes - self.clases_utilizadas, 0)

    def __str__(self):
        return f"{self.cliente} · {self.plan} · {self.periodo}"
