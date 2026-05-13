(function() {
    "use strict";

    const search = document.getElementById("productoSearch");
    const hidden = document.getElementById("producto_id");
    const dropdown = document.getElementById("productoDropdown");
    const selected = document.getElementById("productoSelected");
    if (!search) return;

    let debounceTimer;

    /** Escapa texto para uso seguro en textContent */
    function escapar(str) {
        return String(str || "");
    }

    /** Limpia el dropdown y lo oculta */
    function limpiarDropdown() {
        dropdown.innerHTML = "";
        dropdown.style.display = "none";
    }

    /** Crea un botón de resultado seguro */
    function crearItem(p) {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "dropdown-item";
        btn.dataset.id = p.id;
        btn.dataset.codigo = p.codigo;
        btn.dataset.desc = p.descripcion;
        btn.dataset.stock = p.stock_actual;
        btn.dataset.um = p.um;

        const strong = document.createElement("strong");
        strong.textContent = "[" + escapar(p.codigo) + "]";

        const descText = document.createTextNode(
            " " + escapar((p.descripcion || "").substring(0, 40))
        );

        const span = document.createElement("span");
        span.className = "text-muted small";
        span.textContent = " (" + p.stock_actual + " " + escapar(p.um || "") + ")";

        btn.appendChild(strong);
        btn.appendChild(descText);
        btn.appendChild(span);

        btn.addEventListener("click", function() {
            hidden.value = this.dataset.id;
            search.value = "[" + escapar(this.dataset.codigo) + "] " + escapar(this.dataset.desc);
            limpiarDropdown();

            selected.innerHTML = "";
            const strongSel = document.createElement("strong");
            strongSel.textContent = escapar(this.dataset.codigo);

            const textSel = document.createTextNode(" - " + escapar(this.dataset.desc) + " ");

            const clearBtn = document.createElement("button");
            clearBtn.type = "button";
            clearBtn.className = "btn btn-sm btn-outline-danger ms-2";
            clearBtn.id = "clearProduct";
            clearBtn.textContent = "✕";

            selected.appendChild(document.createTextNode("✅ "));
            selected.appendChild(strongSel);
            selected.appendChild(textSel);
            selected.appendChild(clearBtn);

            if (this.dataset.stock) {
                const badge = document.createElement("span");
                badge.className = "badge bg-info";
                badge.textContent = "Stock: " + parseFloat(this.dataset.stock).toFixed(2) + " " + escapar(this.dataset.um || "");
                selected.appendChild(badge);
            }

            selected.style.display = "block";
        });

        return btn;
    }

    search.addEventListener("input", function() {
        clearTimeout(debounceTimer);
        const q = this.value.trim();
        if (q.length < 1) {
            limpiarDropdown();
            hidden.value = "";
            selected.style.display = "none";
            return;
        }
        debounceTimer = setTimeout(function() {
            fetch("/api/productos?q=" + encodeURIComponent(q) + "&limit=15")
                .then(function(r) { return r.json(); })
                .then(function(data) {
                    dropdown.innerHTML = "";
                    if (data.results.length === 0) {
                        const empty = document.createElement("div");
                        empty.className = "dropdown-item text-muted";
                        empty.textContent = "Sin resultados";
                        dropdown.appendChild(empty);
                        dropdown.style.display = "block";
                        return;
                    }
                    data.results.forEach(function(p) {
                        dropdown.appendChild(crearItem(p));
                    });
                    dropdown.style.display = "block";
                });
        }, 200);
    });

    document.addEventListener("click", function(e) {
        if (e.target && e.target.id === "clearProduct") {
            search.value = "";
            hidden.value = "";
            selected.style.display = "none";
            search.focus();
        }
    });

    document.addEventListener("click", function(e) {
        if (!e.target.closest("#productoSearch") && !e.target.closest("#productoDropdown")) {
            limpiarDropdown();
        }
    });
})();
