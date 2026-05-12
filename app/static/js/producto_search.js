(function() {
    const search = document.getElementById('productoSearch');
    const hidden = document.getElementById('producto_id');
    const dropdown = document.getElementById('productoDropdown');
    const selected = document.getElementById('productoSelected');
    if (!search) return;

    let debounceTimer;

    search.addEventListener('input', function() {
        clearTimeout(debounceTimer);
        const q = this.value.trim();
        if (q.length < 1) {
            dropdown.style.display = 'none';
            hidden.value = '';
            selected.style.display = 'none';
            return;
        }
        debounceTimer = setTimeout(function() {
            fetch('/api/productos?q=' + encodeURIComponent(q) + '&limit=15')
                .then(r => r.json())
                .then(data => {
                    if (data.results.length === 0) {
                        dropdown.innerHTML = '<div class="dropdown-item text-muted">Sin resultados</div>';
                        dropdown.style.display = 'block';
                        return;
                    }
                    let html = '';
                    data.results.forEach(function(p) {
                        html += '<button type="button" class="dropdown-item" data-id="' + p.id + '" data-codigo="' + p.codigo + '" data-desc="' + p.descripcion + '" data-stock="' + p.stock_actual + '" data-um="' + p.um + '">';
                        html += '<strong>[' + p.codigo + ']</strong> ' + (p.descripcion || '').substring(0, 40);
                        html += ' <span class="text-muted small">(' + p.stock_actual + ' ' + p.um + ')</span>';
                        html += '</button>';
                    });
                    dropdown.innerHTML = html;
                    dropdown.style.display = 'block';

                    dropdown.querySelectorAll('.dropdown-item').forEach(function(item) {
                        item.addEventListener('click', function() {
                            hidden.value = this.dataset.id;
                            search.value = '[' + this.dataset.codigo + '] ' + this.dataset.desc;
                            dropdown.style.display = 'none';
                            selected.innerHTML = '✅ <strong>' + this.dataset.codigo + '</strong> - ' + this.dataset.desc + ' <button type="button" class="btn btn-sm btn-outline-danger ms-2" id="clearProduct">✕</button>';
                            if (this.dataset.stock) {
                                selected.innerHTML += ' <span class="badge bg-info">Stock: ' + parseFloat(this.dataset.stock).toFixed(2) + ' ' + (this.dataset.um || '') + '</span>';
                            }
                            selected.style.display = 'block';
                        });
                    });
                });
        }, 200);
    });

    document.addEventListener('click', function(e) {
        if (e.target && e.target.id === 'clearProduct') {
            search.value = '';
            hidden.value = '';
            selected.style.display = 'none';
            search.focus();
        }
    });

    document.addEventListener('click', function(e) {
        if (!e.target.closest('#productoSearch') && !e.target.closest('#productoDropdown')) {
            dropdown.style.display = 'none';
        }
    });
})();
