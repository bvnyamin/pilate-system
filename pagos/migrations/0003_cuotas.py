import django.db.models.deletion
from django.core.validators import MinValueValidator
from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [
        ("pagos", "0002_matricula_unica"),
    ]

    operations = [
        migrations.CreateModel(
            name="Cuota",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("numero", models.PositiveSmallIntegerField(validators=[MinValueValidator(1)], verbose_name="número de cuota")),
                ("monto_clp", models.PositiveIntegerField(validators=[MinValueValidator(1)], verbose_name="monto programado (CLP)")),
                ("fecha_vencimiento", models.DateField(verbose_name="vencimiento")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="creada")),
                ("cliente_plan", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="cuotas", to="mensualidades.clienteplan", verbose_name="mensualidad")),
            ],
            options={
                "verbose_name": "cuota",
                "verbose_name_plural": "cuotas",
                "ordering": ["cliente_plan_id", "numero"],
            },
        ),
        migrations.AddField(
            model_name="pago",
            name="cuota",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="pagos", to="pagos.cuota", verbose_name="cuota"),
        ),
        migrations.AddConstraint(
            model_name="cuota",
            constraint=models.UniqueConstraint(fields=("cliente_plan", "numero"), name="cuota_plan_numero_uniq"),
        ),
        migrations.AddConstraint(
            model_name="cuota",
            constraint=models.CheckConstraint(condition=Q(numero__gte=1), name="cuota_numero_positivo"),
        ),
        migrations.AddConstraint(
            model_name="cuota",
            constraint=models.CheckConstraint(condition=Q(monto_clp__gte=1), name="cuota_monto_positivo"),
        ),
    ]
