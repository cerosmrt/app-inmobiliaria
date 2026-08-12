# VISION.md — Moret Inmobiliaria como plataforma inteligente

> Documento estratégico. No es código: es la dirección de producto. El backlog accionable vive en `ROADMAP.md`; acá está el "por qué" y las apuestas de mayor impacto.
> Rol con el que está escrito: Head of Product + UX + AI Strategist + Growth + Data. Opinionado a propósito.

---

## 0. Tesis (lo más importante — leer esto aunque no leas el resto)

**No compitas con Zillow/ZonaProp copiando features. Ganá donde ellos no pueden entrar: Gualeguay.**

Tres realidades definen la estrategia:

1. **El mercado es chico y de baja frecuencia.** Pocas propiedades, pocas transacciones/mes. Los modelos de ML hambrientos de datos (AVM estilo Zillow, predicción de precios entrenada) **no tienen volumen** para funcionar bien todavía. Copiar esas features sería teatro.
2. **Tenés un activo único que ningún portal nacional tiene: el catastro de ATER (13.761 parcelas + dueños) + datos rurales de campos.** Eso no es un mapa lindo: es una **máquina de prospección de vendedores**. Sabés quién tiene qué tierra antes de que decida vender.
3. **El canal es WhatsApp, no el email ni el portal.** Toda la conversión pasa (o debería pasar) por ahí, y ya lo tenés integrado a medias.

**Dónde está el 10x, en orden:**
- **A. Prospección de vendedores por catastro** (captar listings antes que la competencia). Esto genera *inventario*, que es el cuello de botella real de una inmobiliaria chica.
- **B. Journey del comprador nativo en WhatsApp** + scoring de intención (convertir mejor los pocos leads que entran).
- **C. Inteligencia de listing con IA** (descripciones, calidad de fotos, deduplicación) para que el inventario flaco se vea de primera.
- **D. Feed personalizado + alertas** (retención: que el comprador vuelva sin que le insistas).
- **E. Productividad del agente + analytics** (que tu viejo trabaje menos y decida con datos).

**Cómo se construyen las "features de IA" acá (realidad técnica):** no entrenás modelos. **Llamás a la API de Claude** para lo generativo/clasificatorio (descripciones, scoring cualitativo, chat, matching semántico) y usás **heurísticas + tus propios datos históricos** para lo numérico. Barato, rápido, sin infra de ML. La restricción es el plan chico de Railway (CPU/RAM acotadas, sin GPU) → todo lo pesado va como job/cron o llamada a API externa.

**Lo que NO vamos a construir (y por qué):** ratings de escuelas, índices de crimen, walkability, AVM entrenado, análisis de commute → **no hay datos confiables para Gualeguay** y sería humo. Si algún día hay volumen y datos, se reevalúa.

---

## 1. Diagnóstico del producto actual

### Fricción de UX
- **Ficha admin sobrecargada:** datos + geo + fotos + personas en una sola columna larga; tu viejo no ve "la propiedad", ve un formulario. (Ya está en el ROADMAP el rediseño con "vista cliente" arriba.)
- **Sitio público sin identidad de búsqueda:** el filtrado es 100% client-side sobre el array completo → no escala y no hay URLs compartibles por filtro (no podés mandar "casas en venta bajo USD 80k" por WhatsApp).
- **Cero captura de intención del visitante:** un comprador entra, mira 5 propiedades y se va sin dejar rastro. No hay "guardar", no hay cuenta, no hay forma de volver a contactarlo.
- **Contacto = fricción:** el lead tiene que escribir. No hay "avisame si baja de precio", no hay "quiero visitarla el sábado".

### Features faltantes (que el usuario espera de un producto 2025)
- Guardar propiedades / favoritos. Búsquedas guardadas con alerta. Comparador. Historial de precio. Tour por WhatsApp agendable. Compartir listing con preview lindo.

### Workflows pobres
- **Captación desconectada del catastro:** tenés los dueños en el mapa pero convertir "parcela → lead → contacto" es manual y sin priorización. Es tu mejor activo y está subutilizado.
- **Sin seguimiento estructurado del comprador:** los interesados se matchean con propiedades, pero no hay "próxima acción", ni recordatorios, ni scoring.
- **Fotos:** buen pipeline técnico, pero nadie te dice si una foto es mala/oscura/duplicada antes de publicar.

### Conversión / funnel
- **No hay funnel medido.** No sabés visitante→lead, ni cuántas fichas se ven por sesión, ni qué propiedad genera más consultas. Estás optimizando a ciegas.
- **Sin retargeting propio:** no hay newsletter, ni "volvé a ver lo que miraste", ni push.

### Analytics / métricas de negocio
- **Prácticamente inexistentes.** Hay stats básicos de conteo. No hay eventos de comportamiento, ni tiempo en ficha, ni tasa de contacto por listing, ni performance por agente.

### Oportunidades de IA desperdiciadas
- Descripciones escritas a mano (lentas, inconsistentes). Matching interesado↔propiedad por reglas rígidas en vez de semántico. Cero asistente para el comprador (que responda 24/7 en el sitio/WhatsApp). Cero priorización de leads.

---

## 2. KPIs que hay que instrumentar (hoy: casi ninguno)

Sin esto, todo lo demás es opinión. **Primer trabajo de datos: un `event(tipo, entidad, meta, session_id, ts)` que registre comportamiento.** Con esa sola tabla salen casi todos los KPIs.

**Funnel de conversión**
- Visitante → Lead (consulta/guardado/contacto)
- Lead → Visita agendada
- Visita → Oferta
- Oferta → Venta

**Engagement / listing**
- Vistas por ficha, tiempo en ficha, fotos vistas por sesión
- Tasa de contacto por listing (consultas / vistas) — *identifica listings que atraen pero no convierten*
- Propiedades guardadas, búsquedas guardadas
- Bounce rate, páginas por sesión, usuarios que vuelven

**Operación / agente**
- Tiempo de respuesta del agente (primer contacto tras lead)
- Días en mercado por propiedad (time-to-sell)
- Leads por fuente, tasa de éxito de búsqueda ("¿encontró algo?")

**Negocio**
- Revenue por propiedad / comisión estimada en pipeline
- Costo de adquisición de listing (para prospección catastral)
- Valor de vida del cliente (recurrencia de inversores/repeat sellers)

> Regla: **cada feature nueva de abajo debe mover al menos uno de estos KPIs, o no se construye.**

---

## 3. Catálogo de features de inteligencia

Framework por feature: **Problema · Valor usuario · Valor negocio · Complejidad · Esfuerzo · Impacto · Prioridad.**
Complejidad y esfuerzo asumen el stack actual (Flask + SQLite/Postgres + JS vanilla + API de Claude para lo generativo).

### 🎯 A. Prospección de vendedores por catastro (tu moat #1)

**A1. Radar de captación catastral (parcela → lead priorizado)**
- **Problema:** tenés 13.761 parcelas con dueños y convertirlas en listings es 100% manual, sin priorizar.
- **Valor usuario (agente):** una lista ordenada de "a quién tocarle la puerta esta semana" en vez de mirar un mapa.
- **Valor negocio:** genera **inventario**, el cuello de botella real. Más listings = más ventas.
- **Complejidad:** Media. **Esfuerzo:** ~3-5 días. Ya existe captación + parcelas; falta el scoring y la cola.
- **Impacto:** Muy alto. **Prioridad: ALTA.**

**A2. Seller Readiness Score (probabilidad de que un dueño venda)**
- **Problema:** no todos los dueños son prospectos iguales.
- **Valor usuario:** enfocar esfuerzo en los que tienen señales de venta (herencia/sucesión, parcela sin uso, dueño ausentista, múltiples parcelas, deuda).
- **Valor negocio:** más conversión de prospección con el mismo esfuerzo.
- **Complejidad:** Media (heurística sobre datos catastrales + señales; no ML). **Esfuerzo:** ~3 días.
- **Impacto:** Alto. **Prioridad: ALTA.**

**A3. Detección de oportunidades de tierra / subdivisión (campos)**
- **Problema:** el valor rural está en subdividir/uso, y hoy se evalúa a ojo.
- **Valor usuario:** el sistema marca parcelas grandes cerca de zona urbana / con potencial de loteo.
- **Valor negocio:** operaciones rurales de alto ticket = comisiones grandes.
- **Complejidad:** Media-alta (geo + reglas de zonificación). **Esfuerzo:** ~1 semana.
- **Impacto:** Alto (pocas operaciones, mucha plata). **Prioridad: MEDIA.**

### 💬 B. Journey del comprador (WhatsApp-native)

**B1. Buyer Intent Score (scoring de intención del lead)**
- **Problema:** todos los leads entran iguales a la bandeja; tu viejo no sabe a quién llamar primero.
- **Valor usuario:** leads ordenados por temperatura (vistas repetidas, guardados, rango de precio realista, velocidad de respuesta).
- **Valor negocio:** más ventas por lead, mejor tiempo de respuesta donde importa.
- **Complejidad:** Media (necesita eventos de comportamiento primero). **Esfuerzo:** ~3-4 días (post-analytics).
- **Impacto:** Muy alto. **Prioridad: ALTA.**

**B2. Guardar propiedades + búsquedas guardadas con alerta (identidad ligera)**
- **Problema:** el visitante no deja rastro y no vuelve.
- **Valor usuario:** "guardá esto", "avisame si baja de precio o entra algo parecido" — sin registro pesado (magic link / número de WhatsApp).
- **Valor negocio:** convierte anónimos en leads con contacto; canal de retención propio.
- **Complejidad:** Media. **Esfuerzo:** ~4-5 días. **Impacto:** Alto. **Prioridad: ALTA.**

**B3. Asistente IA para compradores (chat 24/7 en sitio + WhatsApp)**
- **Problema:** consultas fuera de horario se pierden; el comprador quiere respuesta ya.
- **Valor usuario:** pregunta "¿tenés casas con patio bajo USD 90k?" y el bot filtra el inventario y responde con fichas.
- **Valor negocio:** captura leads 24/7, califica antes de que intervenga el humano.
- **Complejidad:** Media (API de Claude + tool-use sobre tu propia API de propiedades). **Esfuerzo:** ~1 semana (web), +integración WhatsApp (Business API) aparte.
- **Impacto:** Muy alto. **Prioridad: ALTA (web primero).**

**B4. Agendar visita en 1 tap**
- **Problema:** coordinar visita es ida y vuelta por WhatsApp.
- **Valor usuario:** elige día/horario propuesto desde la ficha.
- **Valor negocio:** más visitas agendadas = más ofertas; mide Visita→Oferta.
- **Complejidad:** Baja-media. **Esfuerzo:** ~3 días. **Impacto:** Medio-alto. **Prioridad: MEDIA.**

### 🏠 C. Inteligencia de listing

**C1. Descripciones generadas por IA**
- **Problema:** escribir descripciones es lento e inconsistente; hay fichas sin texto.
- **Valor usuario (agente):** de los datos + fotos → una descripción vendedora en 3 segundos, editable.
- **Valor negocio:** más listings completos = más engagement y mejor SEO.
- **Complejidad:** Baja (API de Claude con los campos de la propiedad). **Esfuerzo:** ~1-2 días.
- **Impacto:** Alto (quick win). **Prioridad: ALTA.**

**C2. Scoring de calidad de fotos + orden automático**
- **Problema:** fotos oscuras/torcidas/irrelevantes matan la conversión; nadie las revisa.
- **Valor usuario:** el sistema puntúa cada foto y sugiere cuál es la portada.
- **Valor negocio:** mejor foto de portada = más clicks = más consultas.
- **Complejidad:** Media (visión: API multimodal o heurística de brillo/nitidez). **Esfuerzo:** ~3 días.
- **Impacto:** Medio-alto. **Prioridad: MEDIA.**

**C3. Detección de listings duplicados**
- **Problema:** la misma propiedad cargada dos veces ensucia inventario y métricas.
- **Valor usuario:** aviso "esto se parece a #123".
- **Valor negocio:** inventario limpio, confianza.
- **Complejidad:** Baja-media (similitud por dirección/geo/precio/fotos). **Esfuerzo:** ~2 días.
- **Impacto:** Medio. **Prioridad: MEDIA.**

**C4. Estimador de valor por comparables (AVM liviano, honesto)**
- **Problema:** poner precio es a ojo; sobreprecio = no vende, subprecio = plata perdida.
- **Valor usuario:** rango sugerido con los comparables de **tu propia base** + parcela catastral (superficie/zona), con nivel de confianza explícito.
- **Valor negocio:** precios mejores = menos días en mercado.
- **Complejidad:** Media (heurística de comparables, NO ML entrenado). **Esfuerzo:** ~4-5 días.
- **Impacto:** Alto — **pero depende de volumen de datos.** **Prioridad: MEDIA** (crece con el tiempo).

### 🧠 D. Retención y personalización

**D1. Feed personalizado / "Para vos"**
- **Problema:** todos ven el mismo listado ordenado igual.
- **Valor usuario:** home ordenado por lo que miró/guardó (behavior-based).
- **Valor negocio:** más engagement, más retorno.
- **Complejidad:** Media (necesita eventos). **Esfuerzo:** ~4 días. **Impacto:** Medio-alto. **Prioridad: MEDIA.**

**D2. Alertas de price-drop y "nuevo parecido a lo que buscás"**
- **Problema:** el comprador se enfría entre visitas al sitio.
- **Valor usuario:** notificación cuando algo relevante cambia.
- **Valor negocio:** reactiva leads sin costo de pauta.
- **Complejidad:** Baja-media (cron + búsquedas guardadas B2). **Esfuerzo:** ~2-3 días sobre B2. **Impacto:** Alto. **Prioridad: ALTA (junto con B2).**

**D3. Comparador inteligente de propiedades**
- **Problema:** comparar es abrir 5 pestañas.
- **Valor usuario:** tabla lado a lado + "por qué esta te conviene" (resumen IA).
- **Valor negocio:** acelera la decisión.
- **Complejidad:** Baja-media. **Esfuerzo:** ~3 días. **Impacto:** Medio. **Prioridad: BAJA-MEDIA.**

### 🤖 E. Productividad del agente y automatización

**E1. Copiloto del agente (bandeja unificada + next-best-action)**
- **Problema:** consultas, matches, seguimientos y captación están en pantallas separadas.
- **Valor usuario:** "hoy: llamá a X (lead caliente), respondé a Y, seguí la parcela Z".
- **Valor negocio:** menos leads que se enfrían por olvido.
- **Complejidad:** Media (agrega eventos + scoring de B1/A1). **Esfuerzo:** ~1 semana. **Impacto:** Alto. **Prioridad: MEDIA.**

**E2. Auto-follow-up por WhatsApp (plantillas + recordatorios)**
- **Problema:** el seguimiento manual se cae.
- **Valor usuario:** el sistema sugiere/recuerda el próximo mensaje, con plantilla pre-armada.
- **Valor negocio:** mejora tiempo de respuesta y tasa de cierre.
- **Complejidad:** Media (recordatorios sí; envío automático requiere WhatsApp Business API). **Esfuerzo:** ~3 días (asistido) / +infra (automático). **Impacto:** Alto. **Prioridad: MEDIA.**

**E3. Dashboard de negocio (el funnel + días en mercado + fuentes de lead)**
- **Problema:** cero visibilidad de qué funciona.
- **Valor usuario:** tu viejo ve el pulso del negocio en una pantalla.
- **Valor negocio:** decisiones con datos (qué precio, qué zona, qué canal).
- **Complejidad:** Media (sobre la tabla de eventos). **Esfuerzo:** ~4-5 días. **Impacto:** Alto. **Prioridad: ALTA (después de instrumentar eventos).**

**E4. Ficha PDF / flyer de propiedad de 1 click (para mandar por WhatsApp)**
- **Problema:** armar el "folleto" para mandar a un cliente es manual.
- **Valor usuario:** botón → PDF lindo con fotos, precio, datos, contacto.
- **Valor negocio:** más profesional, más compartible; el print CSS ya existe.
- **Complejidad:** Baja. **Esfuerzo:** ~1-2 días. **Impacto:** Medio (quick win real). **Prioridad: MEDIA.**

### 📊 F. Fundaciones (habilitadores — sin esto lo de arriba no vive)

**F1. Instrumentación de eventos de comportamiento** — la tabla `event`. Habilita B1, D1, D2, E1, E3 y todos los KPIs. **Esfuerzo:** ~2-3 días. **Prioridad: ALTA (es el cimiento).**
**F2. Búsqueda server-side + URLs por filtro + saved search** — escala el listado y hace compartible la búsqueda. **Esfuerzo:** ~3-4 días. **Prioridad: ALTA.**
**F3. Identidad ligera del visitante** (magic link / WhatsApp OTP) — habilita guardados, alertas y feed. **Esfuerzo:** ~3 días. **Prioridad: ALTA.**

---

## 4. Top 20 mejoras rankeadas por impacto de negocio

Orden = retorno esperado sobre esfuerzo, para *este* negocio (inmobiliaria chica, mercado Gualeguay, canal WhatsApp). Los primeros ~6 son los que yo empezaría.

| # | Mejora | Palanca | Prioridad | Esfuerzo |
|---|--------|---------|-----------|----------|
| 1 | **F1 · Instrumentar eventos + KPIs del funnel** | Analytics (habilitador de todo) | ALTA | S-M |
| 2 | **A1 · Radar de captación catastral (parcela→lead priorizado)** | Inventario (moat) | ALTA | M |
| 3 | **C1 · Descripciones con IA** | Calidad de listing (quick win) | ALTA | S |
| 4 | **B1 · Buyer Intent Score** | Conversión de leads | ALTA | M |
| 5 | **F2 · Búsqueda server-side + URLs compartibles + saved search** | UX/escala/compartir | ALTA | M |
| 6 | **B2 + D2 · Guardados + alertas price-drop / "nuevo parecido"** | Retención | ALTA | M |
| 7 | **B3 · Asistente IA para compradores (web)** | Conversión 24/7 | ALTA | M-L |
| 8 | **A2 · Seller Readiness Score** | Inventario (calidad de prospección) | ALTA | M |
| 9 | **E3 · Dashboard de negocio (funnel + días en mercado)** | Decisiones con datos | ALTA | M |
| 10 | **F3 · Identidad ligera del visitante** | Habilitador de retención | ALTA | S-M |
| 11 | **C4 · Estimador de valor por comparables (honesto)** | Pricing / días en mercado | MEDIA | M |
| 12 | **E1 · Copiloto del agente (next-best-action)** | Productividad | MEDIA | L |
| 13 | **C2 · Scoring de calidad de fotos + portada** | Conversión de ficha | MEDIA | M |
| 14 | **D1 · Feed personalizado "Para vos"** | Engagement | MEDIA | M |
| 15 | **E4 · Ficha PDF/flyer de 1 click** | Compartir por WhatsApp (quick win) | MEDIA | S |
| 16 | **B4 · Agendar visita en 1 tap** | Visita→Oferta | MEDIA | S-M |
| 17 | **A3 · Oportunidades de tierra/subdivisión (campos)** | Operaciones de alto ticket | MEDIA | L |
| 18 | **E2 · Auto-follow-up por WhatsApp (asistido)** | Tiempo de respuesta | MEDIA | M |
| 19 | **C3 · Detección de duplicados** | Higiene de inventario | MEDIA | S |
| 20 | **D3 · Comparador inteligente** | Decisión del comprador | BAJA-MEDIA | S-M |

**Esfuerzo:** S ≈ 1-2 días · M ≈ 3-5 días · L ≈ ~1 semana+.

### Secuencia recomendada (no todo a la vez — regla del proyecto)
1. **Cimientos** (#1, #5, #10): eventos, búsqueda server-side, identidad ligera → sin esto la mitad de lo demás no existe.
2. **Quick wins de valor inmediato** (#3, #15): descripciones IA + ficha PDF. Días, no semanas, y tu viejo lo siente ya.
3. **Moat de inventario** (#2, #8): captación catastral inteligente.
4. **Conversión** (#4, #6, #7): intent score, guardados/alertas, asistente IA.
5. **Decisión con datos** (#9): dashboard.

---

## 5. Restricciones y riesgos a tener presentes
- **Datos:** los AVM/scoring numéricos mejoran con volumen; al principio son heurísticas honestas con "nivel de confianza" visible. Nada de precisión falsa.
- **Infra (Railway, plan Hobby ~USD5/mes):** CPU/RAM acotadas y sin GPU → lo pesado va como cron/job o llamada a API externa (Claude). Evaluar si algún feature obliga a subir de plan.
- **IA = API de Claude,** no modelos propios: costo por request bajo y predecible, pero hay que cachear y limitar para no disparar gasto (ej. no regenerar descripciones en cada view).
- **Privacidad/legal:** los datos de dueños catastrales y el scoring de vendedores son sensibles — uso interno, con cuidado en cómo se contacta (no spam). Definir política antes de escalar A1/A2.
- **WhatsApp:** el salto de "links wa.me" a **automatización real** (bot que envía) requiere WhatsApp Business API (costo + aprobación). El chat web (B3) no depende de eso y se hace primero.
