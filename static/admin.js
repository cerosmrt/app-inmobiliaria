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

// WhatsApp icon — green clickable logo if phone exists, gray if not
function waIcon(phone) {
    var svg = '<svg viewBox="0 0 24 24" width="15" height="15" fill="currentColor" style="display:block" xmlns="http://www.w3.org/2000/svg"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/></svg>';
    // Número como texto: oculto en pantalla, se muestra al imprimir (el ícono
    // de WhatsApp no sirve en papel; ver @media print en admin.css).
    var num = '<span class="tel-print">' + esc(String(phone == null ? '' : phone).trim()) + '</span>';
    if (phone) {
        return '<a href="' + waLink(phone) + '" target="_blank" title="WhatsApp" onclick="event.stopPropagation()" class="wa-icon" style="color:#25D366;display:inline-flex;align-items:center;vertical-align:middle;text-decoration:none">' + svg + '</a>' + num;
    }
    return '<span title="Sin teléfono" class="wa-icon" style="color:var(--muted);opacity:0.35;display:inline-flex;align-items:center;vertical-align:middle">' + svg + '</span>' + num;
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
