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
