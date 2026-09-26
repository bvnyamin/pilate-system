(function () {
    "use strict";
    const dateElement = document.querySelector("[data-current-date]");
    if (dateElement) {
        dateElement.textContent = new Intl.DateTimeFormat("es-CL", { weekday: "long", day: "numeric", month: "long", year: "numeric" }).format(new Date());
    }
})();
