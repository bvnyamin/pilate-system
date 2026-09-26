(function () {
    "use strict";

    const form = document.querySelector("[data-payment-form]");
    if (!form) return;

    const mensualidadSelect = form.querySelector('[data-payment-field="mensualidad"]');
    const title = document.getElementById("payment-context-title");
    const plan = document.getElementById("payment-context-plan");
    const agreed = document.getElementById("payment-agreed-price");
    const received = document.getElementById("payment-received-total");
    const balance = document.getElementById("payment-balance");
    const currency = new Intl.NumberFormat("es-CL", {
        style: "currency",
        currency: "CLP",
        maximumFractionDigits: 0,
    });

    function updateMonthlyContext() {
        const option = mensualidadSelect.options[mensualidadSelect.selectedIndex];
        if (!option || !option.value || !option.dataset.precioAcordado) {
            title.textContent = "Selecciona una mensualidad";
            plan.textContent = "Elige una clienta y período para ver su estado.";
            agreed.textContent = "—";
            received.textContent = "—";
            balance.textContent = "—";
            return;
        }

        const currentId = mensualidadSelect.dataset.currentMensualidad;
        let receivedAmount = Number(option.dataset.totalRecibido || 0);
        if (option.value === currentId && mensualidadSelect.dataset.currentPagoContabilizado === "true") {
            receivedAmount = Math.max(0, receivedAmount - Number(mensualidadSelect.dataset.currentPagoMonto || 0));
        }
        const agreedAmount = Number(option.dataset.precioAcordado);

        title.textContent = option.dataset.cliente;
        plan.textContent = option.dataset.planPeriodo;
        agreed.textContent = currency.format(agreedAmount);
        received.textContent = currency.format(receivedAmount);
        balance.textContent = currency.format(Math.max(0, agreedAmount - receivedAmount));
    }

    mensualidadSelect.addEventListener("change", updateMonthlyContext);
    updateMonthlyContext();
})();
