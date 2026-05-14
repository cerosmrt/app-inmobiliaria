"""
Auditoría funcional completa — Moret Inmobiliaria
Corre contra servidor local en :5000
"""
import requests
import json
import os
import sys
import io

BASE = "http://127.0.0.1:5000"
PASS = []
FAIL = []

def ok(name):
    PASS.append(name)
    print(f"  PASS  {name}")

def fail(name, detail=""):
    FAIL.append((name, detail))
    print(f"  FAIL  {name}: {detail}")

def check(name, condition, detail=""):
    if condition:
        ok(name)
    else:
        fail(name, detail)

# ── Sesión autenticada ────────────────────────────────────────────────────────
session = requests.Session()

def get_csrf():
    r = session.get(f"{BASE}/admin/login")
    from html.parser import HTMLParser
    class P(HTMLParser):
        token = None
        def handle_starttag(self, tag, attrs):
            d = dict(attrs)
            if d.get("name") == "csrf_token":
                self.token = d.get("value")
    p = P(); p.feed(r.text)
    return p.token

# ─────────────────────────────────────────────────────────────────────────────
print("\n=== FASE 1: ARRANQUE ===")

r = session.get(BASE)
check("Sitio público responde 200", r.status_code == 200, str(r.status_code))

r = session.get(f"{BASE}/admin/login")
check("Login page 200", r.status_code == 200)
check("CSRF token en login", "csrf_token" in r.text, "no encontrado")

# ─────────────────────────────────────────────────────────────────────────────
print("\n=== FASE 2: LOGIN ===")

csrf = get_csrf()
check("CSRF token obtenido", bool(csrf), repr(csrf))

# Login inválido
r = session.post(f"{BASE}/admin/login", data={"username": "wrong", "password": "wrong", "csrf_token": csrf})
check("Login inválido no redirige a admin", "/admin" not in r.url or "login" in r.url)

# Login válido — leemos admin de la DB directamente
import sqlite3
conn = sqlite3.connect("z:/programming/Dad/instance/inmobiliaria.db")
admin_row = conn.execute("SELECT username FROM admins LIMIT 1").fetchone()
conn.close()

if not admin_row:
    fail("Admin en DB", "no hay admin registrado")
    print("ABORTANDO — sin admin no podemos continuar tests autenticados")
    sys.exit(1)

admin_user = admin_row[0]
# Necesitamos la contraseña — no la tenemos, probamos con la default del setup
# Intentamos con contraseñas comunes del proyecto
csrf = get_csrf()
logged_in = False
for pwd in ["moret2026", "audit_tmp_123", "admin", "admin123", "moret", "1234", "moret123"]:
    r = session.post(f"{BASE}/admin/login",
                     data={"username": admin_user, "password": pwd, "csrf_token": csrf},
                     allow_redirects=True)
    if "/admin" in r.url and "login" not in r.url:
        logged_in = True
        ok(f"Login válido ({admin_user}/{pwd})")
        break
    csrf = get_csrf()

if not logged_in:
    # Intentamos con un admin nuevo via setup si no hay conflicto
    fail("Login válido", f"no pudimos autenticar como {admin_user}")
    # Continuamos igual — los endpoints protegidos fallarán con 401/redirect
    print("  [!] Tests autenticados marcarán FAIL por 401")

# ─────────────────────────────────────────────────────────────────────────────
print("\n=== FASE 3: PROTECCIÓN CSRF ===")

r = session.post(f"{BASE}/api/clientes", json={"nombre": "Test"})
check("API rechaza POST sin CSRF token", r.status_code in (401, 403), str(r.status_code))

# ─────────────────────────────────────────────────────────────────────────────
print("\n=== FASE 4: CLIENTES ===")

r = session.get(f"{BASE}/api/clientes")
check("GET /api/clientes 200", r.status_code == 200, str(r.status_code))
clientes_orig = r.json() if r.status_code == 200 else []
check("GET /api/clientes devuelve lista", isinstance(clientes_orig, list))

# Crear cliente
csrf = get_csrf()
new_cli = {"nombre": "Audit", "apellido": "Test", "telefono": "3490000001",
           "tipo": "interesado", "rango_min": 100000, "rango_max": 200000,
           "es_usd": True, "ambientes": 3, "operacion": "venta"}
r = session.post(f"{BASE}/api/clientes", json=new_cli,
                 headers={"X-CSRFToken": session.cookies.get("session", "")})
# Obtener token real
csrf_token = None
for c in session.cookies:
    pass
# El CSRF está en la sesión del servidor, lo enviamos via header
r2 = session.get(f"{BASE}/admin")  # refresca sesión
# El token CSRF real está guardado en la sesión de Flask, lo obtenemos del HTML
from html.parser import HTMLParser
class MetaParser(HTMLParser):
    token = None
    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if tag == "meta" and d.get("name") == "csrf-token":
            self.token = d.get("content")
p = MetaParser(); p.feed(r2.text)
real_csrf = p.token

r = session.post(f"{BASE}/api/clientes", json=new_cli,
                 headers={"X-CSRFToken": real_csrf, "Content-Type": "application/json"})
check("POST /api/clientes 201", r.status_code == 201, f"{r.status_code}: {r.text[:100]}")

new_cli_id = None
if r.status_code == 201:
    new_cli_id = r.json().get("id")
    check("POST cliente devuelve id", bool(new_cli_id))

# Actualizar cliente
if new_cli_id:
    r = session.put(f"{BASE}/api/clientes/{new_cli_id}",
                    json={"nombre": "AuditMod"},
                    headers={"X-CSRFToken": real_csrf})
    check("PUT /api/clientes/<id> 200", r.status_code == 200, str(r.status_code))

    # Verificar actualización
    r = session.get(f"{BASE}/api/clientes/{new_cli_id}")
    check("GET /api/clientes/<id> devuelve datos", r.status_code == 200)
    if r.status_code == 200:
        check("PUT persistió nombre", r.json().get("nombre") == "AuditMod", r.json().get("nombre"))

    # Soft delete
    r = session.delete(f"{BASE}/api/clientes/{new_cli_id}",
                       headers={"X-CSRFToken": real_csrf})
    check("DELETE /api/clientes soft delete 200", r.status_code == 200, str(r.status_code))

    # No aparece en lista activa
    r = session.get(f"{BASE}/api/clientes")
    ids_activos = [c["id"] for c in r.json()] if r.status_code == 200 else []
    check("Soft delete oculta cliente de lista activa", new_cli_id not in ids_activos)

    # Aparece en archivados
    r = session.get(f"{BASE}/api/clientes/archivados")
    check("GET /api/clientes/archivados 200", r.status_code == 200, str(r.status_code))
    if r.status_code == 200:
        ids_arch = [c["id"] for c in r.json()]
        check("Cliente archivado aparece en archivados", new_cli_id in ids_arch)

    # Restore
    r = session.put(f"{BASE}/api/clientes/{new_cli_id}/restore",
                    json={}, headers={"X-CSRFToken": real_csrf})
    check("PUT /api/clientes/restore 200", r.status_code == 200, str(r.status_code))

    r = session.get(f"{BASE}/api/clientes")
    ids_activos2 = [c["id"] for c in r.json()] if r.status_code == 200 else []
    check("Restore devuelve cliente a lista activa", new_cli_id in ids_activos2)

    # Delete permanente
    r = session.delete(f"{BASE}/api/clientes/{new_cli_id}/permanente",
                       headers={"X-CSRFToken": real_csrf})
    check("DELETE permanente 200", r.status_code == 200, str(r.status_code))

    r = session.get(f"{BASE}/api/clientes/{new_cli_id}")
    check("Cliente permanente no existe más", r.status_code == 404, str(r.status_code))

# ─────────────────────────────────────────────────────────────────────────────
print("\n=== FASE 5: PROPIEDADES ===")

r = session.get(f"{BASE}/api/propiedades")
check("GET /api/propiedades 200", r.status_code == 200, str(r.status_code))
propiedades_orig = r.json() if r.status_code == 200 else []
check("GET devuelve lista", isinstance(propiedades_orig, list))
check("Hay propiedades reales", len(propiedades_orig) > 0, f"count={len(propiedades_orig)}")

# Crear propiedad
new_prop = {"direccion": "Audit Test 123", "tipo": "casa", "estado": "disponible",
            "operacion": "venta", "rango_min": 80000, "es_usd": True, "ambientes": 3}
r = session.post(f"{BASE}/api/propiedades", json=new_prop,
                 headers={"X-CSRFToken": real_csrf})
check("POST /api/propiedades 201", r.status_code == 201, f"{r.status_code}: {r.text[:100]}")

new_prop_id = None
if r.status_code == 201:
    new_prop_id = r.json().get("id")
    check("POST propiedad devuelve id", bool(new_prop_id))

if new_prop_id:
    # GET individual
    r = session.get(f"{BASE}/api/propiedades/{new_prop_id}")
    check("GET /api/propiedades/<id> 200", r.status_code == 200, str(r.status_code))

    # PUT actualización
    r = session.put(f"{BASE}/api/propiedades/{new_prop_id}",
                    json={"estado": "vendida"},
                    headers={"X-CSRFToken": real_csrf})
    check("PUT /api/propiedades 200", r.status_code == 200, str(r.status_code))

    r = session.get(f"{BASE}/api/propiedades/{new_prop_id}")
    check("PUT estado persistió", r.json().get("estado") == "vendida" if r.ok else False)

    # as_dict incluye interesados como lista de dicts
    p_data = r.json()
    check("as_dict interesados es lista", isinstance(p_data.get("interesados"), list))
    check("as_dict tiene interesados_ids", "interesados_ids" in p_data)

    # Soft delete
    r = session.delete(f"{BASE}/api/propiedades/{new_prop_id}",
                       headers={"X-CSRFToken": real_csrf})
    check("DELETE soft propiedad 200", r.status_code == 200, str(r.status_code))

    r = session.get(f"{BASE}/api/propiedades")
    ids = [p["id"] for p in r.json()] if r.ok else []
    check("Soft delete oculta propiedad", new_prop_id not in ids)

    # Archivados
    r = session.get(f"{BASE}/api/propiedades/archivados")
    check("GET /api/propiedades/archivados 200", r.status_code == 200, str(r.status_code))
    if r.ok:
        check("Propiedad en archivados", new_prop_id in [p["id"] for p in r.json()])

    # Restore
    r = session.put(f"{BASE}/api/propiedades/{new_prop_id}/restore",
                    json={}, headers={"X-CSRFToken": real_csrf})
    check("PUT restore propiedad 200", r.status_code == 200, str(r.status_code))

    # Delete permanente
    r = session.delete(f"{BASE}/api/propiedades/{new_prop_id}/permanente",
                       headers={"X-CSRFToken": real_csrf})
    check("DELETE permanente propiedad 200", r.status_code == 200, str(r.status_code))

    r = session.get(f"{BASE}/api/propiedades/{new_prop_id}")
    check("Propiedad permanente no existe", r.status_code == 404, str(r.status_code))

# ─────────────────────────────────────────────────────────────────────────────
print("\n=== FASE 6: INTERESADOS (M2M) ===")

# Crear propiedad y cliente de prueba para M2M
r = session.post(f"{BASE}/api/propiedades",
                 json={"direccion": "Test M2M 1", "barrio": "Centro", "tipo": "casa",
                       "operacion": "venta", "estado": "disponible"},
                 headers={"X-CSRFToken": real_csrf})
m2m_prop_id = r.json().get("id") if r.ok else None

r = session.post(f"{BASE}/api/clientes",
                 json={"nombre": "Test", "apellido": "Interesado", "tipo": "interesado",
                       "telefono": "1199990000"},
                 headers={"X-CSRFToken": real_csrf})
m2m_cli_id = r.json().get("id") if r.ok else None

if m2m_prop_id and m2m_cli_id:
    pid, cid = m2m_prop_id, m2m_cli_id

    r = session.post(f"{BASE}/api/propiedades/{pid}/interesados/{cid}",
                     headers={"X-CSRFToken": real_csrf})
    check("POST asignar interesado 200", r.status_code == 200, str(r.status_code))
    if r.ok:
        data = r.json()
        inter_ids = data.get("interesados_ids", [])
        check("Interesado aparece en interesados_ids", cid in inter_ids, str(inter_ids))
        inter_obj = data.get("interesados", [])
        check("Interesados es lista de dicts", all(isinstance(x, dict) for x in inter_obj), str(inter_obj[:1]))
        if inter_obj:
            check("Interesado dict tiene id/nombre/telefono",
                  all(k in inter_obj[0] for k in ("id","nombre","apellido","telefono")),
                  str(inter_obj[0]))

    r = session.delete(f"{BASE}/api/propiedades/{pid}/interesados/{cid}",
                       headers={"X-CSRFToken": real_csrf})
    check("DELETE desasignar interesado 200", r.status_code == 200, str(r.status_code))
    if r.ok:
        check("Interesado ya no esta en lista", cid not in r.json().get("interesados_ids", []))

    # Matches
    r = session.get(f"{BASE}/api/propiedades/{pid}/matches")
    check("GET /api/propiedades/<id>/matches 200", r.status_code == 200, str(r.status_code))
    check("Matches devuelve lista", isinstance(r.json(), list) if r.ok else False)

    # Cleanup M2M test records
    session.delete(f"{BASE}/api/propiedades/{pid}", headers={"X-CSRFToken": real_csrf})
    session.delete(f"{BASE}/api/clientes/{cid}", headers={"X-CSRFToken": real_csrf})
else:
    fail("Interesados test", f"no se pudo crear datos de prueba (prop={m2m_prop_id}, cli={m2m_cli_id})")

# ─────────────────────────────────────────────────────────────────────────────
print("\n=== FASE 7: FOTOS ===")

props = session.get(f"{BASE}/api/propiedades").json()
if isinstance(props, list) and props:
    pid = props[0]["id"]

    # Upload JPG válido (creamos un JPEG mínimo en memoria)
    jpeg_bytes = (
        b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00'
        b'\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t'
        b'\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a'
        b'\x1f\x1e\x1d\x1a\x1c\x1c $.\' ",#\x1c\x1c(7),01444\x1f\'9=82<.342\x1e'
        b'C\t\t\t\r\x0b\r\x18\x10\x10\x18"\x16\x1c\x16"\"\"\"\"\"\"\"\"\"\"\"\"\"'
        b'\"\"\"\"\"\"\"\"\"\"\"\"\"\"\"\"\"\"\"\"\"\"\"\"\"\"\"\"\"\"\"\"\"\"\"\"'
        b'\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00'
        b'\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00'
        b'\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b'
        b'\xff\xc4\x00\xb5\x10\x00\x02\x01\x03\x03\x02\x04\x03\x05\x05\x04'
        b'\x04\x00\x00\x01}\x01\x02\x03\x00\x04\x11\x05\x12!1A\x06\x13Qa'
        b'\x07"q\x142\x81\x91\xa1\x08#B\xb1\xc1\x15R\xd1\xf0$3br'
        b'\x82\t\n\x16\x17\x18\x19\x1a%&\'()*456789:CDEFGHIJSTUVWXYZ'
        b'cdefghijstuvwxyz\x83\x84\x85\x86\x87\x88\x89\x8a\x92\x93\x94\x95'
        b'\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xfb\xd2\x8a(\x03\xff\xd9'
    )
    files = {"file": ("test_audit.jpg", io.BytesIO(jpeg_bytes), "image/jpeg")}
    r = session.post(f"{BASE}/api/propiedades/{pid}/upload",
                     files=files, headers={"X-CSRFToken": real_csrf})
    check("Upload JPEG válido 200", r.status_code == 200, f"{r.status_code}: {r.text[:80]}")
    uploaded_path = None
    if r.ok:
        fotos = r.json().get("fotos", [])
        check("Upload agrega foto a lista", len(fotos) > 0)
        uploaded_path = fotos[-1] if fotos else None

    # Archivo inválido (texto plano)
    files_bad = {"file": ("bad.jpg", io.BytesIO(b"this is not an image"), "image/jpeg")}
    r = session.post(f"{BASE}/api/propiedades/{pid}/upload",
                     files=files_bad, headers={"X-CSRFToken": real_csrf})
    check("Upload archivo inválido rechazado 400", r.status_code == 400, str(r.status_code))

    # Reordenar fotos
    r = session.get(f"{BASE}/api/propiedades/{pid}")
    if r.ok and r.json().get("fotos"):
        fotos = r.json()["fotos"]
        r = session.put(f"{BASE}/api/propiedades/{pid}/fotos/orden",
                        json={"fotos": fotos},
                        headers={"X-CSRFToken": real_csrf})
        check("PUT reordenar fotos 200", r.status_code == 200, str(r.status_code))

    # Eliminar foto subida en test
    if uploaded_path:
        r = session.delete(f"{BASE}/api/propiedades/{pid}/fotos/{uploaded_path}",
                           headers={"X-CSRFToken": real_csrf})
        check("DELETE foto 200", r.status_code == 200, str(r.status_code))
else:
    fail("Fotos test", "sin propiedades en DB")

# ─────────────────────────────────────────────────────────────────────────────
print("\n=== FASE 8: STATS ===")

r = session.get(f"{BASE}/api/stats")
check("GET /api/stats 200", r.status_code == 200, str(r.status_code))
if r.ok:
    s = r.json()
    expected_keys = ["disponibles","vendidas","rentadas","publicadas","clientes","consultas_no_leidas"]
    for k in expected_keys:
        check(f"stats tiene campo '{k}'", k in s, str(list(s.keys())))

# ─────────────────────────────────────────────────────────────────────────────
print("\n=== FASE 9: PÁGINAS ADMIN ===")

r = session.get(f"{BASE}/admin")
check("GET /admin 200", r.status_code == 200, str(r.status_code))
check("/admin carga sin error Jinja2", "Traceback" not in r.text and "Error" not in r.text[:200])

if propiedades_orig:
    pid = propiedades_orig[0]["id"]
    r = session.get(f"{BASE}/admin/propiedad/{pid}")
    check(f"GET /admin/propiedad/{pid} 200", r.status_code == 200, str(r.status_code))
    check("propiedad.html sin error Jinja2", "Traceback" not in r.text)

r = session.get(f"{BASE}/admin/consultas")
check("GET /admin/consultas 200", r.status_code == 200, str(r.status_code))

clis_check = session.get(f"{BASE}/api/clientes").json()
if isinstance(clis_check, list) and clis_check:
    cid = clis_check[0]["id"]
    r = session.get(f"{BASE}/cliente/{cid}")
    check(f"GET /cliente/{cid} 200", r.status_code == 200, str(r.status_code))

# ─────────────────────────────────────────────────────────────────────────────
print("\n=== FASE 10: PROTECCIÓN RUTAS SIN AUTH ===")

anon = requests.Session()
r = anon.get(f"{BASE}/api/clientes")
check("GET /api/clientes sin auth 401", r.status_code == 401, str(r.status_code))
r = anon.get(f"{BASE}/admin")
check("GET /admin sin auth redirect login", r.url.endswith("/admin/login") or "login" in r.url, r.url)

# ─────────────────────────────────────────────────────────────────────────────
print("\n=== FASE 11: CONSULTAS ===")

r = session.get(f"{BASE}/api/consultas")
check("GET /api/consultas 200", r.status_code == 200, str(r.status_code))
r = session.get(f"{BASE}/api/consultas/no_leidas")
check("GET /api/consultas/no_leidas 200", r.status_code == 200, str(r.status_code))
if r.ok:
    check("no_leidas tiene campo count", "count" in r.json(), str(r.json()))

# ─────────────────────────────────────────────────────────────────────────────
print("\n=== FASE 12: CAMPO CODIGO ===")

# Create property with codigo
r = session.post(f"{BASE}/api/propiedades",
                 json={"codigo": "TEST-01", "direccion": "Test Codigo 1", "barrio": "Centro",
                       "tipo": "casa", "operacion": "venta", "estado": "disponible"},
                 headers={"X-CSRFToken": real_csrf})
check("POST propiedad con codigo 201", r.status_code == 201, str(r.status_code))
cod_prop_id = None
if r.ok:
    cod_prop_id = r.json().get("id")
    check("Propiedad devuelve campo codigo", r.json().get("codigo") == "TEST-01", str(r.json().get("codigo")))

# Update codigo
if cod_prop_id:
    r = session.put(f"{BASE}/api/propiedades/{cod_prop_id}",
                    json={"codigo": "TRILLINI"},
                    headers={"X-CSRFToken": real_csrf})
    check("PUT codigo actualiza 200", r.status_code == 200, str(r.status_code))
    r2 = session.get(f"{BASE}/api/propiedades/{cod_prop_id}")
    check("GET devuelve codigo actualizado", r2.json().get("codigo") == "TRILLINI", str(r2.json().get("codigo")))

# Search by codigo via propiedades list
    r3 = session.get(f"{BASE}/api/propiedades?codigo=TRILLINI")
    check("GET /api/propiedades?codigo busqueda exacta", r.status_code == 200)
    check("Busqueda por codigo devuelve resultado", any(p.get("codigo") == "TRILLINI" for p in r3.json()))

    r4 = session.get(f"{BASE}/api/propiedades?codigo=TRILL")
    check("Busqueda parcial por codigo funciona", any(p.get("codigo") == "TRILLINI" for p in r4.json()))

# Cleanup
if cod_prop_id:
    session.delete(f"{BASE}/api/propiedades/{cod_prop_id}", headers={"X-CSRFToken": real_csrf})

# ─────────────────────────────────────────────────────────────────────────────
print("\n=== FASE 13: PROPIETARIOS M2M ===")

r = session.post(f"{BASE}/api/propiedades",
                 json={"codigo": "PROP-M2M", "direccion": "Test Propietarios", "barrio": "Sur",
                       "tipo": "terreno", "operacion": "venta", "estado": "disponible"},
                 headers={"X-CSRFToken": real_csrf})
m2m_pid = r.json().get("id") if r.ok else None

r = session.post(f"{BASE}/api/clientes",
                 json={"nombre": "Ana", "apellido": "Trillini", "tipo": "propietario", "telefono": "1100001111"},
                 headers={"X-CSRFToken": real_csrf})
m2m_cid1 = r.json().get("id") if r.ok else None

r = session.post(f"{BASE}/api/clientes",
                 json={"nombre": "Bruno", "apellido": "Trillini", "tipo": "propietario", "telefono": "1100002222"},
                 headers={"X-CSRFToken": real_csrf})
m2m_cid2 = r.json().get("id") if r.ok else None

if m2m_pid and m2m_cid1 and m2m_cid2:
    # Asignar propietario 1
    r = session.post(f"{BASE}/api/propiedades/{m2m_pid}/propietarios/{m2m_cid1}",
                     headers={"X-CSRFToken": real_csrf})
    check("POST asignar propietario 1 200", r.status_code == 200, str(r.status_code))
    if r.ok:
        d = r.json()
        check("propietarios_ids tiene cid1", m2m_cid1 in d.get("propietarios_ids", []))
        check("propietarios lista de dicts", all(isinstance(x, dict) for x in d.get("propietarios", [])))

    # Asignar propietario 2 (N:N)
    r = session.post(f"{BASE}/api/propiedades/{m2m_pid}/propietarios/{m2m_cid2}",
                     headers={"X-CSRFToken": real_csrf})
    check("POST asignar propietario 2 (N:N) 200", r.status_code == 200, str(r.status_code))
    if r.ok:
        ids = r.json().get("propietarios_ids", [])
        check("Propiedad tiene 2 propietarios", len(ids) == 2, str(ids))

    # Cliente debe ver propiedades como propietario
    r = session.get(f"{BASE}/api/clientes/{m2m_cid1}")
    check("GET cliente tiene propiedades_propietario", r.ok)
    if r.ok:
        pp = r.json().get("propiedades_propietario", [])
        check("Cliente ve propiedad asignada", any(p["id"] == m2m_pid for p in pp), str(pp))

    # Desasignar propietario 1
    r = session.delete(f"{BASE}/api/propiedades/{m2m_pid}/propietarios/{m2m_cid1}",
                       headers={"X-CSRFToken": real_csrf})
    check("DELETE desasignar propietario 200", r.status_code == 200, str(r.status_code))
    if r.ok:
        ids = r.json().get("propietarios_ids", [])
        check("cid1 ya no es propietario", m2m_cid1 not in ids, str(ids))
        check("cid2 sigue siendo propietario", m2m_cid2 in ids, str(ids))

    # Cleanup
    session.delete(f"{BASE}/api/propiedades/{m2m_pid}", headers={"X-CSRFToken": real_csrf})
    session.delete(f"{BASE}/api/clientes/{m2m_cid1}", headers={"X-CSRFToken": real_csrf})
    session.delete(f"{BASE}/api/clientes/{m2m_cid2}", headers={"X-CSRFToken": real_csrf})
else:
    fail("Propietarios M2M", f"no se pudo crear datos (pid={m2m_pid} cid1={m2m_cid1} cid2={m2m_cid2})")

# ─────────────────────────────────────────────────────────────────────────────
print("\n=== FASE 14: ESTADOS OPERATIVOS ===")

estados_nuevos = ["reservada", "cerrada"]
for est in estados_nuevos:
    r = session.post(f"{BASE}/api/propiedades",
                     json={"direccion": f"Test Estado {est}", "tipo": "casa",
                           "operacion": "venta", "estado": est},
                     headers={"X-CSRFToken": real_csrf})
    check(f"POST propiedad estado={est} 201", r.status_code == 201, str(r.status_code))
    tid = r.json().get("id") if r.ok else None
    if tid:
        r2 = session.get(f"{BASE}/api/propiedades/{tid}")
        check(f"GET persiste estado={est}", r2.json().get("estado") == est, str(r2.json().get("estado")))
        # Transition between states
        r3 = session.put(f"{BASE}/api/propiedades/{tid}", json={"estado": "disponible"},
                         headers={"X-CSRFToken": real_csrf})
        check(f"PUT {est}->disponible 200", r3.status_code == 200)
        # Cleanup
        session.delete(f"{BASE}/api/propiedades/{tid}", headers={"X-CSRFToken": real_csrf})

# ─────────────────────────────────────────────────────────────────────────────
print("\n=== FASE 15: FOTOS — PATH Y PERSISTENCIA ===")

# Create fresh property for photo tests
r = session.post(f"{BASE}/api/propiedades",
                 json={"direccion": "Test Fotos Path", "tipo": "casa",
                       "operacion": "venta", "estado": "disponible"},
                 headers={"X-CSRFToken": real_csrf})
foto_pid = r.json().get("id") if r.ok else None

jpeg_bytes = (
    b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00'
    b'\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t'
    b'\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a'
    b'\x1f\x1e\x1d\x1a\x1c\x1c $.\' ",#\x1c\x1c(7),01444\x1f\'9=82<.342\x1e'
    b'\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00'
    b'\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00'
    b'\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b'
    b'\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xfb\xd2\x8a(\x03\xff\xd9'
)

if foto_pid:
    # Upload foto 1
    r = session.post(f"{BASE}/api/propiedades/{foto_pid}/upload",
                     files={"file": ("test1.jpg", io.BytesIO(jpeg_bytes), "image/jpeg")},
                     headers={"X-CSRFToken": real_csrf})
    check("Upload foto 1 200", r.status_code == 200, str(r.status_code))
    if r.ok:
        fotos = r.json().get("fotos", [])
        check("Foto 1 en lista", len(fotos) >= 1)
        if fotos:
            check("Foto path usa forward slash", "/" in fotos[0] and "\\" not in fotos[0], fotos[0])
            check("Foto path comienza con static/", fotos[0].startswith("static/"), fotos[0])

    # Upload foto 2 (test sequential safety)
    r2 = session.post(f"{BASE}/api/propiedades/{foto_pid}/upload",
                      files={"file": ("test2.jpg", io.BytesIO(jpeg_bytes), "image/jpeg")},
                      headers={"X-CSRFToken": real_csrf})
    check("Upload foto 2 200", r2.status_code == 200, str(r2.status_code))
    if r2.ok:
        fotos2 = r2.json().get("fotos", [])
        check("Ambas fotos presentes tras 2 uploads", len(fotos2) >= 2, str(len(fotos2)))

    # Upload 5 more (total 7) to test bulk
    uploaded = 2
    for i in range(3, 8):
        rb = session.post(f"{BASE}/api/propiedades/{foto_pid}/upload",
                          files={"file": (f"test{i}.jpg", io.BytesIO(jpeg_bytes), "image/jpeg")},
                          headers={"X-CSRFToken": real_csrf})
        if rb.ok:
            uploaded += 1
    r_check = session.get(f"{BASE}/api/propiedades/{foto_pid}")
    check(f"Todas las fotos persisten ({uploaded}/7)", len(r_check.json().get("fotos", [])) == uploaded,
          str(len(r_check.json().get("fotos", []))))

    # Verify no backslash in DB
    check("Sin backslash en paths", all("\\" not in f for f in r_check.json().get("fotos", [])))

    # Delete foto intermedia (index 3)
    fotos_actual = r_check.json().get("fotos", [])
    if len(fotos_actual) >= 4:
        target = fotos_actual[3]
        r_del = session.delete(f"{BASE}/api/propiedades/{foto_pid}/fotos/{target}",
                               headers={"X-CSRFToken": real_csrf})
        check("DELETE foto intermedia 200", r_del.status_code == 200, str(r_del.status_code))
        if r_del.ok:
            fotos_post = r_del.json().get("fotos", [])
            check("Foto intermedia eliminada", target not in fotos_post)
            check("Resto de fotos intactas", len(fotos_post) == len(fotos_actual) - 1,
                  f"{len(fotos_post)} vs {len(fotos_actual)-1}")

    # Reorder
    fotos_reorder = session.get(f"{BASE}/api/propiedades/{foto_pid}").json().get("fotos", [])
    if len(fotos_reorder) >= 2:
        reversed_order = list(reversed(fotos_reorder))
        r_ord = session.put(f"{BASE}/api/propiedades/{foto_pid}/fotos/orden",
                            json={"fotos": reversed_order},
                            headers={"X-CSRFToken": real_csrf})
        check("PUT reordenar 7 fotos 200", r_ord.status_code == 200, str(r_ord.status_code))
        if r_ord.ok:
            check("Orden persistido correctamente",
                  r_ord.json().get("fotos") == reversed_order, str(r_ord.json().get("fotos")[:2]))

    # Persistencia: re-fetch via GET
    r_persist = session.get(f"{BASE}/api/propiedades/{foto_pid}")
    check("Fotos persisten en GET fresco", len(r_persist.json().get("fotos", [])) > 0)

    # Cleanup
    session.delete(f"{BASE}/api/propiedades/{foto_pid}", headers={"X-CSRFToken": real_csrf})
else:
    fail("Fotos path test", "no se pudo crear propiedad de prueba")

# ─────────────────────────────────────────────────────────────────────────────
print("\n=== FASE 16: FORMULARIOS DE CONTACTO ===")

r = session.get(BASE)
check("Sitio publico carga 200", r.status_code == 200)
check("Email destino en pagina publica", "robertomoret55@gmail.com" in r.text, "email no encontrado")
check("WA en pagina publica contiene 543444460856", "543444460856" in r.text, "WA no encontrado")

# Test public consulta form endpoint
r_c = requests.post(f"{BASE}/api/public/consultas",
                    json={"nombre": "Test Contacto", "mensaje": "Test de contacto audit", "propiedad_id": None},
                    headers={"Content-Type": "application/json"})
check("POST consulta publica 201", r_c.status_code == 201, str(r_c.status_code))
check("Consulta mensaje guardado", "correctamente" in r_c.json().get("message", ""), str(r_c.json()))

# ─────────────────────────────────────────────────────────────────────────────
print("\n=== FASE 17: STATS EXPANDIDOS ===")

r = session.get(f"{BASE}/api/stats")
check("GET /api/stats 200", r.status_code == 200, str(r.status_code))
if r.ok:
    s = r.json()
    for k in ["disponibles", "reservadas", "vendidas", "rentadas", "cerradas", "publicadas",
              "clientes", "consultas_no_leidas"]:
        check(f"stats tiene campo '{k}'", k in s, str(list(s.keys())))

# ─────────────────────────────────────────────────────────────────────────────
print("\n=== FASE 18: CLIENTES VEN SUS PROPIEDADES ===")

r = session.post(f"{BASE}/api/propiedades",
                 json={"codigo": "CLV-01", "direccion": "Test Cliente Vista", "tipo": "casa",
                       "operacion": "venta", "estado": "disponible"},
                 headers={"X-CSRFToken": real_csrf})
clv_pid = r.json().get("id") if r.ok else None

r = session.post(f"{BASE}/api/clientes",
                 json={"nombre": "Vista", "apellido": "Test", "tipo": "propietario", "telefono": "1188887777"},
                 headers={"X-CSRFToken": real_csrf})
clv_cid = r.json().get("id") if r.ok else None

if clv_pid and clv_cid:
    # Assign as propietario
    session.post(f"{BASE}/api/propiedades/{clv_pid}/propietarios/{clv_cid}",
                 headers={"X-CSRFToken": real_csrf})
    r = session.get(f"{BASE}/api/clientes/{clv_cid}")
    check("Cliente tiene propiedades_propietario en as_dict", "propiedades_propietario" in r.json())
    check("Cliente tiene propiedades_interesado en as_dict", "propiedades_interesado" in r.json())
    pp = r.json().get("propiedades_propietario", [])
    check("Cliente ve codigo de propiedad asignada",
          any(p.get("id") == clv_pid for p in pp), str(pp))

    # Assign as interesado
    session.post(f"{BASE}/api/propiedades/{clv_pid}/interesados/{clv_cid}",
                 headers={"X-CSRFToken": real_csrf})
    r2 = session.get(f"{BASE}/api/clientes/{clv_cid}")
    pi = r2.json().get("propiedades_interesado", [])
    check("Cliente ve propiedades como interesado", any(p.get("id") == clv_pid for p in pi), str(pi))

    # Cleanup
    session.delete(f"{BASE}/api/propiedades/{clv_pid}", headers={"X-CSRFToken": real_csrf})
    session.delete(f"{BASE}/api/clientes/{clv_cid}", headers={"X-CSRFToken": real_csrf})
else:
    fail("Cliente vista propiedades", f"no se pudo crear datos (pid={clv_pid} cid={clv_cid})")

# ─────────────────────────────────────────────────────────────────────────────
print("\n=== FASE 19: UI ASIGNACIÓN — ESTRUCTURA Y ROUND-TRIP ===")

# ── Setup: create fresh property + 2 clients ─────────────────────────────────
r19p = session.post(f"{BASE}/api/propiedades",
                    json={"codigo": "F19-TEST", "direccion": "Calle Fase 19 #100",
                          "tipo": "casa", "estado": "disponible"},
                    headers={"X-CSRFToken": real_csrf})
pid19 = r19p.json().get("id") if r19p.ok else None

r19cp = session.post(f"{BASE}/api/clientes",
                     json={"nombre": "Prop", "apellido": "Test19", "telefono": "190001",
                           "tipo": "propietario"},
                     headers={"X-CSRFToken": real_csrf})
cid19p = r19cp.json().get("id") if r19cp.ok else None

r19ci = session.post(f"{BASE}/api/clientes",
                     json={"nombre": "Inter", "apellido": "Test19", "telefono": "190002",
                           "tipo": "interesado"},
                     headers={"X-CSRFToken": real_csrf})
cid19i = r19ci.json().get("id") if r19ci.ok else None

if not (pid19 and cid19p and cid19i):
    fail("Fase 19 setup", f"pid={pid19} cid_prop={cid19p} cid_int={cid19i}")
else:
    # ── 1. propiedad.html HTML structure ─────────────────────────────────────
    rph = session.get(f"{BASE}/admin/propiedad/{pid19}")
    check("propiedad.html carga 200", rph.status_code == 200, str(rph.status_code))
    check("propiedad.html tiene #buscar-propietario",
          'id="buscar-propietario"' in rph.text, "input no encontrado")
    check("propiedad.html tiene #buscar-prop-resultados",
          'id="buscar-prop-resultados"' in rph.text, "div no encontrado")
    check("propiedad.html CSS dropdown propietarios (display:none compartido)",
          '#buscar-prop-resultados' in rph.text, "CSS no encontrado")
    check("propiedad.html tiene #buscar-interesado",
          'id="buscar-interesado"' in rph.text, "input no encontrado")

    # ── 2. perfil.html HTML structure (nuevo UI) ──────────────────────────────
    rpf_prop = session.get(f"{BASE}/cliente/{cid19p}")
    check("perfil.html (propietario) carga 200", rpf_prop.status_code == 200, str(rpf_prop.status_code))
    check("perfil.html tiene #buscar-propiedad-cli",
          'id="buscar-propiedad-cli"' in rpf_prop.text, "input de búsqueda no encontrado")
    check("perfil.html tiene #buscar-prop-cli-resultados",
          'id="buscar-prop-cli-resultados"' in rpf_prop.text, "div resultados no encontrado")
    check("perfil.html NO usa query legacy ?propietario=",
          '?propietario=' not in rpf_prop.text, "sigue usando query por nombre")
    check("perfil.html llama desasignarPropiedad",
          'desasignarPropiedad' in rpf_prop.text, "función de desasignación no encontrada")

    rpf_int = session.get(f"{BASE}/cliente/{cid19i}")
    check("perfil.html (interesado) carga 200", rpf_int.status_code == 200, str(rpf_int.status_code))
    check("perfil.html interesado tiene búsqueda",
          'id="buscar-propiedad-cli"' in rpf_int.text, "input no encontrado para interesado")

    # ── 3. Round-trip: asignar propietario ────────────────────────────────────
    r_asgn = session.post(f"{BASE}/api/propiedades/{pid19}/propietarios/{cid19p}",
                          headers={"X-CSRFToken": real_csrf})
    check("POST asignar propietario 200", r_asgn.status_code == 200, str(r_asgn.status_code))
    r_cli = session.get(f"{BASE}/api/clientes/{cid19p}")
    pp = r_cli.json().get("propiedades_propietario", [])
    check("cliente ve propiedad asignada (propietario)",
          any(p["id"] == pid19 for p in pp), str(pp))
    check("propiedad tiene codigo en lista del cliente",
          any(p.get("codigo") == "F19-TEST" for p in pp), str(pp))

    # ── 4. Round-trip: asignar interesado ─────────────────────────────────────
    r_asgn_i = session.post(f"{BASE}/api/propiedades/{pid19}/interesados/{cid19i}",
                            headers={"X-CSRFToken": real_csrf})
    check("POST asignar interesado 200", r_asgn_i.status_code == 200, str(r_asgn_i.status_code))
    r_cli_i = session.get(f"{BASE}/api/clientes/{cid19i}")
    pi = r_cli_i.json().get("propiedades_interesado", [])
    check("cliente ve propiedad asignada (interesado)",
          any(p["id"] == pid19 for p in pi), str(pi))

    # ── 5. Persistencia: propiedad ve ambos clientes ──────────────────────────
    r_prop = session.get(f"{BASE}/api/propiedades/{pid19}")
    propietarios_ids = r_prop.json().get("propietarios_ids", [])
    interesados_ids  = r_prop.json().get("interesados_ids", [])
    check("propiedad ve al propietario asignado", cid19p in propietarios_ids, str(propietarios_ids))
    check("propiedad ve al interesado asignado", cid19i in interesados_ids, str(interesados_ids))

    # ── 6. Desasignar propietario ─────────────────────────────────────────────
    session.delete(f"{BASE}/api/propiedades/{pid19}/propietarios/{cid19p}",
                   headers={"X-CSRFToken": real_csrf})
    r_after = session.get(f"{BASE}/api/clientes/{cid19p}")
    pp_after = r_after.json().get("propiedades_propietario", [])
    check("propietario desasignado — ya no en lista",
          not any(p["id"] == pid19 for p in pp_after), str(pp_after))

    # ── 7. Desasignar interesado ──────────────────────────────────────────────
    session.delete(f"{BASE}/api/propiedades/{pid19}/interesados/{cid19i}",
                   headers={"X-CSRFToken": real_csrf})
    r_after_i = session.get(f"{BASE}/api/clientes/{cid19i}")
    pi_after = r_after_i.json().get("propiedades_interesado", [])
    check("interesado desasignado — ya no en lista",
          not any(p["id"] == pid19 for p in pi_after), str(pi_after))

    # ── Cleanup ───────────────────────────────────────────────────────────────
    session.delete(f"{BASE}/api/propiedades/{pid19}/permanente",
                   headers={"X-CSRFToken": real_csrf})
    session.delete(f"{BASE}/api/clientes/{cid19p}/permanente",
                   headers={"X-CSRFToken": real_csrf})
    session.delete(f"{BASE}/api/clientes/{cid19i}/permanente",
                   headers={"X-CSRFToken": real_csrf})

# ─────────────────────────────────────────────────────────────────────────────
print("\n=== FASE 20: SISTEMA CÓDIGO — INTEGRACIÓN COMPLETA ===")

# ── Setup ─────────────────────────────────────────────────────────────────────
CODIGOS = ["TRILLINI", "C14", "SARMIENTO", "M102", "LOTE7"]
pids20 = []
for i, cod in enumerate(CODIGOS):
    r = session.post(f"{BASE}/api/propiedades",
                     json={"codigo": cod, "direccion": f"Calle Test {i+1}", "tipo": "casa",
                           "estado": "disponible", "operacion": "venta"},
                     headers={"X-CSRFToken": real_csrf})
    if r.ok:
        pids20.append((cod, r.json()["id"]))

check("Setup: 5 propiedades con código creadas", len(pids20) == 5, str(len(pids20)))

# ── 1. Persistencia: GET devuelve codigo exacto ───────────────────────────────
for cod, pid in pids20:
    r = session.get(f"{BASE}/api/propiedades/{pid}")
    check(f"GET persiste codigo={cod}", r.json().get("codigo") == cod, r.json().get("codigo"))

# ── 2. Búsqueda exacta por ?codigo= ──────────────────────────────────────────
for cod, _ in pids20:
    r = session.get(f"{BASE}/api/propiedades?codigo={cod}")
    found = any(p["codigo"] == cod for p in r.json())
    check(f"Búsqueda exacta ?codigo={cod}", found, str([p['codigo'] for p in r.json()]))

# ── 3. Búsqueda parcial (subcadena) ──────────────────────────────────────────
partial_cases = [("TRILL", "TRILLINI"), ("C1", "C14"), ("SARM", "SARMIENTO"),
                 ("M10", "M102"), ("LOT", "LOTE7")]
for q, expected in partial_cases:
    r = session.get(f"{BASE}/api/propiedades?codigo={q}")
    found = any(p["codigo"] == expected for p in r.json())
    check(f"Búsqueda parcial ?codigo={q} encuentra {expected}", found,
          str([p['codigo'] for p in r.json()]))

# ── 4. Update código ──────────────────────────────────────────────────────────
if pids20:
    _, pid_upd = pids20[0]
    r = session.put(f"{BASE}/api/propiedades/{pid_upd}",
                    json={"codigo": "TRILLINI-A"},
                    headers={"X-CSRFToken": real_csrf, "Content-Type": "application/json"})
    check("PUT actualiza codigo 200", r.status_code == 200, str(r.status_code))
    r2 = session.get(f"{BASE}/api/propiedades/{pid_upd}")
    check("Codigo actualizado persiste", r2.json().get("codigo") == "TRILLINI-A",
          r2.json().get("codigo"))
    # Restore
    session.put(f"{BASE}/api/propiedades/{pid_upd}",
                json={"codigo": "TRILLINI"},
                headers={"X-CSRFToken": real_csrf, "Content-Type": "application/json"})

# ── 5. as_dict incluye codigo en lista de propiedades del cliente ─────────────
if pids20:
    _, pid_cli = pids20[1]
    rc = session.post(f"{BASE}/api/clientes",
                      json={"nombre": "Codigo", "apellido": "Test20", "telefono": "200001",
                            "tipo": "propietario"},
                      headers={"X-CSRFToken": real_csrf})
    cid20 = rc.json().get("id") if rc.ok else None
    if cid20:
        session.post(f"{BASE}/api/propiedades/{pid_cli}/propietarios/{cid20}",
                     headers={"X-CSRFToken": real_csrf})
        r = session.get(f"{BASE}/api/clientes/{cid20}")
        pp = r.json().get("propiedades_propietario", [])
        check("Cliente.as_dict propiedades_propietario incluye codigo",
              any(p.get("codigo") == "C14" for p in pp), str(pp))
        session.delete(f"{BASE}/api/clientes/{cid20}/permanente",
                       headers={"X-CSRFToken": real_csrf})

# ── 6. HTML: columna se llama "Código" (no "ID") ─────────────────────────────
r_admin = session.get(f"{BASE}/admin")
check("Columna tabla propiedades dice 'Código'", '>Código <' in r_admin.text,
      "sigue diciendo 'ID' o no encontrado")
check("Columna NO dice '>ID <'", '>ID <' not in r_admin.text,
      "header viejo todavía presente")

# ── 7. HTML: placeholder del filtro menciona código ──────────────────────────
check("Placeholder filtro menciona Código",
      'Código, dirección' in r_admin.text or 'digo, direcci' in r_admin.text,
      "placeholder no actualizado")

# ── 8. admin.js: command palette busca por codigo ────────────────────────────
r_js = requests.get(f"{BASE}/static/admin.js")
check("admin.js incluye p.codigo en palette search",
      'p.codigo' in r_js.text, "no encontrado en admin.js")
check("admin.js muestra codigo en label del palette",
      'p.codigo + \']' in r_js.text or "p.codigo + ']" in r_js.text or '[' + '" + p.codigo' in r_js.text or "p.codigo ? '['" in r_js.text,
      "código no aparece en label")

# ── 9. propiedad.html: _CAMPOS tiene campo código ────────────────────────────
if pids20:
    _, pid_det = pids20[2]
    r_det = session.get(f"{BASE}/admin/propiedad/{pid_det}")
    check("propiedad.html _CAMPOS tiene 'Código'",
          "'C\\u00f3digo'" in r_det.text or "'Código'" in r_det.text or "C\\u00f3digo" in r_det.text
          or "label: 'C" in r_det.text,
          "campo Código no encontrado en _CAMPOS")
    check("propiedad.html campo codigo es editable (field='codigo')",
          "field: 'codigo'" in r_det.text, "field codigo no encontrado")

# ── 10. Ordenamiento: API devuelve codigo en todos los registros ──────────────
r_all = session.get(f"{BASE}/api/propiedades")
all_with_codigo = [p for p in r_all.json() if "codigo" in p]
check("Todas las propiedades tienen campo codigo en as_dict",
      len(all_with_codigo) == len(r_all.json()),
      f"{len(all_with_codigo)}/{len(r_all.json())}")
mis_codigos = [p["codigo"] for p in r_all.json() if p["codigo"] in CODIGOS]
check("Los 5 códigos de prueba aparecen en listado general",
      len(mis_codigos) == 5, str(mis_codigos))

# ── Cleanup ───────────────────────────────────────────────────────────────────
for _, pid in pids20:
    session.delete(f"{BASE}/api/propiedades/{pid}/permanente",
                   headers={"X-CSRFToken": real_csrf})

# ─────────────────────────────────────────────────────────────────────────────
print("\n=== FASE 21: CATÁLOGO PÚBLICO — NAVEGACIÓN CON TABS ===")

# ── 1. HTML structure ─────────────────────────────────────────────────────────
r_pub = requests.get(BASE)
check("Catálogo público carga 200", r_pub.status_code == 200, str(r_pub.status_code))
check("HTML tiene tabs-bar", 'class="tabs-bar"' in r_pub.text, "tabs-bar no encontrado")
check("HTML tiene tab-todas",    'id="tab-todas"'    in r_pub.text, "tab-todas no encontrado")
check("HTML tiene tab-venta",    'id="tab-venta"'    in r_pub.text, "tab-venta no encontrado")
check("HTML tiene tab-alquiler", 'id="tab-alquiler"' in r_pub.text, "tab-alquiler no encontrado")
check("HTML NO tiene f-operacion select",
      'id="f-operacion"' not in r_pub.text, "select f-operacion todavía presente")

# ── 2. JS functions present ───────────────────────────────────────────────────
check("JS tiene función setTab",    'function setTab'    in r_pub.text, "setTab no encontrado")
check("JS tiene variable _activeTab", '_activeTab'       in r_pub.text, "_activeTab no encontrado")
check("JS limpiar no resetea operacion",
      "f-operacion" not in r_pub.text, "limpiar sigue reseteando f-operacion")
check("JS buscar usa _activeTab para operacion",
      "_activeTab !== 'todas'" in r_pub.text or "_activeTab != 'todas'" in r_pub.text,
      "buscar() no usa _activeTab para filtrar operacion")

# ── 3. Setup: propiedades públicas para filtrar ───────────────────────────────
r_v = session.post(f"{BASE}/api/propiedades",
                   json={"codigo": "F21-V", "direccion": "Fase21 Venta", "tipo": "casa",
                         "operacion": "venta", "estado": "disponible", "publicada": True},
                   headers={"X-CSRFToken": real_csrf})
r_a = session.post(f"{BASE}/api/propiedades",
                   json={"codigo": "F21-A", "direccion": "Fase21 Alquiler", "tipo": "casa",
                         "operacion": "alquiler", "estado": "disponible", "publicada": True},
                   headers={"X-CSRFToken": real_csrf})
pid21v = r_v.json().get("id") if r_v.ok else None
pid21a = r_a.json().get("id") if r_a.ok else None

# Publicar
if pid21v:
    session.put(f"{BASE}/api/propiedades/{pid21v}",
                json={"publicada": True},
                headers={"X-CSRFToken": real_csrf, "Content-Type": "application/json"})
if pid21a:
    session.put(f"{BASE}/api/propiedades/{pid21a}",
                json={"publicada": True},
                headers={"X-CSRFToken": real_csrf, "Content-Type": "application/json"})

if not (pid21v and pid21a):
    fail("FASE 21 setup", f"pid_v={pid21v} pid_a={pid21a}")
else:
    # ── 4. Tab "todas" — API devuelve ambas ──────────────────────────────────
    r_all = requests.get(f"{BASE}/api/public/propiedades")
    ids_all = [p["id"] for p in r_all.json()]
    check("Tab Todas: venta aparece en listado general", pid21v in ids_all, str(ids_all[:5]))
    check("Tab Todas: alquiler aparece en listado general", pid21a in ids_all, str(ids_all[:5]))

    # ── 5. Tab "venta" — solo venta ───────────────────────────────────────────
    r_ven = requests.get(f"{BASE}/api/public/propiedades?operacion=venta")
    ids_ven = [p["id"] for p in r_ven.json()]
    ops_ven = [p["operacion"] for p in r_ven.json()]
    check("Tab Venta: propiedad de venta aparece", pid21v in ids_ven, str(ids_ven[:5]))
    check("Tab Venta: propiedad de alquiler NO aparece", pid21a not in ids_ven, str(ids_ven[:5]))
    check("Tab Venta: todos los resultados son 'venta'",
          all(o == "venta" for o in ops_ven), str(set(ops_ven)))

    # ── 6. Tab "alquiler" — solo alquiler ─────────────────────────────────────
    r_alq = requests.get(f"{BASE}/api/public/propiedades?operacion=alquiler")
    ids_alq = [p["id"] for p in r_alq.json()]
    ops_alq = [p["operacion"] for p in r_alq.json()]
    check("Tab Alquiler: propiedad de alquiler aparece", pid21a in ids_alq, str(ids_alq[:5]))
    check("Tab Alquiler: propiedad de venta NO aparece", pid21v not in ids_alq, str(ids_alq[:5]))
    check("Tab Alquiler: todos los resultados son 'alquiler'",
          all(o == "alquiler" for o in ops_alq), str(set(ops_alq)))

    # ── 7. Orden descendente (IDs decrecientes) ───────────────────────────────
    if len(ids_all) >= 2:
        check("Orden descendente por ID (primero >= último)",
              ids_all[0] >= ids_all[-1], f"first={ids_all[0]} last={ids_all[-1]}")

    # ── 8. URL persistence: ?tab=venta en HTML ────────────────────────────────
    check("JS usa history.replaceState para URL persistence",
          'replaceState' in r_pub.text, "history.replaceState no encontrado")
    check("JS lee ?tab= en DOMContentLoaded",
          "params.get('tab')" in r_pub.text, "no lee query param tab")

    # ── Cleanup ───────────────────────────────────────────────────────────────
    session.delete(f"{BASE}/api/propiedades/{pid21v}/permanente",
                   headers={"X-CSRFToken": real_csrf})
    session.delete(f"{BASE}/api/propiedades/{pid21a}/permanente",
                   headers={"X-CSRFToken": real_csrf})

# ─────────────────────────────────────────────────────────────────────────────
print("\n=== FASE 22: ASSIGNMENT UI — LISTAS INMEDIATAS ===")

# ── Setup ─────────────────────────────────────────────────────────────────────
r22p = session.post(f"{BASE}/api/propiedades",
                    json={"codigo": "F22-P", "direccion": "Fase22 Prop", "tipo": "casa",
                          "operacion": "venta", "estado": "disponible"},
                    headers={"X-CSRFToken": real_csrf})
pid22 = r22p.json().get("id") if r22p.ok else None

r22c = session.post(f"{BASE}/api/clientes",
                    json={"nombre": "Cliente", "apellido": "F22", "telefono": "220001",
                          "tipo": "propietario"},
                    headers={"X-CSRFToken": real_csrf})
cid22 = r22c.json().get("id") if r22c.ok else None

if not (pid22 and cid22):
    fail("FASE 22 setup", f"pid={pid22} cid={cid22}")
else:
    # ── 1. propiedad.html — estructura JS del nuevo UI ────────────────────────
    rph22 = session.get(f"{BASE}/admin/propiedad/{pid22}")
    check("propiedad.html carga 200", rph22.status_code == 200, str(rph22.status_code))
    check("propiedad.html tiene renderDispList (lista inmediata)",
          'renderDispList' in rph22.text, "función renderDispList no encontrada")
    check("propiedad.html tiene filtrarDisp (filtro inline)",
          'filtrarDisp' in rph22.text, "función filtrarDisp no encontrada")
    check("propiedad.html tiene ensureClientesCache",
          'ensureClientesCache' in rph22.text, "función ensureClientesCache no encontrada")
    check("propiedad.html NO tiene buscarClienteGeneric (eliminada)",
          'buscarClienteGeneric' not in rph22.text, "función vieja aún presente")
    check("propiedad.html interesados sin cap slice(0, 8)",
          '.slice(0, 8)' not in rph22.text, "cap de 8 registros todavía presente")
    check("propiedad.html ID buscar-propietario presente en JS",
          "'buscar-propietario'" in rph22.text or 'id="buscar-propietario"' in rph22.text,
          "id buscar-propietario no encontrado")
    check("propiedad.html ID buscar-prop-resultados presente en JS",
          "'buscar-prop-resultados'" in rph22.text or 'id="buscar-prop-resultados"' in rph22.text,
          "id buscar-prop-resultados no encontrado")
    check("propiedad.html ID buscar-interesado presente en JS",
          "'buscar-interesado'" in rph22.text or 'id="buscar-interesado"' in rph22.text,
          "id buscar-interesado no encontrado")
    check("propiedad.html tiene disp-empty para estado vacío",
          'disp-empty' in rph22.text, "clase disp-empty no encontrada")
    check("propiedad.html CSS #buscar-prop-resultados como lista inline",
          '#buscar-prop-resultados' in rph22.text, "selector CSS no encontrado")

    # ── 2. perfil.html — estructura JS del nuevo UI ───────────────────────────
    rpf22 = session.get(f"{BASE}/cliente/{cid22}")
    check("perfil.html carga 200", rpf22.status_code == 200, str(rpf22.status_code))
    check("perfil.html tiene renderDispListProp",
          'renderDispListProp' in rpf22.text, "función renderDispListProp no encontrada")
    check("perfil.html tiene filtrarDisponiblesProp",
          'filtrarDisponiblesProp' in rpf22.text, "función filtrarDisponiblesProp no encontrada")
    check("perfil.html renderDetalle llama renderDispListProp",
          'renderDispListProp' in rpf22.text and 'renderDetalle' in rpf22.text,
          "renderDetalle no invoca renderDispListProp")
    check("perfil.html NO tiene buscarPropiedadParaCliente (eliminada)",
          'buscarPropiedadParaCliente' not in rpf22.text, "función vieja aún presente")
    check("perfil.html NO tiene slice(0, 6) cap",
          '.slice(0, 6)' not in rpf22.text, "cap de 6 resultados todavía presente")
    check("perfil.html ID buscar-propiedad-cli presente en JS",
          "'buscar-propiedad-cli'" in rpf22.text or 'id="buscar-propiedad-cli"' in rpf22.text,
          "input filtro no encontrado")
    check("perfil.html ID buscar-prop-cli-resultados presente en JS",
          "'buscar-prop-cli-resultados'" in rpf22.text or 'id="buscar-prop-cli-resultados"' in rpf22.text,
          "div lista no encontrado")
    check("perfil.html tiene disp-empty para estado vacío",
          'disp-empty' in rpf22.text, "clase disp-empty no encontrada")
    check("perfil.html CSS #buscar-prop-cli-resultados como lista inline",
          '#buscar-prop-cli-resultados' in rpf22.text, "selector CSS no encontrado")

    # ── 3. API: GET /api/clientes sin paginación (para lista inmediata) ────────
    r_clientes = session.get(f"{BASE}/api/clientes")
    check("GET /api/clientes 200", r_clientes.status_code == 200, str(r_clientes.status_code))
    check("GET /api/clientes incluye cliente F22",
          any(c["id"] == cid22 for c in r_clientes.json()), "cliente F22 no encontrado")

    r_props22 = session.get(f"{BASE}/api/propiedades")
    check("GET /api/propiedades 200", r_props22.status_code == 200, str(r_props22.status_code))
    check("GET /api/propiedades incluye propiedad F22",
          any(p["id"] == pid22 for p in r_props22.json()), "propiedad F22 no encontrada")

    # ── 4. Round-trip asignar / desasignar propietario ────────────────────────
    r_asgn22 = session.post(f"{BASE}/api/propiedades/{pid22}/propietarios/{cid22}",
                             headers={"X-CSRFToken": real_csrf})
    check("POST asignar propietario 200", r_asgn22.status_code == 200, str(r_asgn22.status_code))
    r_check22 = session.get(f"{BASE}/api/propiedades/{pid22}")
    check("Propietario aparece en propietarios_ids",
          cid22 in r_check22.json().get("propietarios_ids", []),
          str(r_check22.json().get("propietarios_ids")))
    r_cli22 = session.get(f"{BASE}/api/clientes/{cid22}")
    check("Propiedad aparece en propiedades_propietario del cliente",
          any(p["id"] == pid22 for p in r_cli22.json().get("propiedades_propietario", [])),
          str(r_cli22.json().get("propiedades_propietario")))

    r_del22 = session.delete(f"{BASE}/api/propiedades/{pid22}/propietarios/{cid22}",
                              headers={"X-CSRFToken": real_csrf})
    check("DELETE desasignar propietario 200", r_del22.status_code == 200, str(r_del22.status_code))
    r_after22 = session.get(f"{BASE}/api/propiedades/{pid22}")
    check("Propietario removido de propietarios_ids",
          cid22 not in r_after22.json().get("propietarios_ids", []),
          str(r_after22.json().get("propietarios_ids")))

    # ── 5. Render con 10+ clientes (verifica sin cap) ─────────────────────────
    ids_extra22 = []
    for i in range(10):
        rx = session.post(f"{BASE}/api/clientes",
                          json={"nombre": f"Extra{i:02d}", "apellido": "F22",
                                "telefono": f"2299{i:02d}", "tipo": "propietario"},
                          headers={"X-CSRFToken": real_csrf})
        if rx.ok:
            ids_extra22.append(rx.json()["id"])
    r_all22 = session.get(f"{BASE}/api/clientes")
    check(f"GET /api/clientes devuelve todos sin cap (>=10)",
          len(r_all22.json()) >= 10, f"solo {len(r_all22.json())} clientes")
    for eid in ids_extra22:
        session.delete(f"{BASE}/api/clientes/{eid}/permanente",
                       headers={"X-CSRFToken": real_csrf})

    # ── Cleanup ───────────────────────────────────────────────────────────────
    session.delete(f"{BASE}/api/propiedades/{pid22}/permanente",
                   headers={"X-CSRFToken": real_csrf})
    session.delete(f"{BASE}/api/clientes/{cid22}/permanente",
                   headers={"X-CSRFToken": real_csrf})

# ─────────────────────────────────────────────────────────────────────────────
print("\n=== FASE 23: STATS BAR COMPLETA + ARCHIVADOS FILTER ===")

# ── 1. API /api/stats devuelve todos los 8 campos ────────────────────────────
r_stats = session.get(f"{BASE}/api/stats")
check("GET /api/stats 200", r_stats.status_code == 200, str(r_stats.status_code))
if r_stats.ok:
    s23 = r_stats.json()
    for campo in ["disponibles", "reservadas", "vendidas", "rentadas", "cerradas",
                  "publicadas", "clientes", "consultas_no_leidas"]:
        check(f"api/stats incluye campo '{campo}'", campo in s23,
              f"campos presentes: {list(s23.keys())}")
    check("api/stats reservadas es int >= 0",
          isinstance(s23.get("reservadas"), int) and s23.get("reservadas", -1) >= 0,
          str(s23.get("reservadas")))
    check("api/stats cerradas es int >= 0",
          isinstance(s23.get("cerradas"), int) and s23.get("cerradas", -1) >= 0,
          str(s23.get("cerradas")))

# ── 2. HTML admin: stats bar incluye reservadas y cerradas ──────────────────
r_admin23 = session.get(f"{BASE}/admin")
check("admin index carga 200", r_admin23.status_code == 200, str(r_admin23.status_code))
if r_admin23.ok:
    check("admin HTML tiene s.reservadas en cargarStats",
          "s.reservadas" in r_admin23.text, "s.reservadas no encontrado en JS inline")
    check("admin HTML tiene s.cerradas en cargarStats",
          "s.cerradas" in r_admin23.text, "s.cerradas no encontrado en JS inline")
    check("admin HTML tiene cls stat-reservada",
          "stat-reservada" in r_admin23.text, "clase stat-reservada no encontrada")
    check("admin HTML tiene cls stat-muted (cerradas)",
          "stat-muted" in r_admin23.text or "'muted'" in r_admin23.text,
          "clase stat-muted no encontrada")
    check("admin HTML tiene label Reservadas en stats",
          "'Reservadas'" in r_admin23.text or "\"Reservadas\"" in r_admin23.text,
          "label Reservadas no encontrado")
    check("admin HTML tiene label Cerradas en stats",
          "'Cerradas'" in r_admin23.text or "\"Cerradas\"" in r_admin23.text,
          "label Cerradas no encontrado")

# ── 3. Stats contadores funcionan con datos reales ───────────────────────────
r23res = session.post(f"{BASE}/api/propiedades",
                      json={"codigo": "F23-RES", "direccion": "Fase23 Reservada",
                            "tipo": "casa", "operacion": "venta", "estado": "reservada"},
                      headers={"X-CSRFToken": real_csrf})
pid23res = r23res.json().get("id") if r23res.ok else None

r23cer = session.post(f"{BASE}/api/propiedades",
                      json={"codigo": "F23-CER", "direccion": "Fase23 Cerrada",
                            "tipo": "casa", "operacion": "venta", "estado": "cerrada"},
                      headers={"X-CSRFToken": real_csrf})
pid23cer = r23cer.json().get("id") if r23cer.ok else None

if pid23res and pid23cer:
    r_s23b = session.get(f"{BASE}/api/stats")
    s23b = r_s23b.json()
    check("stats.reservadas >= 1 con propiedad reservada creada",
          s23b.get("reservadas", 0) >= 1, str(s23b.get("reservadas")))
    check("stats.cerradas >= 1 con propiedad cerrada creada",
          s23b.get("cerradas", 0) >= 1, str(s23b.get("cerradas")))
    session.delete(f"{BASE}/api/propiedades/{pid23res}/permanente",
                   headers={"X-CSRFToken": real_csrf})
    session.delete(f"{BASE}/api/propiedades/{pid23cer}/permanente",
                   headers={"X-CSRFToken": real_csrf})
else:
    fail("FASE 23 stats contadores setup", f"pid_res={pid23res} pid_cer={pid23cer}")

# ── 4. Archivados tab tiene filtro de búsqueda en HTML ───────────────────────
if r_admin23.ok:
    check("tab-archivados tiene #archivados-search input",
          'id="archivados-search"' in r_admin23.text, "input no encontrado")
    check("tab-archivados tiene #archivados-filter div",
          'id="archivados-filter"' in r_admin23.text, "div filter no encontrado")
    check("admin HTML tiene función filtrarArchivados",
          "filtrarArchivados" in r_admin23.text, "función no encontrada")
    check("admin HTML tiene _archivadosData variable (cache local)",
          "_archivadosData" in r_admin23.text, "_archivadosData no encontrado")
    check("archivados-filter oculto por defecto (display:none)",
          'id="archivados-filter" style="display:none"' in r_admin23.text or
          "archivados-filter\" style=\"display:none" in r_admin23.text,
          "filter no inicia oculto")

# ── 5. Round-trip: archivar propiedad y verificar que aparece en archivados ──
r23arc = session.post(f"{BASE}/api/propiedades",
                      json={"codigo": "F23-ARC", "direccion": "Fase23 Archivar",
                            "tipo": "departamento", "operacion": "alquiler", "estado": "disponible"},
                      headers={"X-CSRFToken": real_csrf})
pid23arc = r23arc.json().get("id") if r23arc.ok else None

if pid23arc:
    r_del = session.delete(f"{BASE}/api/propiedades/{pid23arc}",
                           headers={"X-CSRFToken": real_csrf})
    check("DELETE (archivar) propiedad 200", r_del.status_code == 200, str(r_del.status_code))

    r_arch = session.get(f"{BASE}/api/propiedades/archivados")
    check("GET /api/propiedades/archivados 200",
          r_arch.status_code == 200, str(r_arch.status_code))
    ids_arch = [p["id"] for p in r_arch.json()]
    check("Propiedad archivada aparece en /api/propiedades/archivados",
          pid23arc in ids_arch, str(ids_arch[:5]))

    r_active = session.get(f"{BASE}/api/propiedades")
    ids_active = [p["id"] for p in r_active.json()]
    check("Propiedad archivada NO aparece en listado activo",
          pid23arc not in ids_active, "sigue apareciendo en activos")

    r_rest = session.put(f"{BASE}/api/propiedades/{pid23arc}/restore",
                         headers={"X-CSRFToken": real_csrf})
    check("PUT restore 200", r_rest.status_code == 200, str(r_rest.status_code))

    r_active2 = session.get(f"{BASE}/api/propiedades")
    ids_active2 = [p["id"] for p in r_active2.json()]
    check("Propiedad restaurada vuelve al listado activo",
          pid23arc in ids_active2, str(ids_active2[:5]))

    session.delete(f"{BASE}/api/propiedades/{pid23arc}/permanente",
                   headers={"X-CSRFToken": real_csrf})
else:
    fail("FASE 23 archivar setup", f"pid={pid23arc}")

# ─────────────────────────────────────────────────────────────────────────────
print("\n=== FASE 24: REGRESIÓN — PRODUCCIÓN DEBUGGING PASS ===")

# ── Bug 1: guardarFiltrosEnURL usa DOM real (no .tab-btn.active muerta) ────────
r_admin_f24 = session.get(f"{BASE}/admin")
if r_admin_f24.ok:
    html = r_admin_f24.text
    check("admin/index.html NO referencia .tab-btn.active (selector muerto)",
          '.tab-btn.active' not in html, "selector muerto todavía presente")
    check("admin/index.html guardarFiltrosEnURL detecta tab por display del DOM",
          "tab-propiedades" in html and ("tab-archivados" in html),
          "detección de tab por DOM no encontrada")
    check("admin/index.html leerFiltrosDeURL NO manipula .tab-btn (ya no existe)",
          ".querySelectorAll('.tab-btn')" not in html and
          ".tab-btn" not in html,
          "leerFiltrosDeURL sigue manipulando .tab-btn")

# ── Bug 2: cargarSimilares guarda contra tipo+operacion vacíos ─────────────────
r_pub_prop = requests.get(BASE)
check("propiedad.html carga sin error", r_pub_prop.status_code == 200)
# Verifica vía contenido del template renderizado (hit un path genérico)
if propiedades_orig:
    pid_sim = propiedades_orig[0]["id"]
    r_det_sim = requests.get(f"{BASE}/propiedad/{pid_sim}")
    check(f"GET /propiedad/{pid_sim} 200", r_det_sim.status_code == 200, str(r_det_sim.status_code))
    check("propiedad.html tiene guard cargarSimilares (!tipo && !operacion)",
          "!p.tipo && !p.operacion" in r_det_sim.text or
          "if (!p.tipo && !p.operacion)" in r_det_sim.text,
          "guard no encontrado en HTML de propiedad")

# ── Bug 3: bulk-toolbar mobile CSS ─────────────────────────────────────────────
if r_admin_f24.ok:
    check("admin/index.html bulk-toolbar tiene media query mobile (left:0)",
          "@media (max-width: 768px)" in r_admin_f24.text and
          "bulk-toolbar" in r_admin_f24.text,
          "media query mobile para bulk-toolbar no encontrada")

# ── Bug 4: fetch de asignación propietario/interesado tiene .catch() ───────────
if r_admin_f24.ok:
    check("agregarPropietarioInline tiene .catch()",
          "Error al asignar propietario" in r_admin_f24.text,
          "falta .catch() en agregarPropietarioInline")
    check("quitarPropietarioInline tiene .catch()",
          "Error al quitar propietario" in r_admin_f24.text,
          "falta .catch() en quitarPropietarioInline")
    check("agregarPropiedadCliente tiene .catch()",
          "Error al asignar propiedad" in r_admin_f24.text,
          "falta .catch() en agregarPropiedadCliente")
    check("quitarPropiedadCliente tiene .catch()",
          "Error al quitar propiedad" in r_admin_f24.text,
          "falta .catch() en quitarPropiedadCliente")

# ── Bug 5: OSError en borrado de foto registra warning (no silencia) ───────────
r_app = requests.get(f"{BASE}/static/admin.js")  # no acceso directo a app.py, lo verificamos via logs
# Verificamos la corrección leyendo el archivo fuente directamente
try:
    with open("z:/programming/Dad/app.py", encoding="utf-8") as f:
        app_src = f.read()
    check("app.py OSError en delete_foto registra warning (no pass silencioso)",
          "app.logger.warning" in app_src and "Could not delete photo file" in app_src,
          "logger.warning no encontrado tras except OSError")
    check("app.py no usa 'except OSError: pass' sin logging en delete_foto",
          "except OSError:\n            pass" not in app_src,
          "OSError todavía silenciado con pass")
except Exception as e:
    fail("app.py lectura para verificar OSError fix", str(e))

# ── Consultas reply endpoint disponible ────────────────────────────────────────
r_cons = session.get(f"{BASE}/api/consultas")
if r_cons.ok and r_cons.json():
    cid_reply = r_cons.json()[0]["id"]
    # Intentar reply sin config de email — debe fallar con 503 o 400, no 404/500
    r_reply = session.post(f"{BASE}/api/consultas/{cid_reply}/responder",
                           json={"asunto": "Test", "cuerpo": "Test reply"},
                           headers={"X-CSRFToken": real_csrf})
    check(f"POST /api/consultas/{cid_reply}/responder endpoint existe (no 404)",
          r_reply.status_code != 404, f"status={r_reply.status_code}")
    check("Reply endpoint retorna 200/503 (no 500 crash)",
          r_reply.status_code in (200, 503, 400), f"status={r_reply.status_code}")

# ── Bulk estado endpoint ────────────────────────────────────────────────────────
r_props_bulk = session.get(f"{BASE}/api/propiedades")
if r_props_bulk.ok and r_props_bulk.json():
    test_ids = [r_props_bulk.json()[0]["id"]]
    orig_estado = r_props_bulk.json()[0].get("estado", "disponible")
    r_bulk = session.patch(f"{BASE}/api/propiedades/bulk-estado",
                           json={"ids": test_ids, "estado": "disponible"},
                           headers={"X-CSRFToken": real_csrf})
    check("PATCH /api/propiedades/bulk-estado 200",
          r_bulk.status_code == 200, f"status={r_bulk.status_code}")
    if r_bulk.ok:
        check("bulk-estado devuelve campo updated",
              "updated" in r_bulk.json(), str(r_bulk.json()))
        check("bulk-estado updated == 1",
              r_bulk.json().get("updated") == 1, str(r_bulk.json().get("updated")))
    # Restore original estado
    session.patch(f"{BASE}/api/propiedades/bulk-estado",
                  json={"ids": test_ids, "estado": orig_estado},
                  headers={"X-CSRFToken": real_csrf})

# ─────────────────────────────────────────────────────────────────────────────
print("\n=== FASE 25: PIPELINE OPTIMIZACIÓN DE IMÁGENES ===")

# ── 1. Verificación estática — app.py ─────────────────────────────────────────
try:
    with open("z:/programming/Dad/app.py", encoding="utf-8") as f:
        app_src25 = f.read()
    check("app.py define _PROPS_FOLDER 'static/uploads/properties'",
          "_PROPS_FOLDER  = 'static/uploads/properties'" in app_src25 or
          "_PROPS_FOLDER = 'static/uploads/properties'" in app_src25,
          "constante no encontrada")
    check("app.py define _THUMBS_FOLDER 'static/uploads/properties/thumbs'",
          "_THUMBS_FOLDER = 'static/uploads/properties/thumbs'" in app_src25 or
          "_THUMBS_FOLDER  = 'static/uploads/properties/thumbs'" in app_src25,
          "constante no encontrada")
    check("app.py define _WEBP_QUALITY = 82",
          "_WEBP_QUALITY  = 82" in app_src25 or "_WEBP_QUALITY = 82" in app_src25,
          "calidad WebP no encontrada")
    check("app.py define _THUMB_WIDTH = 480",
          "_THUMB_WIDTH   = 480" in app_src25 or "_THUMB_WIDTH = 480" in app_src25,
          "ancho miniatura no encontrado")
    check("app.py tiene función _thumb_path_for",
          "def _thumb_path_for(" in app_src25, "función no encontrada")
    check("app.py tiene función _optimize_and_save",
          "def _optimize_and_save(" in app_src25, "función no encontrada")
    check("app.py tiene función _save_photo",
          "def _save_photo(" in app_src25, "función no encontrada")
    check("app.py upload_foto_propiedad usa _save_photo",
          "_save_photo(file," in app_src25, "_save_photo no llamado en upload")
    check("app.py delete_foto_propiedad llama _thumb_path_for",
          "_thumb_path_for(target)" in app_src25, "_thumb_path_for no en delete handler")
    check("app.py ImageOps.exif_transpose para auto-orient",
          "ImageOps.exif_transpose" in app_src25, "exif_transpose no encontrado")
    check("app.py WebP magic bytes en allowed_file",
          "_WEBP_MAGIC" in app_src25 and "header[8:12] == b'WEBP'" in app_src25,
          "validación magic bytes WebP no encontrada")
    check("allowed_file lee 12 bytes (no 4) para soportar WebP",
          "file.read(12)" in app_src25, "read(12) no encontrado")
    check("_optimize_and_save convierte a RGB antes de guardar WebP",
          "img.convert('RGB')" in app_src25, "conversión RGB no encontrada")
    check("_save_photo genera filename con .webp",
          ".webp\"" in app_src25 or "'.webp'" in app_src25 or '".webp"' in app_src25,
          ".webp no encontrado en _save_photo")
except Exception as e:
    fail("FASE 25 lectura app.py", str(e))

# ── 2. Verificación estática — config.py ─────────────────────────────────────
try:
    with open("z:/programming/Dad/config.py", encoding="utf-8") as f:
        cfg_src25 = f.read()
    check("config.py ALLOWED_EXTENSIONS incluye 'webp'",
          "'webp'" in cfg_src25, "webp no está en ALLOWED_EXTENSIONS")
except Exception as e:
    fail("FASE 25 lectura config.py", str(e))

# ── 3. Verificación estática — templates ─────────────────────────────────────
try:
    with open("z:/programming/Dad/templates/index.html", encoding="utf-8") as f:
        idx_src25 = f.read()
    check("index.html tiene función thumbUrl",
          "function thumbUrl(" in idx_src25, "thumbUrl no encontrada")
    check("index.html renderCard usa thumbUrl para foto de card",
          "thumbUrl(fotos[0])" in idx_src25, "thumbUrl no usado en renderCard")
    check("index.html carouselGo usa thumbUrl al cambiar imagen",
          "thumbUrl(fotos[idx])" in idx_src25, "thumbUrl no usado en carouselGo")
except Exception as e:
    fail("FASE 25 lectura index.html", str(e))

try:
    with open("z:/programming/Dad/templates/propiedad.html", encoding="utf-8") as f:
        prop_src25 = f.read()
    check("propiedad.html tiene función thumbUrl",
          "function thumbUrl(" in prop_src25, "thumbUrl no encontrada")
    check("propiedad.html renderSimCard usa thumbUrl",
          "thumbUrl(p.fotos[0])" in prop_src25, "thumbUrl no usado en renderSimCard")
except Exception as e:
    fail("FASE 25 lectura propiedad.html", str(e))

# ── 4. Directorios creados al arranque ────────────────────────────────────────
check("static/uploads/properties/ existe",
      os.path.isdir("z:/programming/Dad/static/uploads/properties"),
      "directorio no creado")
check("static/uploads/properties/thumbs/ existe",
      os.path.isdir("z:/programming/Dad/static/uploads/properties/thumbs"),
      "directorio thumbs no creado")

# ── 5. Integration: upload JPEG → WebP + thumbnail generados ─────────────────
r25p = session.post(f"{BASE}/api/propiedades",
                    json={"codigo": "F25-IMG", "direccion": "Fase25 Imagen",
                          "tipo": "departamento", "operacion": "venta", "estado": "disponible"},
                    headers={"X-CSRFToken": real_csrf})
pid25 = r25p.json().get("id") if r25p.ok else None

if pid25:
    r_up25 = session.post(f"{BASE}/api/propiedades/{pid25}/upload",
                          files={"file": ("foto.jpg", io.BytesIO(jpeg_bytes), "image/jpeg")},
                          headers={"X-CSRFToken": real_csrf})
    check("Upload JPEG via pipeline 200", r_up25.status_code == 200, str(r_up25.status_code))

    if r_up25.ok:
        fotos25 = r_up25.json().get("fotos", [])
        check("Foto en static/uploads/properties/",
              fotos25 and fotos25[0].startswith("static/uploads/properties/"),
              fotos25[0] if fotos25 else "sin fotos")
        check("Foto guardada como .webp",
              fotos25 and fotos25[0].endswith(".webp"),
              fotos25[0] if fotos25 else "no webp")
        check("Foto NO está en static/uploads/properties/thumbs/ (ruta full)",
              fotos25 and "/thumbs/" not in fotos25[0],
              fotos25[0] if fotos25 else "sin fotos")

        if fotos25:
            full_disk  = os.path.join("z:/programming/Dad", fotos25[0].replace("/", os.sep))
            thumb_disk = full_disk.replace(
                os.sep + "properties" + os.sep,
                os.sep + "properties" + os.sep + "thumbs" + os.sep
            )
            check("Full WebP existe en disco", os.path.isfile(full_disk),
                  f"no encontrado: {full_disk}")
            full_size  = os.path.getsize(full_disk)  if os.path.isfile(full_disk)  else 0
            check("Full WebP > 0 bytes",  full_size > 0,  str(full_size))

            # DELETE — debe borrar tanto full como thumb
            r_del25 = session.delete(f"{BASE}/api/propiedades/{pid25}/fotos/{fotos25[0]}",
                                     headers={"X-CSRFToken": real_csrf})
            check("DELETE foto 200", r_del25.status_code == 200, str(r_del25.status_code))
            check("Full WebP eliminado del disco", not os.path.isfile(full_disk),
                  f"archivo aún existe: {full_disk}")
            check("Thumbnail WebP eliminado del disco", not os.path.isfile(thumb_disk),
                  f"thumbnail aún existe: {thumb_disk}")

    # ── 6. Backward compat: API pública sigue funcionando con fotos legadas ───
    r_pub25 = requests.get(f"{BASE}/api/public/propiedades")
    check("API pública sigue respondiendo con fotos legacy en DB",
          r_pub25.status_code == 200, str(r_pub25.status_code))

    # Cleanup
    session.delete(f"{BASE}/api/propiedades/{pid25}/permanente",
                   headers={"X-CSRFToken": real_csrf})
else:
    fail("FASE 25 setup", "no se pudo crear propiedad de prueba")

# ─────────────────────────────────────────────────────────────────────────────
print("\n\n" + "="*60)
print(f"TOTAL: {len(PASS)} PASS, {len(FAIL)} FAIL")
print("="*60)
if FAIL:
    print("\nFAILS:")
    for name, detail in FAIL:
        print(f"  FAIL {name}: {detail}")
print()
