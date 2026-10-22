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

    function clpConFormato(value) {
        const raw = String(value).trim();
        const negative = raw.startsWith("-");
        const digits = raw.replace(/\D/g, "");
        const grouped = digits.replace(/\B(?=(\d{3})+(?!\d))/g, ".");
        return `${negative ? "-" : ""}${grouped}`;
    }

    window.aldraFormatClpInput = (input) => {
        if (input) input.value = clpConFormato(input.value);
    };

    document.querySelectorAll('[data-input-format="clp"]').forEach((input) => {
        const format = () => setFormattedValue(input, clpConFormato);
        input.addEventListener("input", format);
        input.addEventListener("blur", format);
        format();
        input.form?.addEventListener("submit", () => {
            input.value = input.value.replace(/\./g, "");
        });
    });

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

    const paymentFilters = Array.from(document.querySelectorAll(".payment-filter-details"));
    const mobileViewport = window.matchMedia("(max-width: 575.98px)");
    function syncPaymentFilterScrollLock() {
        document.body.classList.toggle(
            "payment-filter-open",
            mobileViewport.matches && paymentFilters.some((details) => details.open),
        );
    }
    function resetPaymentFilterPosition(details) {
        const panel = details.querySelector(".payment-filter-panel");
        if (!panel) return;
        panel.classList.remove("is-floating");
        panel.style.removeProperty("--payment-filter-left");
        panel.style.removeProperty("--payment-filter-top");
        panel.style.removeProperty("max-height");
    }
    function positionPaymentFilter(details) {
        const trigger = details.querySelector("summary");
        const panel = details.querySelector(".payment-filter-panel");
        if (!details.open || !trigger || !panel) {
            resetPaymentFilterPosition(details);
            return;
        }
        if (mobileViewport.matches) {
            resetPaymentFilterPosition(details);
            return;
        }

        panel.classList.add("is-floating");
        panel.style.setProperty("--payment-filter-left", "12px");
        panel.style.setProperty("--payment-filter-top", "12px");
        const triggerRect = trigger.getBoundingClientRect();
        const roomAbove = triggerRect.top - 20;
        const roomBelow = window.innerHeight - triggerRect.bottom - 20;
        const opensAbove = roomAbove > roomBelow;
        const availableHeight = Math.max(180, Math.min(680, Math.max(roomAbove, roomBelow) - 16));
        panel.style.maxHeight = `${availableHeight}px`;
        const panelRect = panel.getBoundingClientRect();
        const preferredTop = opensAbove
            ? triggerRect.top - panelRect.height - 8
            : triggerRect.bottom + 8;
        const left = Math.max(12, Math.min(window.innerWidth - panelRect.width - 12, triggerRect.right - panelRect.width));
        const top = Math.max(12, Math.min(window.innerHeight - panelRect.height - 12, preferredTop));
        panel.style.setProperty("--payment-filter-left", `${left}px`);
        panel.style.setProperty("--payment-filter-top", `${top}px`);
    }
    function repositionOpenPaymentFilters() {
        paymentFilters.forEach((details) => {
            if (details.open) positionPaymentFilter(details);
        });
    }
    paymentFilters.forEach((details) => {
        details.addEventListener("toggle", () => {
            syncPaymentFilterScrollLock();
            requestAnimationFrame(() => positionPaymentFilter(details));
        });
        details.querySelectorAll("[data-payment-filter-dismiss]").forEach((button) => {
            button.addEventListener("click", () => {
                details.open = false;
                details.querySelector("summary")?.focus();
            });
        });
    });
    syncPaymentFilterScrollLock();
    paymentFilters.filter((details) => details.open).forEach((details) => {
        requestAnimationFrame(() => positionPaymentFilter(details));
    });
    mobileViewport.addEventListener?.("change", () => {
        syncPaymentFilterScrollLock();
        repositionOpenPaymentFilters();
    });
    const notificationMenus = Array.from(document.querySelectorAll("[data-notification-menu]"));
    function closeNotificationMenu(menu, restoreFocus = false) {
        const trigger = menu.querySelector("[data-notification-trigger]");
        const panel = menu.querySelector("[data-notification-panel]");
        if (!trigger || !panel || panel.hidden) return;
        panel.hidden = true;
        trigger.setAttribute("aria-expanded", "false");
        if (restoreFocus) trigger.focus();
    }
    notificationMenus.forEach((menu) => {
        const trigger = menu.querySelector("[data-notification-trigger]");
        const panel = menu.querySelector("[data-notification-panel]");
        if (!trigger || !panel) return;
        trigger.addEventListener("click", () => {
            const shouldOpen = panel.hidden;
            notificationMenus.forEach((other) => closeNotificationMenu(other));
            if (shouldOpen) {
                panel.hidden = false;
                trigger.setAttribute("aria-expanded", "true");
            }
        });
        menu.querySelector("[data-notification-close]")?.addEventListener("click", () => closeNotificationMenu(menu, true));
    });
    document.addEventListener("pointerdown", (event) => {
        notificationMenus.forEach((menu) => {
            if (!menu.contains(event.target)) closeNotificationMenu(menu);
        });
    });
    document.addEventListener("keydown", (event) => {
        if (event.key !== "Escape") return;
        const openNotification = notificationMenus.find((menu) => !menu.querySelector("[data-notification-panel]")?.hidden);
        if (openNotification) {
            closeNotificationMenu(openNotification, true);
            return;
        }
        const openFilter = paymentFilters.find((details) => details.open);
        if (openFilter) {
            openFilter.open = false;
            openFilter.querySelector("summary")?.focus();
            return;
        }
        const openMenu = paymentRowMenus?.find((menu) => menu.open);
        if (openMenu) {
            openMenu.open = false;
            openMenu.querySelector("summary")?.focus();
        }
    });

    const paymentRowMenus = Array.from(document.querySelectorAll("[data-payment-row-menu]"));
    function positionPaymentRowMenu(menu) {
        if (!menu.open) return;
        const trigger = menu.querySelector("summary");
        const panel = menu.querySelector(".payment-row-menu-panel");
        if (!trigger || !panel) return;
        panel.classList.add("is-floating");
        panel.style.setProperty("--payment-menu-left", "12px");
        panel.style.setProperty("--payment-menu-top", "12px");
        const triggerRect = trigger.getBoundingClientRect();
        const panelRect = panel.getBoundingClientRect();
        const rowRect = menu.closest(".payment-table tbody tr")?.getBoundingClientRect();
        const footerRect = menu.closest(".payment-list-card")?.querySelector(".payment-list-footer")?.getBoundingClientRect();
        const roomBelow = window.innerHeight - triggerRect.bottom;
        const roomAbove = triggerRect.top;
        const downTop = triggerRect.bottom + 8;
        const wouldCoverNextContent = mobileViewport.matches
            && rowRect
            && downTop + panelRect.height > rowRect.bottom;
        const wouldCoverPagination = footerRect
            && downTop < footerRect.bottom
            && downTop + panelRect.height > footerRect.top;
        const shouldOpenUp = (panelRect.height + 10 > roomBelow && roomAbove > roomBelow)
            || (wouldCoverNextContent && roomAbove > panelRect.height + 10)
            || (wouldCoverPagination && roomAbove > panelRect.height + 10);
        menu.classList.toggle("opens-up", shouldOpenUp);
        const preferredTop = shouldOpenUp
            ? triggerRect.top - panelRect.height - 8
            : triggerRect.bottom + 8;
        const left = Math.max(12, Math.min(window.innerWidth - panelRect.width - 12, triggerRect.right - panelRect.width));
        const top = Math.max(12, Math.min(window.innerHeight - panelRect.height - 12, preferredTop));
        panel.style.setProperty("--payment-menu-left", `${left}px`);
        panel.style.setProperty("--payment-menu-top", `${top}px`);
    }
    paymentRowMenus.forEach((menu) => {
        menu.addEventListener("toggle", () => {
            if (menu.open) {
                paymentRowMenus.forEach((other) => {
                    if (other !== menu) other.open = false;
                });
                requestAnimationFrame(() => positionPaymentRowMenu(menu));
            } else {
                menu.classList.remove("opens-up");
                const panel = menu.querySelector(".payment-row-menu-panel");
                panel?.classList.remove("is-floating");
                panel?.style.removeProperty("--payment-menu-left");
                panel?.style.removeProperty("--payment-menu-top");
            }
        });
    });
    document.addEventListener("pointerdown", (event) => {
        paymentRowMenus.forEach((menu) => {
            if (menu.open && !menu.contains(event.target)) menu.open = false;
        });
    });
    const repositionOpenPaymentMenu = () => paymentRowMenus.forEach(positionPaymentRowMenu);
    window.addEventListener("resize", repositionOpenPaymentMenu, { passive: true });
    window.addEventListener("scroll", repositionOpenPaymentMenu, { passive: true, capture: true });
    window.addEventListener("resize", repositionOpenPaymentFilters, { passive: true });
    window.addEventListener("scroll", repositionOpenPaymentFilters, { passive: true, capture: true });
})();
