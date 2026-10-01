from datetime import date

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db import transaction
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.generic import CreateView, ListView, UpdateView, View
from django.utils.dateparse import parse_date

from mensualidades.models import ClientePlan

from .forms import AsistenciaFormSet, AsistenciaRowForm, HorarioEstudioForm, SesionForm
from .models import Asistencia, HorarioEstudio, RecuperacionClase, Sesion
from .horarios import horas_inicio_permitidas, periodos_clases


class SesionListView(LoginRequiredMixin, ListView):
    model = Sesion
    template_name = "asistencias/list.html"
    context_object_name = "sesiones"
    paginate_by = 12

    def get_queryset(self):
        selected_date = self.request.GET.get("fecha", "").strip()
        self.search_query = self.request.GET.get("q", "").strip()
        self.selected_status = self.request.GET.get("estado", "").strip()
        self.selected_block = self.request.GET.get("bloque", "").strip()
        self.show_all_dates = self.request.GET.get("todas") == "1" and not selected_date
        self.selected_date = None if self.show_all_dates else timezone.localdate()
        if selected_date:
            try:
                self.selected_date = date.fromisoformat(selected_date)
            except ValueError:
                self.selected_date = timezone.localdate()
                self.show_all_dates = False
        queryset = Sesion.objects.all().order_by("-fecha", "-hora")
        if self.selected_date:
            queryset = queryset.filter(fecha=self.selected_date).order_by("hora")
        if self.search_query:
            queryset = queryset.filter(
                Q(nombre__icontains=self.search_query)
                | Q(asistencias__cliente_plan__cliente__nombres__icontains=self.search_query)
                | Q(asistencias__cliente_plan__cliente__apellidos__icontains=self.search_query)
                | Q(asistencias__cliente_plan__cliente__rut__icontains=self.search_query.replace(".", "").replace(" ", ""))
            ).distinct()
        if self.selected_status in Asistencia.Estado.values:
            queryset = queryset.filter(asistencias__estado=self.selected_status).distinct()
        periods = periodos_clases()
        blocks = {key: (start, end) for key, (_, start, end) in zip(("matutino", "vespertino"), periods)}
        if self.selected_block in blocks:
            start, end = blocks[self.selected_block]
            queryset = queryset.filter(hora__gte=start, hora__lt=end)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        periods = periodos_clases()
        context.update({
            "page_title": "Asistencias",
            "selected_date": self.selected_date.isoformat() if self.selected_date else "",
            "today": timezone.localdate().isoformat(),
            "show_all_dates": self.show_all_dates,
            "search_query": self.search_query,
            "selected_status": self.selected_status,
            "selected_block": self.selected_block,
            "status_choices": Asistencia.Estado.choices,
            "block_choices": (
                ("matutino", periods[0][0].replace("Bloque ", "")),
                ("vespertino", periods[1][0].replace("Bloque ", "")),
            ),
        })
        return context


class SesionCreateView(LoginRequiredMixin, CreateView):
    model = Sesion
    form_class = SesionForm
    template_name = "asistencias/session_form.html"
    extra_context = {"page_title": "Nueva sesión"}

    def get_initial(self):
        initial = super().get_initial()
        initial["fecha"] = self.request.GET.get("fecha") or timezone.localdate()
        return initial

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Sesión creada. Ya puedes registrar la asistencia.")
        return response

    def get_success_url(self):
        return reverse("asistencias:roster", kwargs={"pk": self.object.pk})


class HorariosDisponiblesView(LoginRequiredMixin, View):
    def get(self, request):
        selected_date = parse_date(request.GET.get("fecha", ""))
        if selected_date is None:
            return JsonResponse({"error": "Selecciona una fecha válida."}, status=400)
        occupied = set(
            Sesion.objects.filter(fecha=selected_date).values_list("hora", flat=True)
        )
        allowed = set(horas_inicio_permitidas())
        groups = []
        for label, start, end in periodos_clases():
            slots = [
                {
                    "value": hour.isoformat(timespec="minutes"),
                    "label": f"{hour:%H:%M} hrs",
                    "available": hour not in occupied,
                }
                for hour in sorted(allowed)
                if start <= hour < end
            ]
            groups.append({"label": label, "slots": slots})
        return JsonResponse({"groups": groups})


class HorarioEstudioUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = HorarioEstudio
    form_class = HorarioEstudioForm
    template_name = "asistencias/horarios_form.html"
    extra_context = {"page_title": "Bloques horarios"}

    def test_func(self):
        return self.request.user.is_staff

    def get_object(self, queryset=None):
        horario, _ = HorarioEstudio.objects.get_or_create(pk=1)
        return horario

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Se actualizaron los bloques horarios del estudio.")
        return response

    def get_success_url(self):
        return reverse("asistencias:schedule_settings")


class SesionRosterView(LoginRequiredMixin, View):
    template_name = "asistencias/roster.html"

    def get_session(self, pk):
        return get_object_or_404(Sesion, pk=pk)

    def get_roster(self, sesion, include_already_attended=False):
        recorded_ids = sesion.asistencias.values_list("cliente_plan_id", flat=True)
        roster = ClientePlan.objects.filter(
            fecha_inicio__lte=sesion.fecha,
            fecha_fin__gte=sesion.fecha,
        ).filter(
            models_q_vigente_or_recorded(recorded_ids)
        ).select_related("cliente", "plan").annotate(
            present_count=Count(
                "asistencias",
                filter=Q(asistencias__estado__in=[Asistencia.Estado.PRESENTE, Asistencia.Estado.AUSENTE]),
                distinct=True,
            )
        ).order_by("cliente__apellidos", "cliente__nombres")
        if not include_already_attended:
            attended_ids = Asistencia.objects.filter(
                sesion__fecha=sesion.fecha,
                estado__in=(Asistencia.Estado.PRESENTE, Asistencia.Estado.AUSENTE, Asistencia.Estado.RECUPERACION),
            ).exclude(sesion=sesion).values_list("cliente_plan_id", flat=True)
            roster = roster.exclude(pk__in=attended_ids)
        return roster

    def get(self, request, pk):
        sesion = self.get_session(pk)
        roster = list(self.get_roster(sesion))
        current = {
            item.cliente_plan_id: item
            for item in sesion.asistencias.filter(cliente_plan__in=roster)
        }
        initial = [
            {
                "cliente_plan": subscription.pk,
                "estado": current[subscription.pk].estado if subscription.pk in current else Asistencia.Estado.PRESENTE,
                "observaciones": current[subscription.pk].observaciones if subscription.pk in current else "",
                "motivo_cancelacion": current[subscription.pk].motivo_cancelacion if subscription.pk in current else "",
                "fecha_aviso_cancelacion": current[subscription.pk].fecha_aviso_cancelacion if subscription.pk in current else "",
            }
            for subscription in roster
        ]
        formset = AsistenciaFormSet(initial=initial, form_kwargs={"cliente_planes": roster, "sesion": sesion})
        self.add_recovery_choices(formset, roster, sesion)
        return self.render_to_response(request, sesion, roster, formset)

    @staticmethod
    def add_recovery_choices(formset, roster, sesion):
        plan_ids = [plan.pk for plan in roster]
        pending = set(RecuperacionClase.objects.filter(
            estado=RecuperacionClase.Estado.PENDIENTE,
            asistencia_origen__cliente_plan_id__in=plan_ids,
            asistencia_origen__sesion__fecha__year=sesion.fecha.year,
            asistencia_origen__sesion__fecha__month=sesion.fecha.month,
        ).values_list("asistencia_origen__cliente_plan_id", flat=True))
        already_recovered = set(sesion.asistencias.filter(
            estado=Asistencia.Estado.RECUPERACION
        ).values_list("cliente_plan_id", flat=True))
        pending |= already_recovered
        used_here = already_recovered
        for form, subscription in zip(formset.forms, roster):
            choices = list(Asistencia.Estado.choices)
            if subscription.pk in pending:
                choices = [choice for choice in choices if choice[0] != Asistencia.Estado.RECUPERACION]
                label = "Recuperación ya registrada" if subscription.pk in used_here else "Recuperó (usar clase pendiente)"
                choices.insert(2, (Asistencia.Estado.RECUPERACION, label))
            else:
                choices = [choice for choice in choices if choice[0] != Asistencia.Estado.RECUPERACION]
            form.fields["estado"].choices = choices

    def post(self, request, pk):
        sesion = self.get_session(pk)
        # Conserva el roster completo en POST para rechazar una segunda asistencia
        # con un error claro, incluso si la pestaña quedó abierta.
        roster = list(self.get_roster(sesion, include_already_attended=True))
        formset = AsistenciaFormSet(
            request.POST,
            form_kwargs={"cliente_planes": roster, "sesion": sesion},
        )
        self.add_recovery_choices(formset, roster, sesion)
        if formset.is_valid():
            submitted_ids = [form.cleaned_data["cliente_plan"].pk for form in formset]
            expected_ids = [subscription.pk for subscription in roster]
            if len(submitted_ids) != len(set(submitted_ids)) or set(submitted_ids) != set(expected_ids):
                formset._non_form_errors = formset.error_class(["La lista de mensualidades cambió. Recarga la página e inténtalo otra vez."])
            else:
                invalid = False
                current = {
                    item.cliente_plan_id: item
                    for item in sesion.asistencias.select_related("recuperacion_generada", "recuperacion_utilizada")
                }
                for form in formset:
                    values = form.cleaned_data
                    plan = values["cliente_plan"]
                    state = values["estado"]
                    existing = current.get(plan.pk)
                    if existing:
                        recovery = getattr(existing, "recuperacion_generada", None)
                        used = recovery and recovery.estado == RecuperacionClase.Estado.UTILIZADA
                        if used and (
                            state != existing.estado
                            or values["motivo_cancelacion"] != existing.motivo_cancelacion
                            or values["fecha_aviso_cancelacion"] != existing.fecha_aviso_cancelacion
                        ):
                            form.add_error("estado", "Esta cancelación ya se recuperó; conserva el registro para mantener el historial.")
                            invalid = True
                    if state in (Asistencia.Estado.PRESENTE, Asistencia.Estado.AUSENTE, Asistencia.Estado.RECUPERACION):
                        duplicate_day = Asistencia.objects.filter(
                            cliente_plan=plan,
                            sesion__fecha=sesion.fecha,
                            estado__in=[Asistencia.Estado.PRESENTE, Asistencia.Estado.AUSENTE, Asistencia.Estado.RECUPERACION],
                        ).exclude(sesion=sesion).exists()
                        if duplicate_day:
                            form.add_error("estado", "La clienta ya tiene una asistencia registrada ese día.")
                            invalid = True
                    if state == Asistencia.Estado.RECUPERACION:
                        already_used_here = (
                            existing is not None
                            and hasattr(existing, "recuperacion_utilizada")
                            and existing.recuperacion_utilizada.estado == RecuperacionClase.Estado.UTILIZADA
                        )
                        eligible = already_used_here or RecuperacionClase.objects.filter(
                            asistencia_origen__cliente_plan=plan,
                            asistencia_origen__sesion__fecha__year=sesion.fecha.year,
                            asistencia_origen__sesion__fecha__month=sesion.fecha.month,
                            estado=RecuperacionClase.Estado.PENDIENTE,
                        ).exists()
                        if not eligible:
                            form.add_error("estado", "No hay una recuperación pendiente de esta mensualidad para el mes de la sesión.")
                            invalid = True
                if invalid:
                    return self.render_to_response(request, sesion, roster, formset)
                with transaction.atomic():
                    for form in formset:
                        values = form.cleaned_data
                        state = values["estado"]
                        asistencia, _ = Asistencia.objects.update_or_create(
                            sesion=sesion,
                            cliente_plan=values["cliente_plan"],
                            defaults={
                                "estado": state,
                                "observaciones": values["observaciones"],
                                "motivo_cancelacion": values["motivo_cancelacion"],
                                "fecha_aviso_cancelacion": values["fecha_aviso_cancelacion"],
                            },
                        )
                        if state == Asistencia.Estado.RECUPERACION:
                            ya_usada = RecuperacionClase.objects.filter(asistencia_recuperacion=asistencia, estado=RecuperacionClase.Estado.UTILIZADA).exists()
                            if not ya_usada:
                                recuperacion = RecuperacionClase.objects.select_for_update().get(
                                    asistencia_origen__cliente_plan=values["cliente_plan"],
                                    asistencia_origen__sesion__fecha__year=sesion.fecha.year,
                                    asistencia_origen__sesion__fecha__month=sesion.fecha.month,
                                    estado=RecuperacionClase.Estado.PENDIENTE,
                                )
                                recuperacion.estado = RecuperacionClase.Estado.UTILIZADA
                                recuperacion.asistencia_recuperacion = asistencia
                                recuperacion.save()
                        elif asistencia.genera_recuperacion:
                            recuperacion, _ = RecuperacionClase.objects.get_or_create(
                                asistencia_origen=asistencia,
                                defaults={"estado": RecuperacionClase.Estado.PENDIENTE},
                            )
                            if recuperacion.estado == RecuperacionClase.Estado.INVALIDADA:
                                recuperacion.estado = RecuperacionClase.Estado.PENDIENTE
                                recuperacion.save(update_fields=["estado"])
                        else:
                            RecuperacionClase.objects.filter(
                                asistencia_origen=asistencia,
                                estado=RecuperacionClase.Estado.PENDIENTE,
                            ).update(estado=RecuperacionClase.Estado.INVALIDADA)
                        if state == Asistencia.Estado.PRESENTE:
                            # Asistir en otro bloque reemplaza la clase cancelada ese día:
                            # no mantiene además un crédito de recuperación por la misma clase.
                            cancelaciones_previas = Asistencia.objects.filter(
                                cliente_plan=values["cliente_plan"],
                                sesion__fecha=sesion.fecha,
                                sesion__hora__lt=sesion.hora,
                                estado=Asistencia.Estado.CANCELO,
                            ).select_related("recuperacion_generada")
                            for cancelacion in cancelaciones_previas:
                                recovery = getattr(cancelacion, "recuperacion_generada", None)
                                if recovery and recovery.estado == RecuperacionClase.Estado.PENDIENTE:
                                    recovery.estado = RecuperacionClase.Estado.INVALIDADA
                                    recovery.save(update_fields=["estado"])
                messages.success(request, "Asistencia guardada. Presente y Ausente descuentan una clase; las recuperaciones pendientes se usan sin otro descuento.")
                return redirect("asistencias:roster", pk=sesion.pk)
        return self.render_to_response(request, sesion, roster, formset)

    def render_to_response(self, request, sesion, roster, formset):
        rows = []
        saved_attendance = {
            item.cliente_plan_id: item
            for item in sesion.asistencias.select_related("recuperacion_generada", "recuperacion_utilizada")
        }
        for index, form in enumerate(formset.forms):
            if request.method == "POST":
                subscription_id = request.POST.get(f"{formset.prefix}-{index}-cliente_plan")
                subscription = next((item for item in roster if str(item.pk) == str(subscription_id)), None)
            else:
                subscription = roster[index]
            if subscription:
                attendance = saved_attendance.get(subscription.pk)
                recovery = getattr(attendance, "recuperacion_generada", None) if attendance else None
                used_recovery = getattr(attendance, "recuperacion_utilizada", None) if attendance else None
                rows.append({
                    "form": form,
                    "subscription": subscription,
                    "recovery_state": (
                        "Utilizada" if used_recovery and used_recovery.estado == RecuperacionClase.Estado.UTILIZADA
                        else recovery.get_estado_display() if recovery else ""
                    ),
                })
        return render(request, self.template_name, {
            "page_title": "Asistencia de hoy" if sesion.fecha == timezone.localdate() else "Asistencia",
            "heading": "Asistencia de hoy" if sesion.fecha == timezone.localdate() else "Asistencia",
            "sesion": sesion,
            "sesiones_del_dia": Sesion.objects.filter(fecha=sesion.fecha).order_by("hora"),
            "rows": rows,
            "formset": formset,
            "total_alumnas": len(roster),
            "now_local": timezone.localtime().strftime("%Y-%m-%dT%H:%M"),
        })


def models_q_vigente_or_recorded(recorded_ids):
    from django.db.models import Q

    return Q(estado=ClientePlan.Estado.VIGENTE) | Q(pk__in=recorded_ids)
