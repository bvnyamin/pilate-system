import django.db.models.deletion
from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [
        ("clientes", "0001_initial"),
        ("pagos", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="pago",
            name="tipo_pago",
            field=models.CharField(
                choices=[("mensualidad", "Mensualidad"), ("matricula", "Matrícula única")],
                default="mensualidad",
                max_length=12,
                verbose_name="tipo de pago",
            ),
        ),
        migrations.AddField(
            model_name="pago",
            name="cliente",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="pagos",
                to="clientes.cliente",
                verbose_name="clienta",
            ),
        ),
        migrations.AlterField(
            model_name="pago",
            name="cliente_plan",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="pagos",
                to="mensualidades.clienteplan",
                verbose_name="mensualidad",
            ),
        ),
        migrations.AddConstraint(
            model_name="pago",
            constraint=models.CheckConstraint(
                condition=(
                    Q(tipo_pago="mensualidad", cliente__isnull=True, cliente_plan__isnull=False)
                    | Q(tipo_pago="matricula", cliente__isnull=False, cliente_plan__isnull=True)
                ),
                name="pago_tipo_relacion_valida",
            ),
        ),
        migrations.AddConstraint(
            model_name="pago",
            constraint=models.UniqueConstraint(
                fields=("cliente",),
                condition=Q(tipo_pago="matricula"),
                name="pago_matricula_unica_cliente",
            ),
        ),
    ]
