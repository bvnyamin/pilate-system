(function () {
    "use strict";

    const form = document.querySelector("[data-cliente-plan-form]");
    if (!form) return;

    const planSelect = form.querySelector('[data-cliente-plan-field="plan"]');
    const discountInput = form.querySelector('[data-cliente-plan-field="descuento"]');
    const baseOutput = document.getElementById("subscription-base-price");
    const discountOutput = document.getElementById("subscription-discount");
    const finalOutput = document.getElementById("subscription-final-price");
    const currency = new Intl.NumberFormat("es-CL", {
        style: "currency",
        currency: "CLP",
        maximumFractionDigits: 0,
    });

    function updatePricePreview() {
        const selectedOption = planSelect.options[planSelect.selectedIndex];
        const rawBase = selectedOption?.dataset.precioClp;
        const basePrice = rawBase ? Number(rawBase) : null;
        const discount = Number((discountInput.value || "0").replace(",", "."));

        if (!Number.isFinite(basePrice)) {
            baseOutput.textContent = "—";
            finalOutput.textContent = "—";
            discountOutput.textContent = `${Number.isFinite(discount) ? discount : 0}%`;
            return;
        }

        const safeDiscount = Number.isFinite(discount) ? Math.min(100, Math.max(0, discount)) : 0;
        baseOutput.textContent = currency.format(basePrice);
        discountOutput.textContent = `${safeDiscount}%`;
        finalOutput.textContent = currency.format(Math.round(basePrice * (1 - safeDiscount / 100)));
    }

    planSelect.addEventListener("change", updatePricePreview);
    discountInput.addEventListener("input", updatePricePreview);
    updatePricePreview();
})();
