document.querySelectorAll(".attendance-cancel-notice").forEach(enhanceCancelDateTime);

function enhanceCancelDateTime(source) {
    if (source.dataset.customDateTime === "true") return;
    source.dataset.customDateTime = "true";
    const wrapper = document.createElement("div");
    wrapper.className = "aldra-datetime-picker";
    const display = document.createElement("input");
    display.type = "text";
    display.className = "aldra-date-input aldra-datetime-display";
    display.readOnly = true;
    display.placeholder = "dd-mm-aaaa  hh:mm";
    display.setAttribute("aria-haspopup", "dialog");
    display.setAttribute("aria-expanded", "false");
    display.setAttribute("aria-label", "Fecha y hora en que avisó la cancelación");
    const originalId = source.id;
    display.id = `${originalId || "attendance-cancel-notice"}-display`;
    if (originalId) document.querySelectorAll(`label[for="${CSS.escape(originalId)}"]`).forEach((label) => { label.htmlFor = display.id; });
    const trigger = document.createElement("button");
    trigger.type = "button";
    trigger.className = "aldra-calendar-trigger";
    trigger.setAttribute("aria-label", "Seleccionar fecha y hora del aviso");
    trigger.innerHTML = '<i class="bi bi-calendar3" aria-hidden="true"></i>';
    const popover = document.createElement("section");
    popover.className = "aldra-calendar-popover aldra-datetime-popover";
    popover.setAttribute("role", "dialog");
    popover.setAttribute("aria-label", "Seleccionar fecha y hora del aviso");
    popover.hidden = true;
    source.parentNode.insertBefore(wrapper, source);
    wrapper.append(display, trigger, source, popover);
    source.classList.add("aldra-date-source");
    source.required = false;
    source.tabIndex = -1;
    source.setAttribute("aria-hidden", "true");

    let current = parseValue(source.value) || new Date();
    let month = new Date(current.getFullYear(), current.getMonth(), 1);
    let open = false;
    const weekdays = ["Lu", "Ma", "Mi", "Ju", "Vi", "Sa", "Do"];
    const months = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"];
    const pad = (value) => String(value).padStart(2, "0");
    const formatValue = (date) => `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
    const formatDisplay = (date) => `${pad(date.getDate())}-${pad(date.getMonth() + 1)}-${date.getFullYear()} · ${pad(date.getHours())}:${pad(date.getMinutes())}`;
    function parseValue(value) {
        const match = String(value || "").match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$/);
        if (!match) return null;
        const [, y, m, d, h, min] = match.map(Number);
        const date = new Date(y, m - 1, d, h, min);
        return date.getFullYear() === y && date.getMonth() === m - 1 && date.getDate() === d && date.getHours() === h && date.getMinutes() === min ? date : null;
    }
    function syncDisplay() {
        display.value = formatDisplay(current);
        source.value = formatValue(current);
        source.dispatchEvent(new Event("input", { bubbles: true }));
        source.dispatchEvent(new Event("change", { bubbles: true }));
    }
    function chooseDate(day) {
        current = new Date(day.getFullYear(), day.getMonth(), day.getDate(), current.getHours(), current.getMinutes());
        month = new Date(day.getFullYear(), day.getMonth(), 1);
        syncDisplay();
        draw();
    }
    function draw() {
        popover.replaceChildren();
        const calendarPanel = document.createElement("div");
        calendarPanel.className = "aldra-datetime-calendar";
        const header = document.createElement("header");
        header.className = "aldra-calendar-header";
        const nav = (text, label, change) => {
            const button = document.createElement("button");
            button.type = "button";
            button.className = "aldra-calendar-nav";
            button.setAttribute("aria-label", label);
            button.innerHTML = `<i class="bi bi-chevron-${text}" aria-hidden="true"></i>`;
            button.addEventListener("click", () => { month = new Date(month.getFullYear(), month.getMonth() + change, 1); draw(); });
            return button;
        };
        const title = document.createElement("h3");
        title.className = "aldra-calendar-title";
        title.textContent = `${months[month.getMonth()]} ${month.getFullYear()}`;
        header.append(nav("left", "Mes anterior", -1), title, nav("right", "Mes siguiente", 1));
        const weekdaysRow = document.createElement("div");
        weekdaysRow.className = "aldra-calendar-weekdays";
        weekdays.forEach((day) => { const span = document.createElement("span"); span.textContent = day; weekdaysRow.append(span); });
        const days = document.createElement("div");
        days.className = "aldra-calendar-days";
        const first = new Date(month.getFullYear(), month.getMonth(), 1);
        const offset = (first.getDay() + 6) % 7;
        const totalDays = new Date(month.getFullYear(), month.getMonth() + 1, 0).getDate();
        for (let index = 0; index < offset + totalDays; index += 1) {
            const day = new Date(month.getFullYear(), month.getMonth(), index - offset + 1);
            const cell = document.createElement("div");
            cell.setAttribute("role", "gridcell");
            const button = document.createElement("button");
            button.type = "button";
            button.className = "aldra-calendar-day";
            button.textContent = String(day.getDate());
            button.setAttribute("aria-label", `${day.getDate()} ${months[day.getMonth()]} ${day.getFullYear()}`);
            if (day.toDateString() === current.toDateString()) button.classList.add("is-selected");
            if (day.toDateString() === new Date().toDateString()) button.classList.add("is-today");
            button.addEventListener("click", () => chooseDate(day));
            cell.append(button); days.append(cell);
        }
        const timePanel = document.createElement("div");
        timePanel.className = "aldra-datetime-time-section";
        const timeHeading = document.createElement("div");
        timeHeading.className = "aldra-datetime-time-heading";
        timeHeading.textContent = "Hora del aviso";
        const timePicker = document.createElement("div");
        timePicker.className = "aldra-datetime-time-picker";
        [["Hora", current.getHours(), 23, "hour"], ["Minuto", current.getMinutes(), 59, "minute"]].forEach(([label, selected, maximum, part]) => {
            const column = document.createElement("div");
            column.className = "aldra-datetime-time-column";
            const caption = document.createElement("span"); caption.textContent = label; column.append(caption);
            const stepper = document.createElement("div"); stepper.className = "aldra-datetime-stepper";
            const valueInput = document.createElement("input");
            valueInput.type = "text";
            valueInput.inputMode = "numeric";
            valueInput.maxLength = 2;
            valueInput.className = "aldra-datetime-stepper-value";
            valueInput.value = pad(selected);
            valueInput.setAttribute("aria-label", label);
            const setPart = (value) => {
                const bounded = Math.max(0, Math.min(maximum, value));
                current = new Date(current.getFullYear(), current.getMonth(), current.getDate(), part === "hour" ? bounded : current.getHours(), part === "minute" ? bounded : current.getMinutes());
                valueInput.value = pad(bounded);
                syncDisplay();
            };
            const adjustment = (delta, description) => {
                const button = document.createElement("button");
                button.type = "button";
                button.className = "aldra-datetime-stepper-button";
                button.setAttribute("aria-label", `${description} ${label.toLowerCase()}`);
                button.textContent = delta < 0 ? "−" : "+";
                button.addEventListener("click", () => setPart((Number(valueInput.value) + delta + maximum + 1) % (maximum + 1)));
                return button;
            };
            valueInput.addEventListener("input", () => {
                const value = Number(valueInput.value);
                if (/^\d{1,2}$/.test(valueInput.value) && Number.isInteger(value) && value >= 0 && value <= maximum) setPart(value);
            });
            valueInput.addEventListener("change", () => {
                const value = Number(valueInput.value);
                if (!/^\d{1,2}$/.test(valueInput.value) || !Number.isInteger(value) || value < 0 || value > maximum) {
                    valueInput.value = pad(part === "hour" ? current.getHours() : current.getMinutes());
                }
            });
            stepper.append(adjustment(-1, "Disminuir"), valueInput, adjustment(1, "Aumentar"));
            column.append(stepper); timePicker.append(column);
        });
        calendarPanel.append(header, weekdaysRow, days);
        timePanel.append(timeHeading, timePicker);
        const footer = document.createElement("footer"); footer.className = "aldra-calendar-footer aldra-datetime-footer";
        const today = document.createElement("button"); today.type = "button"; today.className = "aldra-calendar-today-action"; today.textContent = "Hoy";
        today.addEventListener("click", () => chooseDate(new Date()));
        const done = document.createElement("button"); done.type = "button"; done.textContent = "Listo"; done.addEventListener("click", close);
        footer.append(today, done);
        popover.append(calendarPanel, timePanel, footer);
    }
    function close() { open = false; popover.hidden = true; wrapper.classList.remove("is-open"); display.setAttribute("aria-expanded", "false"); }
    function show() { open = true; draw(); popover.hidden = false; wrapper.classList.add("is-open"); display.setAttribute("aria-expanded", "true"); }
    function updateRequired() { display.required = source.required; }
    display.value = source.value ? formatDisplay(current) : "";
    display.addEventListener("click", () => open ? close() : show());
    trigger.addEventListener("click", () => open ? close() : show());
    source.addEventListener("change", () => { current = parseValue(source.value) || current; display.value = source.value ? formatDisplay(current) : ""; if (open) draw(); });
    source.addEventListener("input", updateRequired);
    source.form?.addEventListener("reset", () => window.setTimeout(() => { current = parseValue(source.value) || new Date(); display.value = source.value ? formatDisplay(current) : ""; }, 0));
    source.form?.addEventListener("submit", (event) => {
        updateRequired();
        if (display.required && !source.value) { event.preventDefault(); display.focus(); display.reportValidity(); }
    }, true);
    document.addEventListener("pointerdown", (event) => { if (open && !wrapper.contains(event.target) && !popover.contains(event.target)) close(); });
    if (source.value) display.value = formatDisplay(current);
}

document.querySelectorAll("[data-attendance-card]").forEach((card) => {
    const cancelFields = card.querySelector("[data-cancel-fields]");
    const initialCancel = card.querySelector('[data-attendance-state][value="cancelo"]:checked');
    cancelFields.querySelectorAll(".aldra-datetime-display").forEach((field) => { field.required = Boolean(initialCancel); });
    card.querySelectorAll("[data-attendance-state]").forEach((input) => {
        input.addEventListener("change", () => {
            const visible = input.checked && input.value === "cancelo";
            if (visible) cancelFields.hidden = false;
            if (!visible && input.checked) cancelFields.hidden = true;
            cancelFields.querySelectorAll("input").forEach((field) => {
                const picker = field.closest(".aldra-datetime-picker");
                field.required = visible;
                if (picker) picker.querySelector(".aldra-datetime-display").required = visible;
                if (visible && field.type === "datetime-local" && !field.value) {
                    const now = new Date();
                    const local = new Date(now.getTime() - now.getTimezoneOffset() * 60000);
                    field.value = local.toISOString().slice(0, 16);
                    field.dispatchEvent(new Event("change", { bubbles: true }));
                }
                if (!visible && input.checked) {
                    field.value = "";
                    field.dispatchEvent(new Event("change", { bubbles: true }));
                }
            });
        });
    });
});

document.querySelectorAll("[data-session-form]").forEach((form) => {
    const dateInput = form.querySelector("[data-session-date]");
    const slotPicker = form.querySelector("[data-session-time-picker]");
    const availability = form.querySelector("[data-session-availability]");
    if (!dateInput || !slotPicker || !availability) return;
    let latestRequest = 0;

    async function loadAvailableTimes() {
        const requestNumber = ++latestRequest;
        const date = dateInput.value;
        const endpoint = dateInput.dataset.availableTimesUrl;
        if (!date || !endpoint) {
            slotPicker.replaceChildren();
            availability.textContent = "Selecciona una fecha para ver los horarios libres.";
            return;
        }

        const selected = form.querySelector('[data-session-time]:checked')?.value;
        const radioName = form.querySelector("[data-session-time]")?.name || "hora";
        availability.textContent = "Buscando horarios…";
        slotPicker.setAttribute("aria-busy", "true");
        try {
            const response = await fetch(`${endpoint}?fecha=${encodeURIComponent(date)}`, {
                headers: { Accept: "application/json" },
                credentials: "same-origin",
                cache: "no-store",
            });
            const data = await response.json();
            if (requestNumber !== latestRequest) return;
            if (!response.ok) throw new Error(data.error || "No fue posible consultar los horarios.");

            slotPicker.replaceChildren();
            let availableCount = 0;
            for (const group of data.groups) {
                const section = document.createElement("section");
                section.className = "attendance-slot-group";
                const heading = document.createElement("h4");
                heading.textContent = group.label;
                section.append(heading);
                const grid = document.createElement("div");
                grid.className = "attendance-time-grid";
                for (const slot of group.slots) {
                    const label = document.createElement("label");
                    label.className = `attendance-time-option${slot.available ? "" : " is-unavailable"}`;
                    const radio = document.createElement("input");
                    radio.type = "radio";
                    radio.name = radioName;
                    radio.value = slot.value;
                    radio.id = `id_hora_${slot.value.replace(/\D/g, "")}`;
                    radio.required = true;
                    radio.disabled = !slot.available;
                    radio.dataset.sessionTime = "true";
                    radio.setAttribute("aria-label", `${slot.label}${slot.available ? "" : ", ocupado"}`);
                    if (slot.value === selected && slot.available) radio.checked = true;
                    if (slot.available) availableCount += 1;
                    const timeText = document.createElement("span");
                    timeText.textContent = slot.label;
                    const status = document.createElement("small");
                    status.dataset.slotStatus = "true";
                    status.textContent = slot.available ? "" : "Ocupado";
                    label.append(radio, timeText, status);
                    grid.append(label);
                }
                section.append(grid);
                slotPicker.append(section);
            }
            availability.textContent = availableCount
                ? "Elige un horario disponible. Los ocupados están deshabilitados."
                : "No quedan horarios disponibles para este día.";
        } catch (error) {
            if (requestNumber !== latestRequest) return;
            slotPicker.replaceChildren();
            availability.textContent = error.message || "No fue posible consultar los horarios.";
        } finally {
            if (requestNumber === latestRequest) slotPicker.removeAttribute("aria-busy");
        }
    }

    dateInput.addEventListener("change", loadAvailableTimes);
    loadAvailableTimes();
});
