from .services import resumen_notificaciones


def resumen(request):
    return resumen_notificaciones(request.user)
