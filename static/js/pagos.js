(function () {
    "use strict";

    const form = document.querySelector("[data-payment-form]");
    if (!form) return;

    const mensualidadSelect = form.querySelector('[data-payment-field="mensualidad"]');
    const cuotaSelect = form.querySelector('[data-payment-field="cuota"]');
    const tipoSelect = form.querySelector('[data-payment-field="tipo"]');
    const clientSelect = form.querySelector('[data-payment-field="cliente"]');
    const mensualidadGroup = form.querySelector('[data-payment-group="mensualidad"]');
    const cuotaGroup = form.querySelector('[data-payment-group="cuota"]');
    const matriculaGroup = form.querySelector('[data-payment-group="matricula"]');
    const conceptInput = form.querySelector('input[name="concepto"]');
    const amountInput = form.querySelector('input[name="monto_clp"]');
    const statusSelect = form.querySelector('select[name="estado_pago"]');
    const formHelp = document.getElementById("payment-form-help");
    const eyebrow = document.getElementById("payment-context-eyebrow");
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
    const initialIsMatricula = tipoSelect?.value === "matricula";
    const monthlyConcept = initialIsMatricula ? "" : conceptInput?.value || "";
    const monthlyAmount = initialIsMatricula ? "" : amountInput?.value || "";

    function updateCuotaOptions() {
        if (!cuotaSelect || !cuotaGroup) return;
        const planId = mensualidadSelect?.value;
        const matching = Array.from(cuotaSelect.options).filter((option) => {
            if (!option.value) return false;
            const belongs = option.dataset.planId === planId;
            option.disabled = !belongs;
            return belongs;
        });
        const isMatricula = tipoSelect?.value === "matricula";
        cuotaGroup.hidden = isMatricula || matching.length === 0;
        const selected = cuotaSelect.options[cuotaSelect.selectedIndex];
        if (selected?.value && selected.dataset.planId !== planId) cuotaSelect.value = "";
    }

    function updatePaymentType() {
        const isMatricula = tipoSelect?.value === "matricula";
        if (mensualidadGroup) mensualidadGroup.hidden = isMatricula;
        if (matriculaGroup) matriculaGroup.hidden = !isMatricula;
        updateCuotaOptions();

        if (conceptInput && amountInput) {
            conceptInput.readOnly = isMatricula;
            amountInput.readOnly = isMatricula;
            conceptInput.value = isMatricula ? "Matrícula" : monthlyConcept;
            amountInput.value = isMatricula ? "25000" : monthlyAmount;
        }
        if (statusSelect) {
            const partialOption = Array.from(statusSelect.options).find((option) => option.value === "parcial");
            if (partialOption) partialOption.disabled = isMatricula;
            if (isMatricula && statusSelect.value === "parcial") statusSelect.value = "pendiente";
        }
        if (formHelp) {
            formHelp.textContent = isMatricula
                ? "La matrícula es un cargo único de $25.000 CLP por clienta."
                : "Registra un abono asociado al período contratado.";
        }
        if (isMatricula) {
            updateMatriculaContext();
        } else {
            updateMonthlyContext();
        }
    }

    function updateMatriculaContext() {
        const selected = clientSelect?.options[clientSelect.selectedIndex];
        if (eyebrow) eyebrow.textContent = "Matrícula única";
        if (title) title.textContent = selected?.value ? selected.text : "Selecciona una clienta";
        if (plan) plan.textContent = "Cargo de inscripción, una sola vez por clienta.";
        if (agreed) agreed.textContent = currency.format(25000);
        if (received) received.textContent = "—";
        if (balance) balance.textContent = currency.format(25000);
    }

    function updateMonthlyContext() {
        updateCuotaOptions();
        if (!mensualidadSelect || !title || !plan || !agreed || !received || !balance) return;
        if (eyebrow) eyebrow.textContent = "Cuenta de la mensualidad";
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

    mensualidadSelect?.addEventListener("change", updateMonthlyContext);
    tipoSelect?.addEventListener("change", updatePaymentType);
    clientSelect?.addEventListener("change", updateMatriculaContext);
    updatePaymentType();
})();
