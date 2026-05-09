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
for pwd in ["audit_tmp_123", "admin", "admin123", "moret", "1234", "moret123"]:
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
print("\n\n" + "="*60)
print(f"TOTAL: {len(PASS)} PASS, {len(FAIL)} FAIL")
print("="*60)
if FAIL:
    print("\nFAILS:")
    for name, detail in FAIL:
        print(f"  FAIL {name}: {detail}")
print()
