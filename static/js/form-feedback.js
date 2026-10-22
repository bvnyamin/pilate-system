(() => {
    const submitControls = (form) => Array.from(form.querySelectorAll(
        'button:not([type]), button[type="submit"], input[type="submit"]',
    ));

    function loadingLabel(control, form) {
        const custom = control?.dataset.loadingText || form.dataset.loadingText;
        if (custom) return custom;

        const action = (control?.textContent || control?.value || "").trim().toLocaleLowerCase("es");
        if (action.includes("aprobar")) return "Aprobando…";
        if (action.includes("rechazar")) return "Rechazando…";
        if (action.includes("revisar")) return "Revisando archivo…";
        if (action.includes("anular")) return "Anulando…";
        if (action.includes("cerrar sesión")) return "Cerrando sesión…";
        if (action.includes("ingresar")) return "Ingresando…";
        if (action.includes("programar")) return "Programando…";
        if (action.includes("confirmar")) return "Confirmando…";
        if (action.includes("guardar") || action.includes("registrar")) return "Guardando…";
        if (action.includes("crear")) return "Creando…";
        if (["activar", "reactivar", "desactivar", "finalizar"].some((word) => action.includes(word))) {
            return "Actualizando…";
        }
        return "Procesando…";
    }

    function beginSubmission(form, submitter) {
        const controls = submitControls(form);
        const activeControl = controls.includes(submitter) ? submitter : controls[0];
        const label = loadingLabel(activeControl, form);
        const originalFormAriaBusy = form.getAttribute("aria-busy");
        let hiddenSubmitter = null;

        if (activeControl instanceof HTMLInputElement && activeControl.name) {
            hiddenSubmitter = document.createElement("input");
            hiddenSubmitter.type = "hidden";
            hiddenSubmitter.name = activeControl.name;
            hiddenSubmitter.value = activeControl.value;
            form.appendChild(hiddenSubmitter);
        }

        form.dataset.submitting = "true";
        form.classList.add("is-submitting");
        form.setAttribute("aria-busy", "true");
        form._aldraFeedback = {
            ariaBusy: originalFormAriaBusy,
            controls: controls.map((control) => ({
                control,
                disabled: control.disabled,
                ariaDisabled: control.getAttribute("aria-disabled"),
                ariaBusy: control.getAttribute("aria-busy"),
                ariaLabel: control.getAttribute("aria-label"),
                ariaLive: control.getAttribute("aria-live"),
                html: control instanceof HTMLButtonElement ? control.innerHTML : null,
                value: control instanceof HTMLInputElement ? control.value : null,
                minWidth: control.style.minWidth,
            })),
            hiddenSubmitter,
        };

        controls.forEach((control) => {
            if (control === activeControl) {
                const width = control.getBoundingClientRect().width;
                if (width > 0) control.style.minWidth = `${width}px`;
                control.setAttribute("aria-disabled", "true");
                control.setAttribute("aria-busy", "true");
                control.setAttribute("aria-label", label);
                control.setAttribute("aria-live", "polite");
                control.classList.add("is-loading");
                if (control instanceof HTMLButtonElement) {
                    const spinner = document.createElement("span");
                    spinner.className = "submit-feedback-spinner";
                    spinner.setAttribute("aria-hidden", "true");
                    control.replaceChildren(spinner, document.createTextNode(label));
                } else {
                    control.disabled = true;
                    control.value = label;
                }
            } else {
                control.disabled = true;
            }
        });
    }

    function restoreSubmission(form) {
        const state = form._aldraFeedback;
        if (!state) return;

        form.classList.remove("is-submitting");
        delete form.dataset.submitting;
        if (state.ariaBusy === null) form.removeAttribute("aria-busy");
        else form.setAttribute("aria-busy", state.ariaBusy);

        state.controls.forEach(({ control, disabled, ariaDisabled, ariaBusy, ariaLabel, ariaLive, html, value, minWidth }) => {
            control.disabled = disabled;
            control.style.minWidth = minWidth;
            control.classList.remove("is-loading");
            [["aria-disabled", ariaDisabled], ["aria-busy", ariaBusy], ["aria-label", ariaLabel], ["aria-live", ariaLive]].forEach(([name, original]) => {
                if (original === null) control.removeAttribute(name);
                else control.setAttribute(name, original);
            });
            if (html !== null) control.innerHTML = html;
            if (value !== null) control.value = value;
        });
        state.hiddenSubmitter?.remove();
        delete form._aldraFeedback;
    }

    document.addEventListener("submit", (event) => {
        const form = event.target;
        if (!(form instanceof HTMLFormElement) || form.method.toLowerCase() !== "post") return;
        if (form.hasAttribute("data-no-loading") || event.defaultPrevented) return;

        if (form.dataset.submitting === "true") {
            event.preventDefault();
            return;
        }

        beginSubmission(form, event.submitter);
    });

    window.addEventListener("pageshow", (event) => {
        if (!event.persisted) return;
        document.querySelectorAll('form[data-submitting="true"]').forEach(restoreSubmission);
    });
})();
