import django.core.validators
import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("mensualidades", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Pago",
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
                ("concepto", models.CharField(max_length=150, verbose_name="concepto")),
                (
                    "monto_clp",
                    models.PositiveIntegerField(
                        validators=[django.core.validators.MinValueValidator(1)],
                        verbose_name="monto (CLP)",
                    ),
                ),
                (
                    "metodo_pago",
                    models.CharField(
                        choices=[
                            ("transferencia", "Transferencia"),
                            ("efectivo", "Efectivo"),
                            ("debito", "Débito"),
                            ("credito", "Crédito"),
                        ],
                        max_length=16,
                        verbose_name="método de pago",
                    ),
                ),
                (
                    "fecha_pago",
                    models.DateField(default=django.utils.timezone.localdate, verbose_name="fecha de pago"),
                ),
                (
                    "estado_pago",
                    models.CharField(
                        choices=[
                            ("pagado", "Pagado"),
                            ("pendiente", "Pendiente"),
                            ("parcial", "Pago parcial"),
                            ("anulado", "Anulado"),
                        ],
                        db_index=True,
                        default="pagado",
                        max_length=10,
                        verbose_name="estado de pago",
                    ),
                ),
                ("observaciones", models.TextField(blank=True, verbose_name="observaciones")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="creado")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="actualizado")),
                (
                    "cliente_plan",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="pagos",
                        to="mensualidades.clienteplan",
                        verbose_name="mensualidad",
                    ),
                ),
            ],
            options={
                "verbose_name": "pago",
                "verbose_name_plural": "pagos",
                "ordering": ["-fecha_pago", "-created_at"],
                "indexes": [models.Index(fields=["estado_pago", "fecha_pago"], name="pago_estado_fecha_idx")],
            },
        ),
        migrations.AddConstraint(
            model_name="pago",
            constraint=models.CheckConstraint(
                condition=Q(monto_clp__gte=1),
                name="pago_monto_positivo",
            ),
        ),
    ]
