from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.db.models import Q, Sum
from django.utils import timezone

from clientes.models import Cliente
from mensualidades.models import ClientePlan


class Cuota(models.Model):
    cliente_plan = models.ForeignKey(
        ClientePlan,
        on_delete=models.PROTECT,
        related_name="cuotas",
        verbose_name="mensualidad",
    )
    numero = models.PositiveSmallIntegerField("número de cuota", validators=[MinValueValidator(1)])
    monto_clp = models.PositiveIntegerField("monto programado (CLP)", validators=[MinValueValidator(1)])
    fecha_vencimiento = models.DateField("vencimiento")
    created_at = models.DateTimeField("creada", auto_now_add=True)

    class Meta:
        ordering = ["cliente_plan_id", "numero"]
        verbose_name = "cuota"
        verbose_name_plural = "cuotas"
        constraints = [
            models.UniqueConstraint(fields=["cliente_plan", "numero"], name="cuota_plan_numero_uniq"),
            models.CheckConstraint(condition=Q(numero__gte=1), name="cuota_numero_positivo"),
            models.CheckConstraint(condition=Q(monto_clp__gte=1), name="cuota_monto_positivo"),
        ]

    def clean(self):
        super().clean()
        if not self.cliente_plan_id or not self.monto_clp:
            return
        monto_previo = Pago.objects.filter(
            cliente_plan_id=self.cliente_plan_id,
            cuota__isnull=True,
            estado_pago__in=[Pago.EstadoPago.PAGADO, Pago.EstadoPago.PARCIAL],
        ).aggregate(total=Sum("monto_clp"))["total"] or 0
        otras_cuotas = Cuota.objects.filter(cliente_plan_id=self.cliente_plan_id).exclude(pk=self.pk)
        total_programado = otras_cuotas.aggregate(total=Sum("monto_clp"))["total"] or 0
        if monto_previo + total_programado + self.monto_clp > self.cliente_plan.precio_final_clp:
            raise ValidationError({"monto_clp": "Las cuotas superan el saldo de esta mensualidad."})
        if self.pk and self.total_pagado_clp > self.monto_clp:
            raise ValidationError({"monto_clp": "La cuota no puede quedar por debajo de lo ya pagado."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    @property
    def total_pagado_clp(self):
        if hasattr(self, "recibido_anotado"):
            return self.recibido_anotado or 0
        return self.pagos.filter(estado_pago__in=["pagado", "parcial"]).aggregate(
            total=Sum("monto_clp")
        )["total"] or 0

    @property
    def saldo_pendiente_clp(self):
        return max(self.monto_clp - self.total_pagado_clp, 0)

    def __str__(self):
        return f"Cuota {self.numero} · {self.cliente_plan}"


class Pago(models.Model):
    MONTO_MATRICULA_CLP = 25000

    class TipoPago(models.TextChoices):
        MENSUALIDAD = "mensualidad", "Mensualidad"
        MATRICULA = "matricula", "Matrícula única"

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

    tipo_pago = models.CharField(
        "tipo de pago",
        max_length=12,
        choices=TipoPago.choices,
        default=TipoPago.MENSUALIDAD,
    )
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.PROTECT,
        related_name="pagos",
        blank=True,
        null=True,
        verbose_name="clienta",
    )
    cliente_plan = models.ForeignKey(
        ClientePlan,
        on_delete=models.PROTECT,
        related_name="pagos",
        blank=True,
        null=True,
        verbose_name="mensualidad",
    )
    cuota = models.ForeignKey(
        Cuota,
        on_delete=models.PROTECT,
        related_name="pagos",
        blank=True,
        null=True,
        verbose_name="cuota",
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
            models.CheckConstraint(
                condition=(
                    Q(tipo_pago="mensualidad", cliente__isnull=True, cliente_plan__isnull=False)
                    | Q(tipo_pago="matricula", cliente__isnull=False, cliente_plan__isnull=True)
                ),
                name="pago_tipo_relacion_valida",
            ),
            models.UniqueConstraint(
                fields=["cliente"],
                condition=Q(tipo_pago="matricula"),
                name="pago_matricula_unica_cliente",
            ),
        ]
        indexes = [
            models.Index(fields=["estado_pago", "fecha_pago"], name="pago_estado_fecha_idx"),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.tipo_pago == self.TipoPago.MATRICULA:
            if not self.cliente_id:
                errors["cliente"] = "Selecciona la clienta para registrar su matrícula."
            if self.cliente_plan_id:
                errors["cliente_plan"] = "La matrícula no se asocia a una mensualidad."
            if self.cuota_id:
                errors["cuota"] = "La matrícula no se asocia a cuotas."
            if self.monto_clp != self.MONTO_MATRICULA_CLP:
                errors["monto_clp"] = (
                    f"El valor de la matrícula es ${self.MONTO_MATRICULA_CLP:,} CLP."
                )
            if self.estado_pago == self.EstadoPago.PARCIAL:
                errors["estado_pago"] = "La matrícula se registra completa o pendiente, no como abono parcial."
            if self.cliente_id and Pago.objects.filter(
                tipo_pago=self.TipoPago.MATRICULA,
                cliente_id=self.cliente_id,
            ).exclude(pk=self.pk).exists():
                errors["cliente"] = "Esta clienta ya tiene un registro de matrícula. Edita ese movimiento."
        elif self.tipo_pago == self.TipoPago.MENSUALIDAD:
            if not self.cliente_plan_id:
                errors["cliente_plan"] = "Selecciona la mensualidad asociada a este pago."
            if self.cliente_id:
                errors["cliente"] = "Los pagos de mensualidad se vinculan mediante su mensualidad."
            if self.cuota_id and self.cliente_plan_id and self.cuota.cliente_plan_id != self.cliente_plan_id:
                errors["cuota"] = "La cuota debe corresponder a la mensualidad seleccionada."
            if self.cliente_plan_id and not self.cuota_id and Cuota.objects.filter(cliente_plan_id=self.cliente_plan_id).exists():
                anterior = Pago.objects.filter(pk=self.pk).values(
                    "cliente_plan_id", "cuota_id", "monto_clp", "estado_pago"
                ).first() if self.pk else None
                if not anterior or any(
                    anterior[campo] != getattr(self, campo)
                    for campo in ("cliente_plan_id", "cuota_id", "monto_clp", "estado_pago")
                ):
                    errors["cuota"] = "Selecciona una cuota. Los pagos anteriores al acuerdo no pueden cambiar su monto o estado."

        if (
            self.tipo_pago == self.TipoPago.MENSUALIDAD
            and self.cliente_plan_id
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
            if self.cuota_id:
                otros_abonos_cuota = Pago.objects.filter(
                    cuota_id=self.cuota_id,
                    estado_pago__in=[self.EstadoPago.PAGADO, self.EstadoPago.PARCIAL],
                ).exclude(pk=self.pk).aggregate(total=Sum("monto_clp"))["total"] or 0
                if otros_abonos_cuota + self.monto_clp > self.cuota.monto_clp:
                    errors["monto_clp"] = "El total recibido superaría el monto de esta cuota."

        if errors:
            raise ValidationError(errors)

    @property
    def cliente_asociado(self):
        if self.tipo_pago == self.TipoPago.MATRICULA:
            return self.cliente
        return self.cliente_plan.cliente if self.cliente_plan_id else None

    @property
    def referencia_display(self):
        if self.tipo_pago == self.TipoPago.MATRICULA:
            return "Matrícula única"
        if self.cliente_plan_id:
            return f"{self.cliente_plan.plan.nombre} · {self.cliente_plan.periodo}"
        return "—"

    def save(self, *args, **kwargs):
        with transaction.atomic():
            if self.cliente_plan_id:
                ClientePlan.objects.select_for_update().get(pk=self.cliente_plan_id)
            if self.cliente_id:
                Cliente.objects.select_for_update().get(pk=self.cliente_id)
            self.full_clean()
            return super().save(*args, **kwargs)

    def __str__(self):
        monto_formateado = f"${self.monto_clp:,}".replace(",", ".")
        return f"{self.concepto} · {monto_formateado} · {self.fecha_pago:%d/%m/%Y}"
