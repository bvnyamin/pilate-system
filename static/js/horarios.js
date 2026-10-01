(() => {
    const page = document.querySelector(".attendance-schedule-page");
    if (!page) return;

    const controls = [...page.querySelectorAll("[data-time-control]")];
    const pad = (value) => String(value).padStart(2, "0");
    const slots = Array.from({ length: 24 * 2 }, (_, index) => {
        const hour = Math.floor(index / 2);
        const minute = index % 2 ? "30" : "00";
        return `${pad(hour)}:${minute}`;
    });

    function closeControl(control, restoreFocus = false) {
        const trigger = control.querySelector("[data-time-trigger]");
        const popover = control.querySelector("[data-time-popover]");
        if (!trigger || !popover || popover.hidden) return;
        popover.hidden = true;
        trigger.setAttribute("aria-expanded", "false");
        if (restoreFocus) trigger.focus();
    }

    controls.forEach((control) => {
        const input = control.querySelector("[data-time-input]");
        const trigger = control.querySelector("[data-time-trigger]");
        const valueLabel = control.querySelector("[data-time-value]");
        const popover = control.querySelector("[data-time-popover]");
        const options = control.querySelector("[data-time-options]");
        if (!input || !trigger || !valueLabel || !popover || !options) return;

        const initialValue = input.value.slice(0, 5);
        valueLabel.textContent = initialValue || "--:--";

        slots.forEach((slot) => {
            const option = document.createElement("button");
            option.className = "attendance-time-option";
            option.type = "button";
            option.textContent = slot;
            option.dataset.timeValue = slot;
            option.setAttribute("aria-pressed", String(slot === initialValue));
            option.setAttribute("aria-label", `${slot} horas`);
            option.addEventListener("click", () => {
                input.value = slot;
                valueLabel.textContent = slot;
                options.querySelectorAll("[data-time-value]").forEach((item) => {
                    item.setAttribute("aria-pressed", String(item.dataset.timeValue === slot));
                });
                input.dispatchEvent(new Event("input", { bubbles: true }));
                input.dispatchEvent(new Event("change", { bubbles: true }));
                closeControl(control, true);
            });
            options.append(option);
        });

        trigger.addEventListener("click", () => {
            const willOpen = popover.hidden;
            controls.forEach((otherControl) => closeControl(otherControl));
            popover.hidden = !willOpen;
            trigger.setAttribute("aria-expanded", String(willOpen));
            if (willOpen) {
                options.querySelector('[aria-pressed="true"]')?.focus();
            }
        });

        control.querySelector("[data-time-close]")?.addEventListener("click", () => closeControl(control, true));
    });

    if (!controls.length || controls.some((control) => !control.querySelector("[data-time-input]"))) return;
    page.classList.add("has-custom-time-picker");
    controls.forEach((control) => {
        const input = control.querySelector("[data-time-input]");
        input.setAttribute("aria-hidden", "true");
        input.tabIndex = -1;
        control.querySelector(".attendance-time-label")?.removeAttribute("for");
    });

    document.addEventListener("click", (event) => {
        controls.forEach((control) => {
            if (!control.contains(event.target)) closeControl(control);
        });
    });

    document.addEventListener("keydown", (event) => {
        if (event.key !== "Escape") return;
        const openControl = controls.find((control) => !control.querySelector("[data-time-popover]")?.hidden);
        if (openControl) closeControl(openControl, true);
    });
})();
