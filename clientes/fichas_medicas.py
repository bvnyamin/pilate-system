"""Lectura del CSV de Google Forms y coincidencias exactas de contacto."""
import csv
import hashlib
import io
import json
import re
import unicodedata
from datetime import datetime, timedelta, timezone as datetime_timezone

from django.utils import timezone
from django.utils.dateparse import parse_datetime


MAX_CSV_BYTES = 2 * 1024 * 1024
MAX_CSV_ROWS = 2000


def normalizar_texto(value):
    text = unicodedata.normalize("NFKD", str(value or ""))
    return " ".join("".join(c for c in text if not unicodedata.combining(c)).lower().split())


def normalizar_correo(value):
    return str(value or "").strip().casefold()


def normalizar_telefono(value):
    value = str(value or "").strip()
    if re.search(r"[^\d\s+().-]", value):
        return ""
    digits = re.sub(r"\D", "", value)
    if len(digits) == 11 and digits.startswith("56"):
        digits = digits[2:]
    return digits if len(digits) == 9 and digits[0] in "29" else ""


def parsear_marca_temporal(value):
    try:
        parsed = parse_datetime(value)
    except ValueError:
        parsed = None
    if parsed is None:
        # Google Forms exporta también horas de doce horas en español con zona GMT.
        localized = re.fullmatch(
            r"(\d{4}/\d{2}/\d{2}) (\d{1,2}:\d{2}:\d{2}) ([ap])\.\s*m\.\s*gmt([+-]\d{1,2})(?::(\d{2}))?",
            normalizar_texto(value),
        )
        if localized:
            day, hour, meridiem, offset, minutes = localized.groups()
            try:
                parsed = datetime.strptime(f"{day} {hour}", "%Y/%m/%d %H:%M:%S")
                if not 1 <= parsed.hour <= 12 or not -12 <= int(offset) <= 14 or int(minutes or 0) >= 60:
                    return None
                parsed = parsed.replace(hour=parsed.hour % 12 + (12 if meridiem == "p" else 0))
                zone = timedelta(hours=int(offset), minutes=int(minutes or 0) * (-1 if offset.startswith("-") else 1))
                parsed = parsed.replace(tzinfo=datetime_timezone(zone))
            except ValueError:
                return None
    if parsed is None:
        for fmt in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%Y/%m/%d %H:%M:%S"):
            try:
                parsed = datetime.strptime(value, fmt)
                break
            except ValueError:
                pass
    if parsed is not None and timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.get_default_timezone())
    return parsed


def leer_csv(archivo):
    if archivo.size > MAX_CSV_BYTES:
        raise ValueError("El archivo supera el máximo de 2 MB.")
    raw = archivo.read(MAX_CSV_BYTES + 1)
    if len(raw) > MAX_CSV_BYTES:
        raise ValueError("El archivo supera el máximo de 2 MB.")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("Exporta el CSV con codificación UTF-8 desde Google Forms o Sheets.") from exc
    try:
        dialect = csv.Sniffer().sniff(text[:8192], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.reader(io.StringIO(text, newline=""), dialect=dialect, strict=True)
    try:
        headers = next(reader)
        normalized = [normalizar_texto(h) for h in headers]
        required = ["marca temporal", "nombre completo", "correo electronico", "telefono de contacto"]
        if any(h not in normalized for h in required):
            raise ValueError("Faltan columnas: Marca temporal, Nombre completo, Correo electronico o Telefono de contacto.")
        # El primer teléfono pertenece a la clienta; el posterior es el de emergencia.
        indexes = {name: normalized.index(name) for name in required}
        rows = []
        for number, values in enumerate(reader, start=2):
            if not any(v.strip() for v in values):
                continue
            if len(rows) >= MAX_CSV_ROWS:
                raise ValueError("El archivo supera las 2000 respuestas permitidas.")
            if len(values) != len(headers) or any(len(v) > 20000 for v in values):
                raise ValueError(f"La respuesta {number} tiene columnas incompletas o un campo demasiado largo.")
            values = [v.strip() for v in values]
            timestamp = values[indexes["marca temporal"]]
            parsed = parsear_marca_temporal(timestamp)
            if parsed is None:
                raise ValueError(f"La respuesta {number} tiene una marca temporal no reconocida.")
            answers = []
            emergency = False
            for heading, key, value in zip(headers, normalized, values):
                if "nombre de contacto de emergencia" in key:
                    emergency = True
                label = "Teléfono de contacto de emergencia" if emergency and key == "telefono de contacto" else heading.strip()
                answers.append({"pregunta": label, "respuesta": value})
            canonical = json.dumps(list(zip(normalized, values)), ensure_ascii=False, separators=(",", ":"))
            rows.append({
                "numero": number,
                "nombre": values[indexes["nombre completo"]],
                "correo": values[indexes["correo electronico"]],
                "telefono": values[indexes["telefono de contacto"]],
                "respondida_en": parsed.isoformat(),
                "respuestas": answers,
                "huella": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
            })
    except (csv.Error, StopIteration) as exc:
        raise ValueError("No se pudo leer el CSV. Revisa el formato y vuelve a exportarlo.") from exc
    if not rows:
        raise ValueError("El CSV no contiene respuestas.")
    return rows


def buscar_coincidencia(row, clientes):
    email = normalizar_correo(row["correo"])
    phone = normalizar_telefono(row["telefono"])
    email_ids = {c.pk for c in clientes if email and normalizar_correo(c.email) == email}
    phone_ids = {c.pk for c in clientes if phone and normalizar_telefono(c.telefono) == phone}
    if len(email_ids) > 1 or len(phone_ids) > 1:
        return None, "Contacto compartido por varias clientas"
    if email_ids and phone_ids and email_ids != phone_ids:
        return None, "Correo y teléfono corresponden a clientas distintas"
    matches = email_ids | phone_ids
    if len(matches) == 1:
        criterion = "Correo y teléfono" if email_ids and phone_ids else "Solo correo" if email_ids else "Solo teléfono"
        return next(iter(matches)), criterion
    return None, "Sin coincidencia de contacto"
