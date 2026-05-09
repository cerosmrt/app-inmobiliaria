// XSS-safe HTML escaping
function esc(s) {
    return String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

// WhatsApp link builder (Argentina)
function waLink(phone) {
    var d = String(phone).replace(/\D/g, '');
    var intl = d.startsWith('54') ? d : d.startsWith('0') ? '54' + d.slice(1) : '54' + d;
    return 'https://wa.me/' + intl;
}

// CSRF fetch interceptor — injects X-CSRFToken on mutating requests, redirects on 401
(function () {
    var meta = document.querySelector('meta[name="csrf-token"]');
    if (!meta) return;
    var token = meta.content;
    var _orig = window.fetch;
    window.fetch = function (url, options) {
        options = options || {};
        if (token && options.method &&
            ['POST', 'PUT', 'DELETE', 'PATCH'].indexOf(options.method.toUpperCase()) !== -1) {
            options.headers = Object.assign({}, options.headers, { 'X-CSRFToken': token });
        }
        return _orig(url, options).then(function (r) {
            if (r.status === 401) window.location.href = '/admin/login';
            return r;
        });
    };
})();

// Toast notifications
function toast(mensaje, tipo) {
    var container = document.getElementById('toast-container');
    if (!container) return;
    var el = document.createElement('div');
    el.className = 'toast toast-' + (tipo || 'info');
    el.textContent = mensaje;
    container.appendChild(el);
    setTimeout(function () { el.remove(); }, 3500);
}

// Promise-based confirm modal
var _confirmResolve = null;

function confirmar(mensaje, titulo, btnLabel) {
    document.getElementById('confirm-titulo').textContent  = titulo   || 'Confirmar';
    document.getElementById('confirm-mensaje').textContent = mensaje  || '¿Estás seguro?';
    document.getElementById('confirm-btn-ok').textContent  = btnLabel || 'Eliminar';
    document.getElementById('confirm-overlay').classList.add('active');
    return new Promise(function (resolve) { _confirmResolve = resolve; });
}

function resolveConfirm(value) {
    document.getElementById('confirm-overlay').classList.remove('active');
    if (_confirmResolve) { _confirmResolve(value); _confirmResolve = null; }
}

// Unread consultas badge
function cargarBadgeConsultas() {
    fetch('/api/consultas/no_leidas')
        .then(function (r) { return r.json(); })
        .then(function (data) {
            var badge = document.getElementById('badge-consultas');
            if (badge && data.count > 0) {
                badge.textContent = data.count;
                badge.style.display = 'flex';
            }
        }).catch(function () {});
}

// ── Command Palette ───────────────────────────────────────────────────────────
var _paletteCache  = null;
var _paletteItems  = [];
var _paletteSelIdx = -1;

var _PALETTE_ACCIONES = [
    { label: 'Propiedades', sub: 'Ir al listado',   href: '/admin?tab=propiedades' },
    { label: 'Clientes',    sub: 'Ir al listado',   href: '/admin' },
    { label: 'Archivados',  sub: 'Ver eliminados',  href: '/admin?tab=archivados' },
    { label: 'Consultas',   sub: 'Ver mensajes',    href: '/admin/consultas' },
];

function abrirPalette() {
    var overlay = document.getElementById('palette-overlay');
    if (!overlay) return;
    overlay.classList.add('active');
    var input = document.getElementById('palette-input');
    input.value = '';
    _renderPaletteItems(_PALETTE_ACCIONES.slice());
    input.focus();
    if (!_paletteCache) {
        Promise.all([
            fetch('/api/propiedades').then(function(r) { return r.json(); }).catch(function() { return []; }),
            fetch('/api/clientes').then(function(r) { return r.json(); }).catch(function() { return []; })
        ]).then(function(res) { _paletteCache = { propiedades: res[0], clientes: res[1] }; });
    }
}

function cerrarPalette() {
    var overlay = document.getElementById('palette-overlay');
    if (overlay) overlay.classList.remove('active');
}

function buscarEnPalette(q) {
    q = (q || '').trim().toLowerCase();
    if (!q) { _renderPaletteItems(_PALETTE_ACCIONES.slice()); return; }
    var items = _PALETTE_ACCIONES.filter(function(a) {
        return a.label.toLowerCase().includes(q) || (a.sub || '').toLowerCase().includes(q);
    });
    if (_paletteCache) {
        _paletteCache.propiedades.forEach(function(p) {
            if ((p.codigo    || '').toLowerCase().includes(q) ||
                (p.direccion || '').toLowerCase().includes(q) ||
                (p.barrio    || '').toLowerCase().includes(q)) {
                var label = (p.codigo ? '[' + p.codigo + '] ' : '') + (p.direccion || '(sin dirección)');
                items.push({ label: label, sub: (p.estado || '') + (p.barrio ? ' · ' + p.barrio : ''),
                    badge: { text: p.estado, cls: 'badge-' + p.estado }, href: '/admin/propiedad/' + p.id });
            }
        });
        _paletteCache.clientes.forEach(function(c) {
            var nombre = c.nombre + ' ' + c.apellido;
            if (nombre.toLowerCase().includes(q) || (c.telefono || '').includes(q)) {
                items.push({ label: nombre, sub: (c.telefono || '') + (c.tipo ? ' · ' + c.tipo : ''),
                    badge: { text: c.tipo, cls: 'badge-' + c.tipo }, href: '/cliente/' + c.id });
            }
        });
    }
    _renderPaletteItems(items.slice(0, 12));
}

function _renderPaletteItems(items) {
    _paletteItems  = items;
    _paletteSelIdx = -1;
    var list = document.getElementById('palette-list');
    if (!list) return;
    if (!items.length) {
        list.innerHTML = '<div style="padding:16px;text-align:center;color:var(--muted);font-size:13px">Sin resultados</div>';
        return;
    }
    list.innerHTML = items.map(function(item, i) {
        var tag = item.badge
            ? '<span class="badge ' + esc(item.badge.cls) + '">' + esc(item.badge.text) + '</span>'
            : '<span style="font-size:11px;color:var(--muted)">Ir</span>';
        return '<div class="palette-item" onclick="ejecutarPaletteItem(' + i + ')">' +
            '<div style="flex:1"><div class="palette-label">' + esc(item.label || '') + '</div>' +
            (item.sub ? '<div class="palette-sub">' + esc(item.sub) + '</div>' : '') + '</div>' +
            tag + '</div>';
    }).join('');
}

function ejecutarPaletteItem(idx) {
    var item = _paletteItems[idx];
    if (!item) return;
    cerrarPalette();
    if (item.href) window.location.href = item.href;
}

function paletteKeyNav(e) {
    var items = document.querySelectorAll('#palette-list .palette-item');
    if (e.key === 'ArrowDown')  { e.preventDefault(); _paletteSelIdx = Math.min(_paletteSelIdx + 1, items.length - 1); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); _paletteSelIdx = Math.max(_paletteSelIdx - 1, 0); }
    else if (e.key === 'Enter')   { e.preventDefault(); ejecutarPaletteItem(_paletteSelIdx >= 0 ? _paletteSelIdx : 0); return; }
    else if (e.key === 'Escape')  { cerrarPalette(); return; }
    items.forEach(function(el, i) { el.classList.toggle('palette-sel', i === _paletteSelIdx); });
    if (_paletteSelIdx >= 0 && items[_paletteSelIdx]) items[_paletteSelIdx].scrollIntoView({ block: 'nearest' });
}

document.addEventListener('DOMContentLoaded', function() {
    var overlay = document.getElementById('palette-overlay');
    if (overlay) overlay.addEventListener('click', function(e) { if (e.target === overlay) cerrarPalette(); });
});

// ── Global keyboard shortcuts ─────────────────────────────────────────────────
document.addEventListener('keydown', function(e) {
    // Ctrl/Cmd+K — command palette
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        var o = document.getElementById('palette-overlay');
        if (o) { o.classList.contains('active') ? cerrarPalette() : abrirPalette(); }
        return;
    }
    // Ignore when typing
    var tag = document.activeElement ? document.activeElement.tagName : '';
    if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
    // Esc — close any open modal
    if (e.key === 'Escape') {
        document.querySelectorAll('.modal-overlay.active').forEach(function(m) { m.classList.remove('active'); });
        return;
    }
    // / — focus search
    if (e.key === '/') {
        var s = document.querySelector('.filterbox input[type="text"]');
        if (s) { e.preventDefault(); s.focus(); }
        return;
    }
    // N — new record (clicks first green toolbar button)
    if (e.key === 'n' || e.key === 'N') {
        var btn = document.querySelector('.toolbar .btn-green');
        if (btn) { e.preventDefault(); btn.click(); }
    }
});
