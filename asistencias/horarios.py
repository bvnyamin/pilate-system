from datetime import date, datetime, time, timedelta


INTERVALO_INICIO_MINUTOS = 30


def configuracion_horarios():
    # Importación local para evitar un ciclo al cargar los modelos.
    from .models import HorarioEstudio

    horario, _ = HorarioEstudio.objects.get_or_create(pk=1)
    return horario


def periodos_clases(horario=None):
    horario = horario or configuracion_horarios()
    return (
        (
            f"Bloque matutino · {horario.matutino_inicio:%H:%M} a {horario.matutino_fin:%H:%M} hrs",
            horario.matutino_inicio,
            horario.matutino_fin,
        ),
        (
            f"Bloque vespertino · {horario.vespertino_inicio:%H:%M} a {horario.vespertino_fin:%H:%M} hrs",
            horario.vespertino_inicio,
            horario.vespertino_fin,
        ),
    )


def descripcion_horarios(horario=None):
    return "; ".join(label.replace("Bloque matutino · ", "").replace("Bloque vespertino · ", "") for label, _, _ in periodos_clases(horario))


def horas_inicio_permitidas(horario=None):
    horas = []
    intervalo = timedelta(minutes=INTERVALO_INICIO_MINUTOS)
    for _, inicio, fin in periodos_clases(horario):
        actual = inicio
        while actual < fin:
            horas.append(actual)
            actual = (datetime.combine(date.min, actual) + intervalo).time()
    return tuple(horas)


def es_hora_inicio_permitida(hora):
    if hora is None:
        return False
    return hora.replace(second=0, microsecond=0) in horas_inicio_permitidas() and not hora.second and not hora.microsecond
