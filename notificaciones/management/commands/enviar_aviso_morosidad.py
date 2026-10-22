from django.core.management.base import BaseCommand

from notificaciones.services import enviar_aviso_morosidad


class Command(BaseCommand):
    help = "Envía una vez al mes el aviso de mensualidades pendientes desde el día 7."

    def handle(self, *args, **options):
        resultado = enviar_aviso_morosidad()
        if resultado["enviado"]:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Aviso enviado con {resultado['cantidad']} mensualidades a "
                    f"{', '.join(resultado['destinatarios'])}."
                )
            )
        elif resultado.get("registrado_en_consola"):
            self.stdout.write(self.style.WARNING(resultado["razon"]))
        else:
            self.stdout.write(resultado["razon"])
