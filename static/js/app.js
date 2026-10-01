(function () {
    "use strict";
    const dateElement = document.querySelector("[data-current-date]");
    if (dateElement) {
        dateElement.textContent = new Intl.DateTimeFormat("es-CL", { weekday: "long", day: "numeric", month: "long", year: "numeric" }).format(new Date());
    }

    function rutConFormato(value) {
        const uppercase = value.toUpperCase();
        let body = "";
        let verifier = "";
        if (uppercase.includes("-")) {
            const [rawBody, rawVerifier = ""] = uppercase.split(/-(.*)/s, 2);
            body = rawBody.replace(/\D/g, "").slice(0, 8);
            verifier = (rawVerifier.match(/[0-9K]/) || [""])[0];
        } else {
            const compact = uppercase.replace(/[^0-9K]/g, "").slice(0, 9);
            const kPosition = compact.indexOf("K");
            if (kPosition >= 0) {
                body = compact.slice(0, kPosition).replace(/\D/g, "").slice(0, 8);
                verifier = "K";
            } else if (compact.length > 8) {
                body = compact.slice(0, 8);
                verifier = compact.slice(8, 9);
            } else {
                body = compact;
            }
        }
        const grouped = body.replace(/\B(?=(\d{3})+(?!\d))/g, ".");
        return `${grouped}${verifier ? `-${verifier}` : ""}`;
    }

    function telefonoChileConFormato(value) {
        const trimmed = value.trim();
        const compact = trimmed.replace(/[^\d+]/g, "").replace(/(?!^)\+/g, "");
        const digits = compact.replace(/\D/g, "");
        let national = "";
        if (/^56[92]/.test(digits)) national = digits.slice(2);
        else if (/^[92]/.test(digits)) national = digits;
        else return compact;
        if (national.length > 9) return compact;
        const code = national.slice(0, 1);
        const subscriber = national.slice(1);
        const firstGroup = subscriber.slice(0, 4);
        const secondGroup = subscriber.slice(4, 8);
        return `+56 ${code}${firstGroup ? ` ${firstGroup}` : ""}${secondGroup ? ` ${secondGroup}` : ""}`;
    }

    function setFormattedValue(input, formatter) {
        const original = input.value;
        const caret = input.selectionStart ?? original.length;
        const formattedPrefix = formatter(original.slice(0, caret));
        input.value = formatter(original);
        const newCaret = Math.min(formattedPrefix.length, input.value.length);
        input.setSelectionRange(newCaret, newCaret);
    }

    document.querySelectorAll('[data-input-format="rut"]').forEach((input) => {
        input.addEventListener("input", () => {
            setFormattedValue(input, rutConFormato);
        });
        input.addEventListener("blur", () => {
            setFormattedValue(input, rutConFormato);
        });
    });

    document.querySelectorAll('[data-input-format="telefono"]').forEach((input) => {
        input.addEventListener("input", () => {
            setFormattedValue(input, telefonoChileConFormato);
        });
        input.addEventListener("blur", () => {
            setFormattedValue(input, telefonoChileConFormato);
        });
    });

    document.querySelectorAll("[data-month-picker]").forEach((picker) => {
        const valueInput = picker.querySelector("[data-month-value]");
        const yearLabel = picker.querySelector("[data-month-year]");
        const caption = picker.querySelector("[data-month-caption]");
        if (!valueInput || !yearLabel || !caption) return;

        const currentYear = Number(picker.dataset.currentYear) || new Date().getFullYear();
        const monthNames = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"];
        const monthButtons = Array.from(picker.querySelectorAll("[data-month-number]"));
        let selectedYear = currentYear;
        let selectedMonth = 0;

        function renderMonthPicker() {
            yearLabel.textContent = String(selectedYear);
            monthButtons.forEach((button) => {
                const active = Number(button.dataset.monthNumber) === selectedMonth;
                button.classList.toggle("is-selected", active);
                button.setAttribute("aria-pressed", String(active));
            });
            caption.textContent = selectedMonth
                ? `${monthNames[selectedMonth - 1]} ${selectedYear}`
                : "Todos los meses";
            valueInput.value = selectedMonth
                ? `${selectedYear}-${String(selectedMonth).padStart(2, "0")}`
                : "";
        }

        const existingValue = valueInput.value.match(/^(\d{4})-(\d{2})$/);
        if (existingValue) {
            selectedYear = Number(existingValue[1]);
            selectedMonth = Number(existingValue[2]);
        }

        monthButtons.forEach((button) => {
            button.addEventListener("click", () => {
                selectedMonth = Number(button.dataset.monthNumber);
                renderMonthPicker();
            });
        });
        picker.querySelectorAll("[data-year-step]").forEach((button) => {
            button.addEventListener("click", () => {
                const nextYear = selectedYear + Number(button.dataset.yearStep);
                if (nextYear < 2000 || nextYear > currentYear + 1) return;
                selectedYear = nextYear;
                renderMonthPicker();
            });
        });
        picker.querySelector("[data-month-clear]")?.addEventListener("click", () => {
            selectedMonth = 0;
            selectedYear = currentYear;
            renderMonthPicker();
        });
        renderMonthPicker();
    });
})();
