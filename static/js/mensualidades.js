(function () {
    "use strict";

    const form = document.querySelector("[data-cliente-plan-form]");
    if (!form) return;

    const planSelect = form.querySelector('[data-cliente-plan-field="plan"]');
    const discountInput = form.querySelector('[data-cliente-plan-field="descuento"]');
    const baseOutput = document.getElementById("subscription-base-price");
    const discountOutput = document.getElementById("subscription-discount");
    const finalOutput = document.getElementById("subscription-final-price");
    const startDateInput = form.querySelector('input[name="fecha_inicio"]');
    const endDateInput = form.querySelector('input[name="fecha_fin"]');
    const currency = new Intl.NumberFormat("es-CL", {
        style: "currency",
        currency: "CLP",
        maximumFractionDigits: 0,
    });

    function updatePricePreview() {
        if (!planSelect || !discountInput || !baseOutput || !discountOutput || !finalOutput) return;
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

    function updateEndDate() {
        if (!startDateInput || !endDateInput || !startDateInput.value) return;

        const [year, month, day] = startDateInput.value.split("-").map(Number);
        const nextMonth = new Date(year, month, 1);
        const lastDayOfNextMonth = new Date(
            nextMonth.getFullYear(),
            nextMonth.getMonth() + 1,
            0,
        ).getDate();
        const anniversaryDay = Math.min(day, lastDayOfNextMonth);
        const anniversary = new Date(nextMonth.getFullYear(), nextMonth.getMonth(), anniversaryDay);
        anniversary.setDate(anniversary.getDate() - 1);
        const calculatedEndDate = [
            anniversary.getFullYear(),
            String(anniversary.getMonth() + 1).padStart(2, "0"),
            String(anniversary.getDate()).padStart(2, "0"),
        ].join("-");
        if (endDateInput.value !== calculatedEndDate) {
            endDateInput.value = calculatedEndDate;
            endDateInput.dispatchEvent(new Event("input", { bubbles: true }));
            endDateInput.dispatchEvent(new Event("change", { bubbles: true }));
        }
    }

    planSelect?.addEventListener("change", updatePricePreview);
    discountInput?.addEventListener("input", updatePricePreview);
    startDateInput?.addEventListener("input", updateEndDate);
    startDateInput?.addEventListener("change", updateEndDate);
    if (endDateInput && !endDateInput.value) updateEndDate();
    updatePricePreview();
})();
