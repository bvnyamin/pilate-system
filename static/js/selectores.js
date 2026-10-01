(function () {
    "use strict";

    let selectorId = 0;
    const instances = new WeakMap();

    function normalizar(texto) {
        return String(texto || "")
            .normalize("NFD")
            .replace(/[\u0300-\u036f]/g, "")
            .toLocaleLowerCase("es-CL")
            .trim();
    }

    function enhance(select) {
        if (select.multiple || select.dataset.nativeSelect === "true" || instances.has(select)) return;

        const required = select.required;
        const associatedLabels = Array.from(select.labels || []);
        const instanceId = ++selectorId;
        const wrapper = document.createElement("div");
        wrapper.className = "aldra-select";
        wrapper.dataset.aldraSelect = "true";
        const input = document.createElement("input");
        input.type = "text";
        input.className = "aldra-select-input";
        input.autocomplete = "off";
        input.autocapitalize = "off";
        input.spellcheck = false;
        input.setAttribute("role", "combobox");
        input.setAttribute("aria-autocomplete", "list");
        input.setAttribute("aria-haspopup", "listbox");
        input.setAttribute("aria-expanded", "false");
        input.setAttribute("aria-controls", `aldra-listbox-${instanceId}`);
        input.setAttribute("aria-required", String(required));
        input.setAttribute("aria-invalid", "false");
        input.disabled = select.disabled;
        input.required = required;
        if (select.getAttribute("aria-label")) {
            input.setAttribute("aria-label", select.getAttribute("aria-label"));
        } else if (!associatedLabels.length) {
            input.setAttribute("aria-label", select.name || "Seleccionar opción");
        }
        if (select.getAttribute("aria-describedby")) {
            input.setAttribute("aria-describedby", select.getAttribute("aria-describedby"));
        }

        const listbox = document.createElement("div");
        listbox.className = "aldra-select-menu";
        listbox.id = input.getAttribute("aria-controls");
        listbox.setAttribute("role", "listbox");
        listbox.hidden = true;

        const searchHint = document.createElement("p");
        searchHint.className = "aldra-select-hint";
        searchHint.textContent = "Escribe para buscar";
        listbox.append(searchHint);

        select.parentNode.insertBefore(wrapper, select);
        wrapper.append(input, listbox, select);
        select.classList.add("aldra-select-source");
        select.tabIndex = -1;
        select.setAttribute("aria-hidden", "true");
        select.required = false;

        if (select.id) {
            wrapper.dataset.sourceId = select.id;
            document.querySelectorAll(`label[for="${CSS.escape(select.id)}"]`).forEach((label) => {
                label.htmlFor = `aldra-input-${instanceId}`;
            });
            input.id = `aldra-input-${instanceId}`;
        }

        let activeIndex = -1;
        let isOpen = false;
        let typedSinceOpen = false;
        let renderedOptions = [];

        function selectedOption() {
            return select.options[select.selectedIndex] || null;
        }

        function updateValidity() {
            const selected = selectedOption();
            const label = selected ? selected.text.trim() : "";
            const inputMatchesSelection = normalizar(input.value) === normalizar(label);
            let message = "";
            if (required && (!selected || selected.value === "")) {
                message = "Selecciona una opción para continuar.";
            } else if (typedSinceOpen && !inputMatchesSelection) {
                message = "Selecciona una opción de la lista o borra la búsqueda.";
            }
            input.setCustomValidity(message);
            input.setAttribute("aria-invalid", String(Boolean(message)));
            return !message;
        }

        function syncFromSelect() {
            const selected = selectedOption();
            input.value = selected ? selected.text.trim() : "";
            input.disabled = select.disabled;
            input.required = required;
            input.classList.toggle("is-invalid", select.classList.contains("is-invalid"));
            input.setAttribute("aria-required", String(required));
            wrapper.classList.toggle("is-disabled", select.disabled);
            typedSinceOpen = false;
            updateValidity();
            if (isOpen) renderOptions("");
        }

        function close(restore = false) {
            isOpen = false;
            activeIndex = -1;
            listbox.hidden = true;
            wrapper.classList.remove("is-open");
            input.setAttribute("aria-expanded", "false");
            input.removeAttribute("aria-activedescendant");
            if (restore) syncFromSelect();
        }

        function choose(option) {
            const disabledByGroup = option?.parentElement.tagName === "OPTGROUP" && option.parentElement.disabled;
            if (!option || option.disabled || disabledByGroup || select.disabled) return;
            select.value = option.value;
            select.dispatchEvent(new Event("input", { bubbles: true }));
            select.dispatchEvent(new Event("change", { bubbles: true }));
            syncFromSelect();
            close();
            input.focus({ preventScroll: true });
        }

        function renderOptions(query) {
            const normalizedQuery = normalizar(query);
            listbox.querySelectorAll(".aldra-select-option, .aldra-select-group").forEach((node) => node.remove());
            renderedOptions = [];
            activeIndex = -1;

            const children = Array.from(select.children);
            children.forEach((child) => {
                const isGroup = child.tagName === "OPTGROUP";
                const optionNodes = isGroup ? Array.from(child.children) : [child];
                const groupLabel = isGroup ? child.label : "";
                const matches = optionNodes.filter((option) => {
                    if (option.tagName !== "OPTION" || option.hidden) return false;
                    const haystack = normalizar(`${option.text} ${groupLabel}`);
                    return !normalizedQuery || haystack.includes(normalizedQuery);
                });
                if (!matches.length) return;
                if (isGroup) {
                    const heading = document.createElement("div");
                    heading.className = "aldra-select-group";
                    heading.setAttribute("role", "presentation");
                    heading.textContent = groupLabel;
                    listbox.append(heading);
                }
                matches.forEach((option) => {
                    const item = document.createElement("div");
                    item.className = "aldra-select-option";
                    item.id = `aldra-option-${instanceId}-${renderedOptions.length}`;
                    item.setAttribute("role", "option");
                    item.setAttribute("aria-selected", String(option.selected));
                    item.setAttribute("aria-disabled", String(option.disabled || (isGroup && child.disabled)));
                    item.dataset.optionIndex = String(renderedOptions.length);
                    item.textContent = option.text.trim();
                    if (option.selected) item.classList.add("is-selected");
                    if (option.disabled || (isGroup && child.disabled)) item.classList.add("is-disabled");
                    listbox.append(item);
                    renderedOptions.push({ element: item, option });
                });
            });

            if (!renderedOptions.length) {
                const empty = document.createElement("p");
                empty.className = "aldra-select-empty";
                empty.setAttribute("role", "status");
                empty.textContent = normalizedQuery ? "No hay coincidencias" : "No hay opciones disponibles";
                listbox.append(empty);
            }
        }

        function setActive(index) {
            const enabled = renderedOptions
                .map((item, itemIndex) => ({ ...item, itemIndex }))
                .filter(({ option }) => !option.disabled && !(option.parentElement.tagName === "OPTGROUP" && option.parentElement.disabled));
            if (!enabled.length) return;
            const current = enabled.findIndex((item) => item.itemIndex === activeIndex);
            const nextPosition = current < 0
                ? (index > 0 ? 0 : enabled.length - 1)
                : (current + index + enabled.length) % enabled.length;
            const next = enabled[nextPosition];
            activeIndex = next.itemIndex;
            renderedOptions.forEach(({ element }, itemIndex) => {
                const active = itemIndex === activeIndex;
                element.classList.toggle("is-active", active);
                if (active) {
                    input.setAttribute("aria-activedescendant", element.id);
                    element.scrollIntoView({ block: "nearest" });
                }
            });
        }

        function open() {
            if (select.disabled) return;
            isOpen = true;
            typedSinceOpen = false;
            listbox.hidden = false;
            wrapper.classList.add("is-open");
            input.setAttribute("aria-expanded", "true");
            renderOptions("");
        }

        input.addEventListener("focus", () => {
            open();
            input.select();
        });
        input.addEventListener("click", () => {
            if (!isOpen) open();
            input.select();
        });
        input.addEventListener("input", () => {
            if (!isOpen) open();
            typedSinceOpen = true;
            renderOptions(input.value);
            const exactMatches = renderedOptions.filter(({ option }) =>
                !option.disabled && normalizar(option.text) === normalizar(input.value)
            );
            if (exactMatches.length === 1) choose(exactMatches[0].option);
            else updateValidity();
        });
        input.addEventListener("keydown", (event) => {
            if (event.key === "ArrowDown") {
                event.preventDefault();
                if (!isOpen) open();
                setActive(1);
            } else if (event.key === "ArrowUp") {
                event.preventDefault();
                if (!isOpen) open();
                setActive(-1);
            } else if (event.key === "Enter" && isOpen) {
                if (activeIndex >= 0) {
                    event.preventDefault();
                    choose(renderedOptions[activeIndex]?.option);
                }
            } else if (event.key === "Escape" && isOpen) {
                event.preventDefault();
                close(true);
            }
        });
        listbox.addEventListener("mousedown", (event) => event.preventDefault());
        listbox.addEventListener("click", (event) => {
            const item = event.target.closest("[data-option-index]");
            if (item) choose(renderedOptions[Number(item.dataset.optionIndex)]?.option);
        });
        input.addEventListener("blur", () => {
            window.setTimeout(() => {
                if (!wrapper.contains(document.activeElement)) close(true);
            }, 0);
        });
        select.addEventListener("change", syncFromSelect);
        select.form?.addEventListener("reset", () => window.setTimeout(syncFromSelect, 0));
        select.form?.addEventListener("submit", (event) => {
            if (!updateValidity()) {
                event.preventDefault();
                input.focus();
                input.reportValidity();
            }
        }, true);

        const observer = new MutationObserver(() => {
            syncFromSelect();
            if (isOpen) renderOptions(input.value);
        });
        observer.observe(select, { childList: true, subtree: true, attributes: true, attributeFilter: ["disabled", "hidden", "label", "value"] });

        instances.set(select, { syncFromSelect, close, observer });
        syncFromSelect();
    }

    document.querySelectorAll("select").forEach(enhance);

    document.addEventListener("pointerdown", (event) => {
        document.querySelectorAll("[data-aldra-select].is-open").forEach((wrapper) => {
            if (!wrapper.contains(event.target)) {
                const select = wrapper.querySelector("select");
                const instance = select && instances.get(select);
                instance?.close(true);
            }
        });
    });
})();
