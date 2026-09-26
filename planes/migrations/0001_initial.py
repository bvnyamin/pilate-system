import django.core.validators
from django.db import migrations, models
from django.db.models.functions import Lower


INITIAL_PLANS = (
    ("INICIAL", 4, 48000),
    ("FLUYE", 8, 69000),
    ("EVOLUCIONA", 12, 105000),
    ("IMPULSO", 16, 139000),
)


def create_initial_plans(apps, schema_editor):
    Plan = apps.get_model("planes", "Plan")
    manager = Plan.objects.using(schema_editor.connection.alias)
    for nombre, clases, precio in INITIAL_PLANS:
        manager.get_or_create(
            nombre=nombre,
            defaults={
                "clases_por_mes": clases,
                "precio_lista_clp": precio,
                "estado": "activo",
            },
        )


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Plan",
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
                ("nombre", models.CharField(max_length=80, verbose_name="nombre")),
                (
                    "clases_por_mes",
                    models.PositiveSmallIntegerField(
                        validators=[django.core.validators.MinValueValidator(1)],
                        verbose_name="clases por mes",
                    ),
                ),
                (
                    "precio_lista_clp",
                    models.PositiveIntegerField(
                        validators=[django.core.validators.MinValueValidator(1)],
                        verbose_name="precio de lista (CLP)",
                    ),
                ),
                ("descripcion", models.TextField(blank=True, verbose_name="descripción")),
                (
                    "estado",
                    models.CharField(
                        choices=[("activo", "Activo"), ("inactivo", "Inactivo")],
                        db_index=True,
                        default="activo",
                        max_length=10,
                        verbose_name="estado",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="creado")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="actualizado")),
            ],
            options={
                "verbose_name": "plan",
                "verbose_name_plural": "planes",
                "ordering": ["precio_lista_clp", "nombre"],
            },
        ),
        migrations.AddConstraint(
            model_name="plan",
            constraint=models.UniqueConstraint(
                Lower("nombre"),
                name="plan_nombre_ci_uniq",
            ),
        ),
        migrations.RunPython(create_initial_plans, migrations.RunPython.noop),
    ]
