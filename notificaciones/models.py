from django.db import models
from django.db.models import Q


class AvisoMorosidadEnviado(models.Model):
    periodo_anio = models.PositiveSmallIntegerField("año")
    periodo_mes = models.PositiveSmallIntegerField("mes")
    destinatarios = models.TextField("destinatarios")
    clientas_informadas = models.PositiveIntegerField("clientas informadas")
    enviado_at = models.DateTimeField("enviado", auto_now_add=True)

    class Meta:
        ordering = ["-periodo_anio", "-periodo_mes"]
        verbose_name = "aviso de morosidad enviado"
        verbose_name_plural = "avisos de morosidad enviados"
        constraints = [
            models.UniqueConstraint(
                fields=["periodo_anio", "periodo_mes"],
                name="aviso_morosidad_periodo_uniq",
            ),
            models.CheckConstraint(
                condition=Q(periodo_mes__gte=1) & Q(periodo_mes__lte=12),
                name="aviso_morosidad_mes_range",
            ),
        ]

    def __str__(self):
        return f"Morosidad {self.periodo_mes:02d}/{self.periodo_anio}"
