from pathlib import Path

from django import forms
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import ValidationError as CoreValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.cache import never_cache

from .fichas_medicas import buscar_coincidencia, leer_csv
from .models import Cliente, FichaMedica, ImportacionFichaMedica, SolicitudAltaCliente
from .solicitudes import crear_solicitud_alta
from .validators import RutChilenoValidator, normalize_rut


def puede_importar(user):
    return user.is_staff or user.has_perm("clientes.add_fichamedica")


def puede_ver(user):
    return user.is_staff or user.has_perm("clientes.view_fichamedica")


class ArchivoMedicoForm(forms.Form):
    archivo = forms.FileField(label="CSV de respuestas", widget=forms.ClearableFileInput(attrs={
        "accept": ".csv", "class": "form-control",
    }))

    def clean_archivo(self):
        archivo = self.cleaned_data["archivo"]
        if not archivo.name.lower().endswith(".csv"):
            raise forms.ValidationError("Selecciona un archivo CSV exportado de Google Forms o Sheets.")
        try:
            self.filas = leer_csv(archivo)
        except ValueError as exc:
            raise forms.ValidationError(str(exc)) from exc
        return archivo


class AccesoImportacionMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return puede_importar(self.request.user)


class SolicitudAltaForm(forms.Form):
    cliente_existente = forms.ModelChoiceField(
        queryset=Cliente.objects.none(), required=False, label="Vincular a una clienta existente",
        help_text="Si la persona ya está registrada, selecciónala. Si es nueva, puedes completar su RUT después.",
    )
    nombres = forms.CharField(required=False, max_length=120, label="Nombres")
    apellidos = forms.CharField(required=False, max_length=120, label="Apellidos")
    rut = forms.CharField(required=False, max_length=12, validators=[RutChilenoValidator()], label="RUT")
    email = forms.EmailField(required=False, label="Correo electrónico")
    telefono = forms.CharField(required=False, max_length=30, label="Teléfono")
    motivo_vinculo = forms.CharField(required=False, max_length=2000, label="Motivo del vínculo manual")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["cliente_existente"].queryset = Cliente.objects.all()
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control" if not isinstance(field.widget, forms.Select) else "form-select"
        self.fields["rut"].widget.attrs.update({
            "placeholder": "12.345.678-5", "inputmode": "text", "maxlength": 12,
            "autocomplete": "off", "data-input-format": "rut",
        })
        self.fields["telefono"].widget.attrs.update({
            "placeholder": "+56 9 1234 5678", "type": "tel", "autocomplete": "tel",
            "data-input-format": "telefono",
        })

    def clean(self):
        data = super().clean()
        if data.get("cliente_existente"):
            if not data.get("motivo_vinculo", "").strip():
                self.add_error("motivo_vinculo", "Explica por qué se vincula esta respuesta con la clienta seleccionada.")
        else:
            for name, label in (("nombres", "los nombres"), ("apellidos", "los apellidos"), ("email", "el correo")):
                if not data.get(name):
                    self.add_error(name, f"Completa {label} para crear el perfil de clienta.")
        if data.get("rut"):
            try:
                data["rut"] = normalize_rut(data["rut"])
            except CoreValidationError:
                self.add_error("rut", "Ingresa un RUT chileno válido.")
        return data


@method_decorator(never_cache, name="dispatch")
class ImportarFichaMedicaView(AccesoImportacionMixin, View):
    def get(self, request):
        return self.render(request, ArchivoMedicoForm())

    def post(self, request):
        form = ArchivoMedicoForm(request.POST, request.FILES)
        if form.is_valid():
            lote = ImportacionFichaMedica.objects.create(
                archivo=Path(form.cleaned_data["archivo"].name).name[:255],
                creada_por=request.user, filas_pendientes=form.filas,
            )
            return redirect("clientes:medical_preview", pk=lote.pk)
        return self.render(request, form)

    def render(self, request, form):
        return render(request, "clientes/medical_import.html", {
            "page_title": "Importar fichas médicas", "form": form,
            "importaciones": ImportacionFichaMedica.objects.filter(creada_por=request.user)[:20],
        })


@method_decorator(never_cache, name="dispatch")
class RevisarFichaMedicaView(AccesoImportacionMixin, View):
    def get(self, request, pk):
        lote = get_object_or_404(ImportacionFichaMedica, pk=pk, creada_por=request.user)
        return self.render(request, lote)

    def post(self, request, pk):
        if request.POST.get("accion") != "confirmar":
            return HttpResponseBadRequest("Acción no válida.")
        errors = []
        with transaction.atomic():
            lote = get_object_or_404(
                ImportacionFichaMedica.objects.select_for_update(), pk=pk, creada_por=request.user,
            )
            clientes = list(Cliente.objects.select_for_update().all())
            clients_by_id = {str(c.pk): c for c in clientes}
            saved = set(FichaMedica.objects.values_list("huella", flat=True))
            saved_requests = set(SolicitudAltaCliente.objects.values_list("huella", flat=True))
            selections = []
            for row in lote.filas_pendientes:
                selected = request.POST.get(f"cliente_{row['numero']}", "")
                request_new = request.POST.get(f"solicitud_{row['numero']}") == "1"
                if row["huella"] in saved or row["huella"] in saved_requests:
                    continue
                if request_new:
                    try:
                        validate_email(row["correo"])
                    except CoreValidationError:
                        errors.append(f"Respuesta {row['numero']}: para crear una solicitud se necesita un correo válido.")
                        continue
                    selections.append((row, None, "Solicitud", ""))
                    continue
                if not selected:
                    continue
                client = clients_by_id.get(selected)
                if client is None:
                    errors.append(f"Respuesta {row['numero']}: selecciona una clienta válida.")
                    continue
                suggestion, criterion = buscar_coincidencia(row, clientes)
                reason = request.POST.get(f"motivo_{row['numero']}", "").strip()
                manual = suggestion != client.pk
                if manual and not reason:
                    errors.append(f"Respuesta {row['numero']}: indica el motivo de la asociación manual.")
                elif len(reason) > 2000:
                    errors.append(f"Respuesta {row['numero']}: el motivo supera los 2000 caracteres.")
                else:
                    selections.append((row, client, "Manual" if manual else criterion, reason))
            if not errors and not selections:
                errors.append("Selecciona al menos una respuesta nueva para importar.")
            if not errors:
                count = 0
                requests = 0
                for row, client, criterion, reason in selections:
                    if client is None:
                        _, created = crear_solicitud_alta(importacion=lote, fila=row, solicitante=request.user)
                        requests += int(created)
                        continue
                    _, created = FichaMedica.objects.get_or_create(huella=row["huella"], defaults={
                        "cliente": client, "importacion": lote,
                        "respuestas": row["respuestas"], "respondida_en": parse_datetime(row["respondida_en"]),
                        "asociada_por": request.user, "criterio_asociacion": criterion,
                        "motivo_asociacion": reason,
                    })
                    count += int(created)
                imported = set(FichaMedica.objects.values_list("huella", flat=True))
                imported |= set(SolicitudAltaCliente.objects.values_list("huella", flat=True))
                lote.filas_pendientes = [r for r in lote.filas_pendientes if r["huella"] not in imported]
                lote.save(update_fields=["filas_pendientes"])
                messages.success(request, f"Se importaron {count} fichas y se generaron {requests} solicitudes de alta pendientes de aprobación.")
                return redirect("clientes:medical_preview", pk=lote.pk)
        return self.render(request, lote, errors)

    def render(self, request, lote, errors=None):
        clientes = list(Cliente.objects.all())
        saved = set(FichaMedica.objects.values_list("huella", flat=True))
        saved |= set(SolicitudAltaCliente.objects.values_list("huella", flat=True))
        rows = []
        seen = set()
        for source in lote.filas_pendientes:
            row = dict(source)
            suggestion, criterion = buscar_coincidencia(row, clientes)
            row["duplicada"] = row["huella"] in saved or row["huella"] in seen
            seen.add(row["huella"])
            row["criterio"] = "Respuesta ya importada o solicitud existente" if row["duplicada"] else criterion
            row["sugerida"] = str(suggestion or "")
            row["seleccionada"] = request.POST.get(f"cliente_{row['numero']}", row["sugerida"])
            row["motivo"] = request.POST.get(f"motivo_{row['numero']}", "")
            default_request = "1" if suggestion is None and row["correo"].strip() else ""
            row["crear_solicitud"] = request.POST.get(
                f"solicitud_{row['numero']}", default_request
            ) == "1"
            row["puede_solicitar"] = bool(row["correo"].strip())
            rows.append(row)
        return render(request, "clientes/medical_preview.html", {
            "page_title": "Revisar fichas médicas", "importacion": lote,
            "filas": rows, "clientas": clientes, "errores": errors or [],
        })


@method_decorator(never_cache, name="dispatch")
class SolicitudesAltaView(AccesoImportacionMixin, View):
    def get(self, request):
        solicitudes = SolicitudAltaCliente.objects.select_related("cliente", "creada_por", "revisada_por")
        estado = request.GET.get("estado", SolicitudAltaCliente.Estado.PENDIENTE)
        if estado in SolicitudAltaCliente.Estado.values:
            solicitudes = solicitudes.filter(estado=estado)
        return render(request, "clientes/medical_requests.html", {
            "page_title": "Solicitudes de alta",
            "solicitudes": solicitudes[:100],
            "estado_seleccionado": estado,
            "pendientes": SolicitudAltaCliente.objects.filter(estado=SolicitudAltaCliente.Estado.PENDIENTE).count(),
        })


@method_decorator(never_cache, name="dispatch")
class ResolverSolicitudAltaView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        return self.request.user.is_staff and puede_ver(self.request.user)

    def get(self, request, pk):
        solicitud = get_object_or_404(SolicitudAltaCliente.objects.select_related("importacion"), pk=pk)
        form = self.form_for(solicitud)
        return self.render(request, solicitud, form)

    def post(self, request, pk):
        if request.POST.get("accion") not in {"aprobar", "rechazar"}:
            return HttpResponseBadRequest("Acción no válida.")
        with transaction.atomic():
            solicitud = get_object_or_404(
                SolicitudAltaCliente.objects.select_for_update().select_related("importacion"), pk=pk
            )
            if solicitud.estado != SolicitudAltaCliente.Estado.PENDIENTE:
                messages.info(request, "Esta solicitud ya fue resuelta.")
                return redirect("clientes:medical_requests")
            if request.POST["accion"] == "rechazar":
                motivo = request.POST.get("resolucion", "").strip()
                if not motivo:
                    form = self.form_for(solicitud, request.POST)
                    form.add_error(None, "Indica el motivo del rechazo para dejar trazabilidad.")
                    return self.render(request, solicitud, form)
                solicitud.estado = SolicitudAltaCliente.Estado.RECHAZADA
                solicitud.resolucion = motivo[:4000]
                solicitud.revisada_por = request.user
                solicitud.revisada_en = timezone.now()
                solicitud.save(update_fields=["estado", "resolucion", "revisada_por", "revisada_en"])
                messages.success(request, "Solicitud rechazada; no se creó el perfil de clienta ni se vinculó su ficha médica.")
                return redirect("clientes:medical_requests")

            form = self.form_for(solicitud, request.POST)
            if not form.is_valid():
                messages.error(request, "La solicitud sigue pendiente. Revisa los campos indicados y vuelve a aprobarla.")
                return self.render(request, solicitud, form)
            client = self.aprobar(solicitud, form, request.user)
            if client is None:
                return self.render(request, solicitud, form)
        messages.success(request, f"Solicitud aprobada para {client}. {solicitud.resolucion}")
        return redirect("clientes:medical_requests")


    @staticmethod
    def aprobar(solicitud, form, user):
        data = form.cleaned_data
        email = (data.get("email") or "").strip().casefold()
        client = data.get("cliente_existente")
        perfil_existente = client is not None
        if not client:
            if data.get("rut") and Cliente.objects.filter(rut=data["rut"]).exists():
                form.add_error("rut", "Ese RUT ya pertenece a una clienta; selecciona el perfil existente.")
                return None
            client = Cliente.objects.create(
                nombres=data["nombres"].strip(), apellidos=data["apellidos"].strip(),
                rut=data.get("rut") or None, email=email, telefono=data.get("telefono", "").strip(),
            )
        if not client.email:
            client.email = email
        if not client.telefono and data.get("telefono"):
            client.telefono = data["telefono"].strip()
        client.save(update_fields=["email", "telefono", "updated_at"])
        FichaMedica.objects.create(
            cliente=client, importacion=solicitud.importacion,
            respuestas=solicitud.respuestas, respondida_en=solicitud.respondida_en,
            huella=solicitud.huella, asociada_por=user,
            criterio_asociacion="Solicitud aprobada",
            motivo_asociacion=data.get("motivo_vinculo", "").strip(),
        )
        solicitud.estado = SolicitudAltaCliente.Estado.APROBADA
        solicitud.cliente = client
        solicitud.revisada_por = user
        solicitud.revisada_en = timezone.now()
        solicitud.resolucion = (
            "Ficha médica vinculada al perfil existente."
            if perfil_existente else "Perfil creado y ficha médica vinculada."
        )
        solicitud.save(update_fields=["estado", "cliente", "revisada_por", "revisada_en", "resolucion"])
        return client

    @staticmethod
    def form_for(solicitud, data=None):
        words = solicitud.nombre_reportado.split()
        initial = {
            "nombres": " ".join(words[:-1]) if len(words) > 1 else solicitud.nombre_reportado,
            "apellidos": words[-1] if len(words) > 1 else "",
            "email": solicitud.email_reportado,
            "telefono": solicitud.telefono_reportado,
            "rut": next((
                respuesta["respuesta"] for respuesta in solicitud.respuestas
                if respuesta["pregunta"].strip().casefold() == "rut"
            ), ""),
        }
        return SolicitudAltaForm(data=data, initial=initial)

    @staticmethod
    def render(request, solicitud, form):
        return render(request, "clientes/medical_request_review.html", {
            "page_title": "Revisar solicitud de alta",
            "solicitud": solicitud, "form": form,
        })


@method_decorator(never_cache, name="dispatch")
class AprobarSolicitudesAltaView(ResolverSolicitudAltaView):
    http_method_names = ["post"]

    def post(self, request):
        seleccion = request.POST.getlist("solicitudes")
        if not seleccion:
            messages.info(request, "Selecciona al menos una solicitud.")
            return redirect("clientes:medical_requests")
        if len(seleccion) > 100 or any(
            not pk.isascii() or not pk.isdigit() or len(pk) > 18 for pk in seleccion
        ):
            return HttpResponseBadRequest("Selección de solicitudes no válida.")

        aprobadas = 0
        ids = sorted({int(pk) for pk in seleccion})
        for pk in ids:
            try:
                with transaction.atomic():
                    solicitud = SolicitudAltaCliente.objects.select_for_update().filter(
                        pk=pk, estado=SolicitudAltaCliente.Estado.PENDIENTE,
                    ).first()
                    if not solicitud:
                        continue
                    datos = self.form_for(solicitud).initial
                    form = self.form_for(solicitud, datos)
                    if not form.is_valid():
                        continue
                    clientas = Cliente.objects.all()
                    _, criterio = buscar_coincidencia({
                        "correo": datos["email"], "telefono": datos["telefono"],
                    }, clientas)
                    if criterio != "Sin coincidencia de contacto" or clientas.filter(
                        nombres__iexact=datos["nombres"], apellidos__iexact=datos["apellidos"],
                    ).exists():
                        continue
                    if self.aprobar(solicitud, form, request.user) is None:
                        continue
                aprobadas += 1
            except (CoreValidationError, IntegrityError):
                continue

        if aprobadas:
            messages.success(request, f"Solicitudes aprobadas: {aprobadas}.")
        if aprobadas < len(ids):
            messages.warning(
                request,
                f"Solicitudes omitidas: {len(ids) - aprobadas}. "
                "Revisa individualmente las que sigan pendientes por datos incompletos o coincidencias con perfiles.",
            )
        return redirect("clientes:medical_requests")
