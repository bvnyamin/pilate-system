(function () {
    "use strict";

    const diasSemana = ["Lu", "Ma", "Mi", "Ju", "Vi", "Sa", "Do"];
    const meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"];
    let pickerId = 0;
    const instances = new WeakMap();

    function leerIso(value) {
        const match = String(value || "").match(/^(\d{4})-(\d{2})-(\d{2})$/);
        if (!match) return null;
        const [, year, month, day] = match.map(Number);
        const date = new Date(year, month - 1, day);
        return date.getFullYear() === year && date.getMonth() === month - 1 && date.getDate() === day ? date : null;
    }

    function iso(date) {
        return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
    }

    function mostrar(date) {
        return `${String(date.getDate()).padStart(2, "0")}-${String(date.getMonth() + 1).padStart(2, "0")}-${date.getFullYear()}`;
    }

    function parsear(text) {
        const value = text.trim();
        if (!value) return { empty: true, date: null };
        let match = value.match(/^(\d{1,2})[./-](\d{1,2})[./-](\d{4})$/);
        if (match) return validarFecha(Number(match[3]), Number(match[2]), Number(match[1]));
        match = value.match(/^(\d{4})-(\d{1,2})-(\d{1,2})$/);
        if (match) return validarFecha(Number(match[1]), Number(match[2]), Number(match[3]));
        return { date: null, error: true };
    }

    function validarFecha(year, month, day) {
        if (year < 1900 || year > 9999 || month < 1 || month > 12 || day < 1 || day > 31) {
            return { date: null, error: true };
        }
        const date = new Date(year, month - 1, day);
        if (date.getFullYear() !== year || date.getMonth() !== month - 1 || date.getDate() !== day) {
            return { date: null, error: true };
        }
        return { date, error: false };
    }

    function inicioDelDia(date) {
        return new Date(date.getFullYear(), date.getMonth(), date.getDate());
    }

    function enhance(source) {
        if (instances.has(source) || source.dataset.nativeDate === "true") return;

        const pickerIdValue = ++pickerId;
        const required = source.required;
        const minimum = source.min || "";
        const maximum = source.max || "";
        const originalId = source.id;
        const labels = Array.from(source.labels || []);
        const currentDate = leerIso(source.value);
        const wrapper = document.createElement("div");
        wrapper.className = "aldra-date-picker";
        wrapper.dataset.aldraDatePicker = "true";

        const input = document.createElement("input");
        input.type = "text";
        input.className = "aldra-date-input";
        input.inputMode = "numeric";
        input.autocomplete = "off";
        input.autocapitalize = "off";
        input.spellcheck = false;
        input.placeholder = "dd-mm-aaaa";
        input.setAttribute("aria-haspopup", "dialog");
        input.setAttribute("aria-expanded", "false");
        input.setAttribute("aria-controls", `aldra-calendar-${pickerIdValue}`);
        input.setAttribute("aria-required", String(required));
        input.setAttribute("aria-invalid", "false");
        input.required = required;
        input.disabled = source.disabled;
        input.value = currentDate ? mostrar(currentDate) : "";
        if (source.getAttribute("aria-label")) input.setAttribute("aria-label", source.getAttribute("aria-label"));
        else if (!labels.length) input.setAttribute("aria-label", source.name || "Fecha");
        if (source.getAttribute("aria-describedby")) input.setAttribute("aria-describedby", source.getAttribute("aria-describedby"));

        const calendarButton = document.createElement("button");
        calendarButton.className = "aldra-calendar-trigger";
        calendarButton.type = "button";
        calendarButton.setAttribute("aria-label", "Abrir calendario");
        calendarButton.setAttribute("aria-controls", `aldra-calendar-${pickerIdValue}`);
        calendarButton.innerHTML = '<i class="bi bi-calendar3" aria-hidden="true"></i>';
        calendarButton.disabled = source.disabled;

        const popover = document.createElement("section");
        popover.className = "aldra-calendar-popover";
        popover.id = `aldra-calendar-${pickerIdValue}`;
        popover.setAttribute("role", "dialog");
        popover.setAttribute("aria-label", "Seleccionar fecha");
        popover.hidden = true;

        source.parentNode.insertBefore(wrapper, source);
        wrapper.append(input, calendarButton, source);
        document.body.append(popover);
        source.classList.add("aldra-date-source");
        source.dataset.dateMin = minimum;
        source.dataset.dateMax = maximum;
        source.type = "hidden";
        source.required = false;
        source.removeAttribute("min");
        source.removeAttribute("max");
        source.tabIndex = -1;
        source.setAttribute("aria-hidden", "true");

        if (originalId) {
            wrapper.dataset.sourceId = originalId;
            input.id = `aldra-date-input-${pickerIdValue}`;
            document.querySelectorAll(`label[for="${CSS.escape(originalId)}"]`).forEach((label) => {
                label.htmlFor = input.id;
            });
        } else if (!labels.length) {
            input.id = `aldra-date-input-${pickerIdValue}`;
        }

        let isOpen = false;
        let suppressOpenOnFocus = false;
        let viewDate = currentDate || new Date();
        let focusedDate = currentDate || inicioDelDia(new Date());
        let positionListenersActive = false;

        function posicionarPopover() {
            if (!isOpen || popover.hidden) return;
            const bounds = input.getBoundingClientRect();
            const margin = 12;
            const viewportLeft = window.visualViewport?.offsetLeft || 0;
            const viewportWidth = window.visualViewport?.width || window.innerWidth;
            const width = Math.min(288, viewportWidth - margin * 2);
            popover.style.width = `${width}px`;
            const height = popover.getBoundingClientRect().height;
            const viewportHeight = window.visualViewport?.height || window.innerHeight;
            const viewportTop = window.visualViewport?.offsetTop || 0;
            const spaceBelow = viewportTop + viewportHeight - bounds.bottom - margin;
            const spaceAbove = bounds.top - viewportTop - margin;
            const opensAbove = spaceBelow < Math.min(height, 330) && spaceAbove > spaceBelow;
            const availableHeight = Math.max(180, (opensAbove ? spaceAbove : spaceBelow));
            const top = opensAbove
                ? Math.max(viewportTop + margin, bounds.top - Math.min(height, availableHeight) - 7)
                : Math.min(bounds.bottom + 7, viewportTop + viewportHeight - margin - Math.min(height, availableHeight));
            const left = Math.max(viewportLeft + margin, Math.min(bounds.left, viewportLeft + viewportWidth - width - margin));
            popover.style.left = `${left}px`;
            popover.style.top = `${top}px`;
            popover.style.maxHeight = `${Math.max(140, Math.min(360, availableHeight))}px`;
            popover.classList.toggle("opens-above", opensAbove);
        }

        function activarSeguimientoPosicion() {
            if (positionListenersActive) return;
            positionListenersActive = true;
            window.addEventListener("resize", posicionarPopover);
            window.addEventListener("scroll", posicionarPopover, true);
            window.visualViewport?.addEventListener("resize", posicionarPopover);
            window.visualViewport?.addEventListener("scroll", posicionarPopover);
        }

        function desactivarSeguimientoPosicion() {
            if (!positionListenersActive) return;
            positionListenersActive = false;
            window.removeEventListener("resize", posicionarPopover);
            window.removeEventListener("scroll", posicionarPopover, true);
            window.visualViewport?.removeEventListener("resize", posicionarPopover);
            window.visualViewport?.removeEventListener("scroll", posicionarPopover);
        }

        function focusWithoutOpening() {
            if (document.activeElement === input) return;
            suppressOpenOnFocus = true;
            input.focus({ preventScroll: true });
        }

        function limiteValido(date) {
            const value = iso(date);
            return (!minimum || value >= minimum) && (!maximum || value <= maximum);
        }

        function mesDentroLimites(date) {
            const monthValue = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
            return (!minimum || monthValue >= minimum.slice(0, 7)) && (!maximum || monthValue <= maximum.slice(0, 7));
        }

        function actualizarValidez(parsed = parsear(input.value)) {
            let message = "";
            if (!parsed.empty && parsed.error) message = "Escribe la fecha como dd-mm-aaaa.";
            else if (parsed.date && !limiteValido(parsed.date)) message = "La fecha está fuera del rango permitido.";
            else if (required && (parsed.empty || !parsed.date)) message = "Ingresa una fecha para continuar.";
            input.setCustomValidity(message);
            input.setAttribute("aria-invalid", String(Boolean(message)));
            input.classList.toggle("is-invalid", source.classList.contains("is-invalid") || Boolean(message));
            return !message;
        }

        function propagarCambio(date) {
            source.value = date ? iso(date) : "";
            source.dispatchEvent(new Event("input", { bubbles: true }));
            source.dispatchEvent(new Event("change", { bubbles: true }));
        }

        function sincronizarDesdeSource() {
            const date = leerIso(source.value);
            input.value = date ? mostrar(date) : "";
            input.disabled = source.disabled;
            calendarButton.disabled = source.disabled;
            input.classList.toggle("is-invalid", source.classList.contains("is-invalid"));
            if (date) {
                viewDate = new Date(date.getFullYear(), date.getMonth(), 1);
                focusedDate = date;
            }
            actualizarValidez();
            if (isOpen) dibujarCalendario();
        }

        function cerrar(restaurar = false) {
            isOpen = false;
            popover.hidden = true;
            wrapper.classList.remove("is-open");
            popover.classList.remove("opens-above");
            desactivarSeguimientoPosicion();
            input.setAttribute("aria-expanded", "false");
            calendarButton.setAttribute("aria-expanded", "false");
            if (restaurar) sincronizarDesdeSource();
        }

        function seleccionar(date) {
            if (!limiteValido(date) || source.disabled) return;
            input.value = mostrar(date);
            actualizarValidez({ date, empty: false, error: false });
            propagarCambio(date);
            cerrar();
            focusWithoutOpening();
        }

        function dibujarCalendario() {
            popover.replaceChildren();
            const header = document.createElement("header");
            header.className = "aldra-calendar-header";
            const previous = document.createElement("button");
            previous.type = "button";
            previous.className = "aldra-calendar-nav";
            previous.setAttribute("aria-label", "Mes anterior");
            previous.innerHTML = '<i class="bi bi-chevron-left" aria-hidden="true"></i>';
            const title = document.createElement("h3");
            title.className = "aldra-calendar-title";
            title.id = `aldra-calendar-title-${pickerIdValue}`;
            title.setAttribute("aria-live", "polite");
            title.textContent = `${meses[viewDate.getMonth()]} ${viewDate.getFullYear()}`;
            const next = document.createElement("button");
            next.type = "button";
            next.className = "aldra-calendar-nav";
            next.setAttribute("aria-label", "Mes siguiente");
            next.innerHTML = '<i class="bi bi-chevron-right" aria-hidden="true"></i>';
            header.append(previous, title, next);
            popover.setAttribute("aria-labelledby", title.id);

            const grid = document.createElement("div");
            grid.className = "aldra-calendar-grid";
            grid.setAttribute("role", "grid");
            const weekdayHeader = document.createElement("div");
            weekdayHeader.className = "aldra-calendar-weekdays";
            weekdayHeader.setAttribute("role", "row");
            diasSemana.forEach((day) => {
                const cell = document.createElement("span");
                cell.setAttribute("role", "columnheader");
                cell.textContent = day;
                weekdayHeader.append(cell);
            });
            grid.append(weekdayHeader);

            const days = document.createElement("div");
            days.className = "aldra-calendar-days";
            days.setAttribute("role", "rowgroup");
            const year = viewDate.getFullYear();
            const month = viewDate.getMonth();
            const first = new Date(year, month, 1);
            const offset = (first.getDay() + 6) % 7;
            const gridStart = new Date(year, month, 1 - offset);
            const selectedValue = source.value;
            const todayValue = iso(new Date());

            const weeksToShow = Math.ceil((offset + new Date(year, month + 1, 0).getDate()) / 7);
            for (let index = 0; index < weeksToShow * 7; index += 1) {
                const date = new Date(gridStart.getFullYear(), gridStart.getMonth(), gridStart.getDate() + index);
                const cell = document.createElement("div");
                cell.setAttribute("role", "gridcell");
                const dayButton = document.createElement("button");
                dayButton.type = "button";
                dayButton.className = "aldra-calendar-day";
                dayButton.dataset.date = iso(date);
                dayButton.textContent = String(date.getDate());
                dayButton.setAttribute("aria-label", new Intl.DateTimeFormat("es-CL", { dateStyle: "long" }).format(date));
                dayButton.setAttribute("aria-pressed", String(iso(date) === selectedValue));
                dayButton.tabIndex = iso(date) === iso(focusedDate) ? 0 : -1;
                dayButton.disabled = !limiteValido(date);
                if (date.getMonth() !== month) dayButton.classList.add("is-outside-month");
                if (iso(date) === selectedValue) dayButton.classList.add("is-selected");
                if (iso(date) === todayValue) dayButton.classList.add("is-today");
                cell.append(dayButton);
                days.append(cell);
            }
            grid.append(days);

            const footer = document.createElement("footer");
            footer.className = "aldra-calendar-footer";
            const clear = document.createElement("button");
            clear.type = "button";
            clear.className = "aldra-calendar-quiet-action";
            clear.textContent = "Borrar";
            clear.disabled = required;
            const today = document.createElement("button");
            today.type = "button";
            today.className = "aldra-calendar-today-action";
            today.textContent = "Hoy";
            const todayDate = inicioDelDia(new Date());
            today.disabled = !limiteValido(todayDate);
            footer.append(clear, today);
            popover.append(header, grid, footer);

            previous.disabled = year <= 1900 && month === 0 || !mesDentroLimites(new Date(year, month - 1, 1));
            next.disabled = year >= 9999 && month === 11 || !mesDentroLimites(new Date(year, month + 1, 1));
            previous.addEventListener("click", () => cambiarMes(-1));
            next.addEventListener("click", () => cambiarMes(1));
            clear.addEventListener("click", () => {
                if (required) return;
                input.value = "";
                actualizarValidez({ empty: true, date: null, error: false });
                propagarCambio(null);
                cerrar();
                focusWithoutOpening();
            });
            today.addEventListener("click", () => seleccionar(todayDate));
        }

        function cambiarMes(delta) {
            const nextMonth = new Date(viewDate.getFullYear(), viewDate.getMonth() + delta, 1);
            if (!mesDentroLimites(nextMonth)) return;
            viewDate = nextMonth;
            focusedDate = new Date(viewDate.getFullYear(), viewDate.getMonth(), 1);
            dibujarCalendario();
        }

        function abrir() {
            if (source.disabled) return;
            const parsed = parsear(input.value);
            const date = parsed.date || leerIso(source.value) || new Date();
            viewDate = new Date(date.getFullYear(), date.getMonth(), 1);
            focusedDate = parsed.date || leerIso(source.value) || inicioDelDia(new Date());
            isOpen = true;
            wrapper.classList.add("is-open");
            popover.hidden = false;
            input.setAttribute("aria-expanded", "true");
            calendarButton.setAttribute("aria-expanded", "true");
            dibujarCalendario();
            activarSeguimientoPosicion();
            posicionarPopover();
        }

        input.addEventListener("input", () => {
            const parsed = parsear(input.value);
            if (parsed.date && limiteValido(parsed.date)) {
                actualizarValidez(parsed);
                propagarCambio(parsed.date);
                if (isOpen) {
                    viewDate = new Date(parsed.date.getFullYear(), parsed.date.getMonth(), 1);
                    focusedDate = parsed.date;
                    dibujarCalendario();
                }
            } else if (parsed.empty) {
                actualizarValidez(parsed);
                propagarCambio(null);
            } else {
                actualizarValidez(parsed);
            }
        });
        input.addEventListener("change", () => {
            const parsed = parsear(input.value);
            if (parsed.date && limiteValido(parsed.date)) input.value = mostrar(parsed.date);
            actualizarValidez(parsed);
        });
        input.addEventListener("focus", () => {
            if (suppressOpenOnFocus) suppressOpenOnFocus = false;
            else abrir();
            input.select();
        });
        input.addEventListener("click", () => input.select());
        input.addEventListener("keydown", (event) => {
            if (event.key === "Escape" && isOpen) {
                event.preventDefault();
                cerrar(true);
            } else if ((event.key === "ArrowDown" || event.key === "Enter") && !isOpen) {
                event.preventDefault();
                abrir();
            }
        });
        calendarButton.addEventListener("click", () => {
            if (isOpen) cerrar();
            else abrir();
        });
        popover.addEventListener("click", (event) => {
            const dayButton = event.target.closest("[data-date]");
            if (dayButton && !dayButton.disabled) seleccionar(leerIso(dayButton.dataset.date));
        });
        popover.addEventListener("keydown", (event) => {
            if (event.key === "Escape") {
                event.preventDefault();
                cerrar();
                focusWithoutOpening();
                return;
            }
            const dayButton = event.target.closest("[data-date]");
            if (!dayButton) return;
            const currentDate = leerIso(dayButton.dataset.date);
            let delta = 0;
            if (event.key === "ArrowRight") delta = 1;
            else if (event.key === "ArrowLeft") delta = -1;
            else if (event.key === "ArrowDown") delta = 7;
            else if (event.key === "ArrowUp") delta = -7;
            else if (event.key === "Home") delta = -((currentDate.getDay() + 6) % 7);
            else if (event.key === "End") delta = 6 - ((currentDate.getDay() + 6) % 7);
            else if (event.key === "PageDown" || event.key === "PageUp") {
                const monthDelta = (event.key === "PageDown" ? 1 : -1) * (event.shiftKey ? 12 : 1);
                const targetMonth = new Date(currentDate.getFullYear(), currentDate.getMonth() + monthDelta, 1);
                const targetDay = Math.min(currentDate.getDate(), new Date(targetMonth.getFullYear(), targetMonth.getMonth() + 1, 0).getDate());
                const nextDate = new Date(targetMonth.getFullYear(), targetMonth.getMonth(), targetDay);
                event.preventDefault();
                focusedDate = nextDate;
                viewDate = new Date(nextDate.getFullYear(), nextDate.getMonth(), 1);
                dibujarCalendario();
                popover.querySelector(`[data-date="${iso(nextDate)}"]`)?.focus();
                return;
            }
            else return;
            event.preventDefault();
            const nextDate = new Date(currentDate.getFullYear(), currentDate.getMonth(), currentDate.getDate() + delta);
            focusedDate = nextDate;
            viewDate = new Date(nextDate.getFullYear(), nextDate.getMonth(), 1);
            dibujarCalendario();
            popover.querySelector(`[data-date="${iso(nextDate)}"]`)?.focus();
        });
        source.addEventListener("input", sincronizarDesdeSource);
        source.addEventListener("change", sincronizarDesdeSource);
        source.form?.addEventListener("reset", () => window.setTimeout(sincronizarDesdeSource, 0));
        source.form?.addEventListener("submit", (event) => {
            if (!actualizarValidez()) {
                event.preventDefault();
                input.focus();
                input.reportValidity();
            }
        }, true);

        instances.set(source, { cerrar, sincronizarDesdeSource, popover });
        actualizarValidez();
    }

    document.querySelectorAll('input[type="date"]').forEach(enhance);
    document.addEventListener("pointerdown", (event) => {
        document.querySelectorAll("[data-aldra-date-picker].is-open").forEach((wrapper) => {
            const source = wrapper.querySelector("input[type='hidden']");
            const instance = instances.get(source);
            if (!wrapper.contains(event.target) && !instance?.popover.contains(event.target)) instance?.cerrar();
        });
    });
})();
