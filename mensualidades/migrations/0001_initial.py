import decimal

import django.core.validators
from django.db import migrations, models
import django.db.models.deletion
from django.db.models import F, Q


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("clientes", "0002_alter_cliente_rut"),
        ("planes", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ClientePlan",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "periodo_mes",
                    models.PositiveSmallIntegerField(
                        validators=[
                            django.core.validators.MinValueValidator(1),
                            django.core.validators.MaxValueValidator(12),
                        ],
                        verbose_name="mes",
                    ),
                ),
                (
                    "periodo_anio",
                    models.PositiveSmallIntegerField(
                        validators=[django.core.validators.MinValueValidator(2000)],
                        verbose_name="año",
                    ),
                ),
                (
                    "descuento_porcentaje",
                    models.DecimalField(
                        decimal_places=2,
                        default=decimal.Decimal("0.00"),
                        max_digits=5,
                        validators=[
                            django.core.validators.MinValueValidator(decimal.Decimal("0")),
                            django.core.validators.MaxValueValidator(decimal.Decimal("100")),
                        ],
                        verbose_name="descuento (%)",
                    ),
                ),
                (
                    "precio_base_clp",
                    models.PositiveIntegerField(
                        blank=True,
                        help_text="Snapshot del precio del plan al contratar.",
                        verbose_name="precio base acordado (CLP)",
                    ),
                ),
                (
                    "precio_final_clp",
                    models.PositiveIntegerField(blank=True, editable=False, verbose_name="precio final (CLP)"),
                ),
                ("fecha_inicio", models.DateField(verbose_name="fecha de inicio")),
                ("fecha_fin", models.DateField(verbose_name="fecha de término")),
                (
                    "estado",
                    models.CharField(
                        choices=[
                            ("vigente", "Vigente"),
                            ("finalizado", "Finalizado"),
                            ("cancelado", "Cancelado"),
                        ],
                        db_index=True,
                        default="vigente",
                        max_length=12,
                        verbose_name="estado",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="creado")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="actualizado")),
                (
                    "cliente",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="contrataciones",
                        to="clientes.cliente",
                        verbose_name="clienta",
                    ),
                ),
                (
                    "plan",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="contrataciones",
                        to="planes.plan",
                        verbose_name="plan",
                    ),
                ),
            ],
            options={
                "verbose_name": "mensualidad",
                "verbose_name_plural": "mensualidades",
                "ordering": ["-periodo_anio", "-periodo_mes", "cliente__apellidos", "cliente__nombres"],
                "indexes": [
                    models.Index(
                        fields=["periodo_anio", "periodo_mes", "estado"],
                        name="cp_periodo_estado_idx",
                    )
                ],
            },
        ),
        migrations.AddConstraint(
            model_name="clienteplan",
            constraint=models.UniqueConstraint(
                fields=("cliente", "periodo_anio", "periodo_mes"),
                name="cliente_plan_periodo_uniq",
            ),
        ),
        migrations.AddConstraint(
            model_name="clienteplan",
            constraint=models.CheckConstraint(
                condition=Q(periodo_mes__gte=1) & Q(periodo_mes__lte=12),
                name="cliente_plan_mes_range",
            ),
        ),
        migrations.AddConstraint(
            model_name="clienteplan",
            constraint=models.CheckConstraint(
                condition=Q(descuento_porcentaje__gte=0) & Q(descuento_porcentaje__lte=100),
                name="cliente_plan_descuento_range",
            ),
        ),
        migrations.AddConstraint(
            model_name="clienteplan",
            constraint=models.CheckConstraint(
                condition=Q(fecha_fin__gte=F("fecha_inicio")),
                name="cliente_plan_fechas_validas",
            ),
        ),
    ]
