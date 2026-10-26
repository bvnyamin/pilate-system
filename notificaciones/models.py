from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone


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


class NotificacionLeida(models.Model):
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notificaciones_leidas",
    )
    clave = models.CharField(max_length=120)
    leida_en = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-leida_en"]
        constraints = [
            models.UniqueConstraint(
                fields=["usuario", "clave"],
                name="notificacion_leida_usuario_clave_uniq",
            ),
        ]
        verbose_name = "notificación leída"
        verbose_name_plural = "notificaciones leídas"

    def __str__(self):
        return f"{self.usuario} · {self.clave}"
