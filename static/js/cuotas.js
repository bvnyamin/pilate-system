(function () {
    "use strict";
    const form = document.querySelector("[data-cuotas-form]");
    if (!form) return;

    const mensualidad = form.querySelector('[name="cliente_plan"]');
    const cantidad = form.querySelector('[name="cantidad"]');
    const title = form.querySelector("[data-cuotas-preview-title]");
    const periodo = form.querySelector("[data-cuotas-preview-periodo]");
    const saldo = form.querySelector("[data-cuotas-preview-saldo]");
    const count = form.querySelector("[data-cuotas-preview-cantidad]");
    const amount = form.querySelector("[data-cuotas-preview-monto]");
    const currency = new Intl.NumberFormat("es-CL", {
        style: "currency", currency: "CLP", maximumFractionDigits: 0,
    });

    function update() {
        const option = mensualidad?.options[mensualidad.selectedIndex];
        const remaining = Number(option?.dataset.saldoPendiente || 0);
        const parts = Number(cantidad?.value || 0);
        title.textContent = option?.value ? option.dataset.cliente : "Selecciona una mensualidad";
        periodo.textContent = option?.value ? option.dataset.planPeriodo : "El saldo se dividirá en cuotas de monto similar.";
        saldo.textContent = option?.value ? currency.format(remaining) : "—";
        count.textContent = parts >= 2 && parts <= 12 ? String(parts) : "—";
        amount.textContent = option?.value && parts >= 2 && parts <= 12 && remaining >= parts
            ? currency.format(Math.floor(remaining / parts))
            : "—";
    }

    mensualidad?.addEventListener("change", update);
    cantidad?.addEventListener("input", update);
    update();
})();
