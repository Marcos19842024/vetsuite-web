# Sesión de trabajo — 2026-11-07 (VetSuite Web v0.9)

## Resumen

Sesión enfocada en **Ingresos** (filtro de fechas de Gmail, visor de
PDF/XML, re-clasificación de sucursales, regex de serie) y en **UI**
(iconos Tabler, color del activo en sidebar, tabla full-height).

Se completó:
- Fix del filtro de fechas de Gmail (header `Date:` en Python).
- Fix del regex de serie para `PRADOS` sin `/` y con espacio.
- Endpoint `POST /ingresos/reclasificar-sucursales`.
- Endpoints `GET /ingresos/ver-pdf/{id}` y `GET /ingresos/ver-xml/{id}`.
- Doble clic en fila de Ingresos: PDF; Ctrl/Cmd+doble clic: XML.
- Tabla de Ingresos full-height.
- Iconos Tabler en sidebar y botones (reemplazo de emojis).
- Color del módulo activo en el sidebar.
- Fix del activo de Permisos IP (URL `/admin` vs nombre interno `admin_ips`).

## Qué se hizo

### 1. Filtro de fechas de Gmail

**Problema**: el filtro de rango de fechas descargaba todo. El `search` de
IMAP se hacía con `SINCE`/`BEFORE`, pero Gmail los ignora o los aplica
sobre `INTERNALDATE` (fecha de entrega), no sobre el header `Date:`.

**Fix**:
- El `search` de IMAP solo lleva `UNSEEN`, `FROM` y `ALL`, pasados como
  argumentos sueltos (`mail.search(None, *criterios)`).
- El filtro de fechas se hace en Python:
  `parsedate_to_datetime(msg.get("Date")).date()`.
- Se aplica **antes** del chequeo de caché y del filtro de remitente.
- `info["omitidos_fecha"]` cuenta los descartados.
- El log del job muestra `Fuera de rango (fecha < >). Se omite. Asunto: ...`.

### 2. Regex de serie tolerante

**Problema**: asuntos como `prados268-267` o `PRADOS 270-269` (sin `/`)
no se reconocían y la factura caía en `_sin_sucursal`.

**Fix**: regex nuevo en `correo_facturas.py`:

    r"\b(S1|PRADOS?)\b[\/\s\-]*(\d+)"

Acepta `S1`, `Prado`, `Prados` con o sin `/`, espacio o guion. Normaliza
`PRADO` → `PRADOS` y quita ceros a la izquierda. Si no encuentra serie
conocida, cae a un regex genérico `([A-Za-z0-9]+)\s*-\s*(\d+)`.

### 3. Re-clasificación de sucursales

**Problema**: facturas ya guardadas como `_sin_sucursal` no se podían
corregir en masa.

**Fix**: endpoint `POST /ingresos/reclasificar-sucursales`:
- Recorre facturas con `sucursal` vacía o `_sin_sucursal`.
- Para cada una: busca su XML, lee `Serie` con `leer_xml_factura()`,
  aplica `serie_a_sucursal(serie)`.
- `S1` → Baalak, `PRADO`/`PRADOS` → Prado. Otras series no se tocan.
- Actualiza la BD y mueve los archivos a la carpeta correcta.
- Botón en el menú ⋯ Más de Ingresos.

### 4. Visor PDF/XML

**Nuevo**:
- `GET /ingresos/ver-pdf/{id}` → PDF `inline`.
- `GET /ingresos/ver-xml/{id}` → XML `inline`.
- Helper `_buscar_archivo(row, extension)`:
  1. Busca por folio en la sucursal de la fila.
  2. Fallback por UUID.
  3. Fallback en cualquier sucursal.
- `404` si el archivo no está en disco.
- Headers: `Content-Disposition: inline`, `Cache-Control: no-store`.

### 5. Doble clic en fila

- El `<tr>` lleva `data-id="{{ r.id }}"` y `style="cursor: pointer;"`.
- `dblclick` normal → `/ingresos/ver-pdf/{id}` en pestaña nueva.
- `Ctrl/Cmd + dblclick` → `/ingresos/ver-xml/{id}`.

### 6. Tabla full-height

- En `ingresos.html`, el card de la tabla lleva `class="card tabla-full"`.
- En `style.css`: `.page-wrapper > .page-body`, `.page-body > .container-xl`,
  `.card.tabla-full` y `.card.tabla-full .tabla-scroll` con flex.
- Solo aplica a Ingresos. Otras páginas conservan su `.tabla-scroll`.
- Nota: en algunas pantallas aún se sale un poco; se dejó así por ahora.

### 7. Iconos Tabler

- Se cargó el webfont en `base.html`:

      <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@latest/dist/tabler-icons.min.css">

- Sidebar: `ti-inbox`, `ti-send`, `ti-chart-histogram`, `ti-tools`,
  `ti-calendar-event`, `ti-shield-lock`, `ti-paw`.
- Botones: `ti-mail` o `ti-download` (Gmail), `ti-eye` o `ti-list`
  (Ver registros), `ti-file-excel` (Excel), `ti-brand-whatsapp-filled`
  (Enviar), `ti-x` (Desmarcar), `ti-trash` o `ti-refresh` (Reset).

### 8. Color del módulo activo en sidebar

En `style.css`:

    .navbar-vertical .nav-item.active > .nav-link {
        background-color: #206bc4;
        color: #ffffff;
    }
    .navbar-vertical .nav-item.active > .nav-link .nav-link-icon,
    .navbar-vertical .nav-item.active > .nav-link .nav-link-title {
        color: #ffffff;
    }

### 9. Item activo de Permisos IP

**Problema**: el `<li>` nunca se marcaba como activo. La condición en
`base.html` era `request.url.path.startswith('/admin_ips')` (con guion
bajo), pero la URL real es `/admin/ips` (con slash). El nombre interno
del módulo (`admin_ips`) es independiente de la URL pública.

**Fix**: en `base.html`, cambiar el `startswith` a `/admin` (o
`/admin/ips`):

    {% if request.url.path.startswith('/admin') %}active{% endif %}

## Bugs resueltos en esta sesión

- **Filtro de fechas de Gmail descargaba todo**: `SINCE`/`BEFORE` de IMAP
  no funcionan en Gmail (ignoran o aplican sobre `INTERNALDATE`). Fix:
  filtrar en Python por header `Date:`.
- **`document.querySelector('input[name="desde"]')` agarraba el input
  del filtro de la tabla, no el del modal**: había dos inputs con el
  mismo `name` en la página. Fix: usar `modalDescarga.querySelector(...)`.
- **Facturas `prados268-267` caían en `_sin_sucursal`**: el regex viejo
  no reconocía `Prados` sin `/`. Fix: regex tolerante
  `\b(S1|PRADOS?)\b[\/\s\-]*(\d+)`.
- **Item activo de Permisos IP no se marcaba**: comparaba contra
  `/admin_ips` (nombre interno) en vez de `/admin/ips` (URL). Fix:
  `startswith('/admin')`.
- **`304 Not Modified` en `style.css`**: no es un error, es caché del
  navegador. Fix: forzar recarga con Ctrl+Shift+R (Cmd+Shift+R en Mac).
- **Tabla de Ingresos dejaba espacio blanco abajo en pantalla grande**:
  el `.tabla-scroll` tenía `max-height: calc(100vh - 380px)` fijo. Fix:
  `.card.tabla-full` con flex y `max-height: none` para el scroll interno.

## Estado actual

### Funcional
- ✅ Ingresos con filtro de fechas de Gmail correcto.
- ✅ Visor PDF/XML (doble clic / Ctrl+doble clic).
- ✅ Re-clasificación de sucursales en masa.
- ✅ Regex de serie tolerante.
- ✅ Iconos Tabler en sidebar y botones.
- ✅ Color del módulo activo en sidebar.
- ✅ Tabla de Ingresos full-height.
- ✅ Todos los módulos anteriores siguen funcionando (Egresos,
  Recordatorios, Servicios Externos, Corte Semanal, Catálogo QVET).

### Pendiente (Ingresos)
- Optimización del filtro de fechas si el volumen de correos crece
  (pre-filtro IMAP grueso o caché por headers).
- Tests automáticos del filtro y del regex.

### Pendiente (global, arrastrado)
- Limpiar `print()` de debug en `sat/descarga.py` (líneas 142-146).
- Documentar instalación en Windows 11.
- Revisar `iicio.txt` y borrarlo.
- Tests automáticos (Recordatorios, Ingresos, Egresos, Corte, Servicios
  Externos).
- Arranque automático con el sistema.

## Cómo trabajar

- Arrancar: `uvicorn main:app --reload --host 127.0.0.1 --port 8000`
- Si uvicorn no recarga un cambio de CSS/JS, forzar recarga en el
  navegador con Ctrl+Shift+R (Cmd+Shift+R en Mac). Un `304 Not Modified`
  es normal (el archivo no cambió para el navegador).
- Probar Ingresos: `http://127.0.0.1:8000/ingresos`
- Probar Corte Semanal: `http://127.0.0.1:8000/corte_semanal`
- Probar Servicios Externos: `http://127.0.0.1:8000/servicios_externos`
- Probar Catálogo: `http://127.0.0.1:8000/ingresos/catalogo`

## Reglas nuevas (Ingresos / UI)

57. El filtro de fechas de Gmail se hace en Python sobre el header
    `Date:`, no con `SINCE`/`BEFORE` de IMAP.
58. El `search` de IMAP solo lleva `UNSEEN`, `FROM` y `ALL`, pasados como
    argumentos sueltos.
59. El filtro de fecha se aplica ANTES del caché y del filtro de
    remitente.
60. El regex de serie del asunto es
    `\b(S1|PRADOS?)\b[\/\s\-]*(\d+)`. Acepta con/sin `/`, espacio o
    guion. Normaliza `PRADO` → `PRADOS`.
61. `/reclasificar-sucursales` solo mueve a Baalak/Prado cuando el XML
    dice `S1` o `Prado(s)`.
62. El visor de archivos sirve `inline` con `Cache-Control: no-store` y
    fallback por UUID y por cualquier sucursal.
63. Doble clic en fila de Ingresos abre PDF; Ctrl/Cmd + doble clic abre
    XML.
64. El item activo del sidebar compara `request.url.path` (URL), NO el
    nombre interno del módulo.
65. Los iconos del sidebar y botones usan Tabler Icons
    (`<i class="ti ti-<nombre>"></i>`), no emojis.
66. La tabla de Ingresos usa `.card.tabla-full` + `.tabla-scroll` para
    ocupar el alto restante. Otras páginas conservan su `.tabla-scroll`
    original.
67. Si uvicorn no recarga CSS/JS, forzar recarga en el navegador. Un
    `304 Not Modified` es normal.

# Sesión de trabajo — 2026-11-05 (VetSuite Web v0.8)

## Resumen

Sesión enfocada en **Corte Semanal**: se agregó la funcionalidad de
**observaciones por celda** para egresos y para `por_cobrar/colaboradores`.
Desde el modal de captura de la celda, el usuario puede escribir un detalle
que se anexa automáticamente al campo `observaciones` del día con formato
`Gasto de $X: <texto>` o `Deuda de $X: <texto>`.

Se completó:
- Columna `cortes_diarios.obs_celdas_json` (JSON por día).
- Migración idempotente + siembra de `__manual__`.
- Regeneración automática de `observaciones` a partir de `__manual__` +
  claves de `obs_celdas_json`.
- Formato unificado: `: ` (dos puntos + espacio) en vez de `es de`.
- Textarea condicional en el modal de celda (solo egresos y colaboradores).
- El textarea del tab Observaciones se cambió a `<textarea>` para que se
  rendericen los `\n` reales.
- Auto-resize del textarea.

## Qué se hizo

### 1. Modelo de datos

Columna nueva en `cortes_diarios`:

    obs_celdas_json TEXT DEFAULT '{}'

Estructura:

    {
      "__manual__": "texto libre del tab Observaciones",
      "gasolina": "agua",
      "nomina_efectivo": "sueldos semana",
      "por_cobrar:colaboradores": "$100 de Andrea y $500 de Mimi"
    }

### 2. Migración en `db.py`

- `PRAGMA table_info(cortes_diarios)` → si no existe `obs_celdas_json`,
  `ALTER TABLE ADD COLUMN`.
- Para filas con `observaciones != ''` y `obs_celdas_json = '{}'`,
  sembrar `__manual__` con el texto viejo.
- **Un solo `conn.commit()` al final de `init_db()`**. Antes había commits
  intermedios que rompían la transacción.

### 3. Backend — `routers/corte_semanal.py`

Helpers:

- `_cargar_obs_celdas(row)` — lee `obs_celdas_json` tolerante a None/JSON roto.
- `_obs_manual_de(obs_celdas)` — devuelve `__manual__` limpio.
- `_formatear_obs_celda(campo, sub, valor_str, obs_texto)`:
  - Egreso → `Gasto de $X: <texto>`
  - Colaboradores → `Deuda de $X: <texto>`
  - Sin texto → `''`
- `_regenerar_observaciones(obs_manual, obs_celdas, dia)` — combina
  `__manual__` + cada clave, une con `\n`.

`_cargar_semana` y `_fila_vacia`: agregan `obs_celdas` a cada día.

`/datos`: agrega `obs_celdas` en cada fila.

`/actualizar`:

- Acepta `obs` en el payload.
- Caso `observaciones`: guarda en `__manual__` y regenera.
- Caso `por_cobrar`: guarda en `por_cobrar_json` y, si `subcampo ==
  "colaboradores"`, guarda el texto en `obs_celdas["por_cobrar:colaboradores"]`.
- Caso campo normal (egreso): guarda en la columna y, si aplica, el texto
  en `obs_celdas[campo]`.
- **Relee el valor fresco** de la celda antes de regenerar (para que la
  cantidad se actualice al editar).
- Devuelve `datos` + `totales` + `dias` (mismo formato que antes).

Se extrajo `_respuesta_actualizar(conn, anio, semana, campo, valor)` para
no duplicar el bloque de "releer + totales + enriquecer".

### 4. Frontend — `templates/corte_semanal.html`

- `#modal-celda-obs-wrap` (oculto por default) con
  `<textarea id="modal-celda-obs">`.
- `abrirModal(td)` decide si mostrarlo:
  - `EGRESOS_CAMPOS.has(campo)` → label "Detalle del gasto".
  - `campo === 'por_cobrar' && subcampo === 'colaboradores'` → label
    "Desglose del adeudo".
  - Carga el valor de `d.obs_celdas[key]`.
- `aplicarModal()` manda `obs` en el payload.
- `guardarRaw(payload)` acepta el payload completo (ya no filtra).
- Tab Observaciones: `<input class="corte-obs">` → `<textarea
  class="corte-obs" rows="1">`.
- Listener de `textarea.corte-obs`:
  - Auto-resize en focus e input.
  - Enter = salto de línea natural.
  - Ctrl/Cmd+Enter = forzar guardado.
  - Escape = revertir.
  - Blur = guardar por debounce.
- `pintar(data)` actualiza `textarea.corte-obs` con el texto regenerado.

### 5. CSS

`static/style.css`:

    textarea.corte-obs {
      width: 100%;
      min-height: 32px;
      resize: vertical;
      font-family: inherit;
      font-size: .875rem;
      padding: .25rem .5rem;
      line-height: 1.3;
      overflow: hidden;
      border: 1px solid #dee2e6;
      border-radius: .25rem;
      background: #fff;
    }
    textarea.corte-obs:focus {
      outline: none;
      border-color: #206bc4;
      box-shadow: 0 0 0 2px rgba(32, 107, 196, .15);
    }

## Bugs resueltos en esta sesión

- **`sqlite3.OperationalError: near ")": syntax error`** al arrancar:
  había una coma de más en el `CREATE TABLE cortes_diarios` al insertar
  `obs_celdas_json`. Fix: revisar el `CREATE TABLE` completo y dejar un
  solo `conn.commit()` al final de `init_db()` (antes había commits
  intermedios que rompían la transacción).
- **Formato `es de` en vez de `: `**: `_formatear_obs_celda` seguía con la
  versión vieja. Fix: reemplazar por `Gasto de $X: <texto>` y
  `Deuda de $X: <texto>`. Reiniciar uvicorn sin `--reload` para asegurar
  que el cambio se aplique.
- **`de de` duplicado** (`es de de agua`): el código viejo prefijaba
  `es de ` y el usuario escribía `de agua`. Fix: con el nuevo formato
  `: ` el usuario escribe solo el detalle.
- **Observaciones pegadas** (`MimiGasto de $100.00`): el tab Observaciones
  era un `<input type="text">` y no renderiza `\n`. Fix: cambiar a
  `<textarea>` + auto-resize.
- **`conn.commit()` huérfano**: había un commit justo después del
  `CREATE TABLE cortes_diarios`, lo que partía la transacción de la
  migración. Fix: un solo commit al final de `init_db()`.

## Estado actual

### Funcional
- ✅ Corte Semanal con observaciones por celda (egresos y colaboradores).
- ✅ Migración idempotente + siembra de `__manual__`.
- ✅ Regeneración automática de `observaciones` al editar monto.
- ✅ Tab Observaciones con `<textarea>` (saltos de línea reales).
- ✅ Todos los módulos anteriores siguen funcionando (Ingresos, Egresos,
  Recordatorios, Servicios Externos, Corte Semanal, Catálogo QVET).

### Pendiente (Corte)
- Validación más estricta al cerrar.
- Exportar a PDF.
- Historial de cierres.
- Tests automáticos de la regeneración de observaciones.

### Pendiente (global, arrastrado)
- Limpiar `print()` de debug en `sat/descarga.py` (líneas 142-146).
- Documentar instalación en Windows 11.
- Revisar `iicio.txt` y borrarlo.
- Tests automáticos (Recordatorios, Ingresos, Egresos, Corte, Servicios
  Externos).
- Arranque automático con el sistema.

## Cómo trabajar

- Arrancar: `uvicorn main:app --reload --host 127.0.0.1 --port 8000`
- Si `--reload` no aplica un cambio en un helper interno, matar uvicorn
  (`pkill -f uvicorn`) y arrancar sin `--reload`.
- Probar Corte Semanal: `http://127.0.0.1:8000/corte_semanal`
- La plantilla del Corte debe estar en
  `uploads/corte_semanal/plantilla_semanal.xlsx`.
- Si se pierde o corrompe: `python regenerar_plantilla.py`

## Reglas nuevas (Corte Semanal / Observaciones por celda)

45. `cortes_diarios.obs_celdas_json` guarda las observaciones por celda.
    `__manual__` es la observación libre del día.
46. `observaciones` del día se REGENERA a partir de `__manual__` + claves
    de `obs_celdas_json`. Nunca se anexa a mano.
47. Formato de las observaciones generadas:
    - Egreso: `Gasto de $X: <texto>`
    - Colaboradores: `Deuda de $X: <texto>`
48. Si el usuario edita el monto de la celda, la cantidad en la observación
    se recalcula; el texto escrito por el usuario se conserva.
49. Si el usuario borra el textarea, la línea desaparece de `observaciones`
    (se elimina la clave del JSON).
50. El tab Observaciones usa `<textarea>` (no `<input>`) para que los `\n`
    se rendericen como saltos de línea reales.
51. Un solo `conn.commit()` al final de `init_db()`. Los `CREATE TABLE` y
    `ALTER` van todos antes.
52. El textarea del modal de celda solo aparece para egresos y para
    `por_cobrar/colaboradores`. El resto de celdas no lo muestran.
53. `_respuesta_actualizar()` centraliza el "releer + totales +
    enriquecer" para no duplicar en `/actualizar`.

# Sesión de trabajo — 2026-11-04 (VetSuite Web v0.7)

## Resumen

Sesión enfocada en el módulo Servicios Externos (nuevo, /servicios_externos)
y en agregar "Ver registros" a Servicios Externos y Corte Semanal. Se
completó el módulo end-to-end (captura, filtros, cierre de semana, árbol de
reportes) y se ajustó la UI para que la tabla se vea igual que Ingresos y
Egresos.

Se completó:
- Módulo Servicios Externos end-to-end.
- Tablas servicios_externos y servicios_semanas.
- Filtro por semana ISO con navegación anterior / siguiente e input type week.
- Cierre / reapertura de semana con snapshot de totales.
- Botón principal dinámico (Cerrar / Reabrir) y badge de estado.
- Modal de reportes (árbol Año, Mes, Semana, Concepto, Estado).
- Modal de alta/edición con doble clic en fila.
- Listas editables de conceptos y tipos de pago (JSON).
- Registro en ip_permisos.json.
- "Ver registros" agregado a Corte Semanal (árbol Año, Semana, Sucursal).

## Qué se hizo

### 1. Modelo de datos

Dos tablas nuevas en db.py (init_db):

Tabla servicios_externos (una fila por servicio):

    id INTEGER PRIMARY KEY AUTOINCREMENT,
    concepto TEXT NOT NULL DEFAULT '',
    fecha TEXT NOT NULL,                       -- YYYY-MM-DD
    cliente TEXT NOT NULL,
    mascota TEXT DEFAULT '',
    recuperacion TEXT DEFAULT '',              -- 'Si' | 'No' | 'N/A'
    fecha_entrega TEXT DEFAULT '',
    total REAL NOT NULL DEFAULT 0,
    fecha_pago TEXT DEFAULT '',                -- '' = pendiente
    tipo_pago TEXT DEFAULT '',                 -- 'Efectivo' | 'Transferencia' | 'TC' | 'TD'
    notas TEXT DEFAULT '',
    creado_en TEXT DEFAULT CURRENT_TIMESTAMP,
    actualizado_en TEXT DEFAULT CURRENT_TIMESTAMP

Tabla servicios_semanas (una fila por semana ISO):

    id INTEGER PRIMARY KEY AUTOINCREMENT,
    anio INTEGER NOT NULL,
    semana INTEGER NOT NULL,
    desde TEXT NOT NULL,                       -- lunes YYYY-MM-DD
    hasta TEXT NOT NULL,                       -- domingo YYYY-MM-DD
    estado TEXT NOT NULL DEFAULT 'abierta',    -- abierta | cerrada
    cerrado_en TEXT,
    total_pendiente REAL NOT NULL DEFAULT 0,
    total_pagado REAL NOT NULL DEFAULT 0,
    n_registros INTEGER NOT NULL DEFAULT 0,
    UNIQUE(anio, semana)

### 2. Configuración — servicios_externos_config.json

Listas editables en JSON (NO va a git):

    {
      "conceptos": ["Incineración", "Hemograma"],
      "tipos_pago": ["Efectivo", "Transferencia", "TC", "TD"]
    }

- core/servicios_externos/config.py — cargar, guardar, agregar_concepto,
  agregar_tipo_pago.
- Tipos de pago fijos (sin botón "+" desde la UI).
- Conceptos editables desde el modal.
- Endpoints:
  - GET  /servicios_externos/config
  - POST /servicios_externos/config/concepto
  - POST /servicios_externos/config/tipo-pago

### 3. Backend — routers/servicios_externos.py

Endpoints:
- GET  /servicios_externos — página.
- GET  /servicios_externos/datos?anio=&semana= — filas + totales + metadatos
  (estado, desde, hasta, rango_legible). Cache-Control: no-store.
- POST /servicios_externos/actualizar — crear/editar. 409 si cerrada.
  Verifica también la semana original del registro si cambia de fecha.
- POST /servicios_externos/marcar-pagado — 409 si cerrada.
- POST /servicios_externos/eliminar — 409 si cerrada.
- POST /servicios_externos/cerrar — guarda snapshot de totales.
- POST /servicios_externos/reabrir — limpia cerrado_en y totales.
- GET  /servicios_externos/arbol — árbol Año, Mes, Semana, Concepto, Estado
  con _total en cada nivel + _total raíz.
- GET  /servicios_externos/semanas?anio= — listado de semanas del año.

Helpers:
- _semana_de_fecha(conn, fecha_iso) — asegurar_semana por fecha.
- _conflicto(msg) — JSONResponse(..., status_code=409).

### 4. Frontend — templates/servicios_externos.html

- Header: "Sem del rango" ("del 2 nov al 8 nov 2026") + badge Abierta/Cerrada.
- Barra de herramientas:
  - Izquierda: Cerrar/Reabrir (dinámico), "Ver registros", "+ Nuevo servicio".
  - Derecha: navegación anterior / input type week / siguiente.
- Filtros: Concepto, Estado, Limpiar (client-side con debounce).
- Tabla dentro de div class tabla-scroll (misma clase que Ingresos/Egresos).
- tfoot sticky con totales: registros, total, pendiente, pagado.
- Modal dialog id modal-serv con todos los campos.
- Modal dialog id modal-reportes con árbol Año, Mes, Semana, Concepto, Estado.
- dblclick en fila — editar. Clic simple — seleccionar.
- Botón Eliminar dentro del modal (no en la fila).
- window.abrirModalReportes = abrirModalReportes al final del IIFE.

### 5. Semanas ISO — core/servicios_externos/semanas.py

Wrapper de core/corte/semanas.py:
- asegurar_semana(conn, anio, semana) — crea la fila si no existe.
- semana_actual() — tupla (anio, semana) de hoy.

### 6. Migración del Excel original

Scripts puntuales (NO van a git):
- migrar_servicios_externos.py — lee Inicineraciones.xlsx, normaliza
  recuperacion y parsea pagado ("Efectivo 24/10/26" a fecha_pago + tipo_pago).
- migrar_tipos_pago.py — "Tarjeta débito" a TD, "Tarjeta crédito" a TC.
- migrar_recuperacion.py — "Con recuperación" a Si, "Sin recuperación" a No.

### 7. "Ver registros" en Corte Semanal

Se agregó el mismo patrón que en Ingresos / Egresos / Servicios Externos:
- Backend: GET /corte_semanal/arbol (árbol Año, Semana, Sucursal con
  ingresos, egresos y utilidad por semana; evalúa expresiones 2345+679).
- Frontend: botón + dialog id modal-reportes-corte + funciones
  abrirModalReportes, nodoAnioCorte, nodoSemanaCorte, nodoSucursalCorte
  dentro del IIFE.
- Clic en sucursal — navega a /corte_semanal?anio=&semana=.

## Bugs resueltos en esta sesión

- /servicios_externos daba 404 — faltaba include_router y la ruta estaba
  como servicios-externos (guion). Fix: usar servicios_externos (guion bajo).
- Modal que no abría — un div de más cerraba el form antes del botón
  Guardar. Fix: quitar el div sobrante.
- "Cannot access SEMANA before initialization" — let SEMANA después de
  init(). Fix: declararla al inicio del IIFE.
- "Cannot set properties of null (setting value)" — pintarEstadoSemana
  tocaba f-semana-ref sin verificar. Fix: guardar con if.
- "q is not defined" — aplicarFiltros usaba q (input eliminado). Fix:
  quitar el bloque if (q).
- "abrirModalReportes is not defined" — la función estaba dentro del IIFE
  pero el botón usaba onclick. Fix: window.abrirModalReportes = ...
- "cargar is not defined" en nodos del árbol — cargar, semanaDeFecha,
  rangoSemana, formatearRango, pintarEstadoSemana estaban dentro de init().
  Fix: moverlas al IIFE (solo listeners en init()).
- Fondo transparente en el dialog — dialog sin background. Fix:
  background var(--tblr-bg-surface, #ffffff) en dialog.modal-propio[open].
- Tabla se salía de la pantalla — tabla-serv con table-layout fixed y
  min-width 900px. Fix: quitar id, borrar reglas de tabla-serv del CSS y
  usar div class tabla-scroll.
- Scroll aplicado a toda la página — contenedor sin max-height. Fix: usar
  tabla-scroll (ya tiene max-height calc(100vh - 380px)).
- "..." al lado del icono eliminar — tooltip nativo del title. Fix: mover
  el botón eliminar al modal.
- Datos no se veían al cambiar semana — handler del input type week
  parseaba mal. Fix: parsear YYYY-Www correctamente.
- Semana actual no cargaba al abrir — init() no inicializaba SEMANA.
  Fix: SEMANA = { ...SEMANA, ...semanaDeFecha(hoy) } antes de cargar().

## Estado actual

Funcional:
- Módulo Servicios Externos completo.
- "Ver registros" en Servicios Externos y Corte Semanal.
- Semana actual por defecto al abrir el módulo.
- Tipos de pago: Efectivo, Transferencia, TC, TD.
- Recuperación: Si, No, N/A.
- Todos los módulos anteriores siguen funcionando (Ingresos, Egresos,
  Recordatorios, Corte Semanal).

Pendiente (Servicios Externos):
- Exportar a Excel (opcional).
- Historial de semanas cerradas.

Pendiente (global, arrastrado):
- Limpiar print() de debug en sat/descarga.py (líneas 142-146).
- Documentar instalación en Windows 11.
- Revisar iicio.txt (archivo huérfano) y borrarlo.
- Tests automáticos (Recordatorios, Ingresos, Egresos, Corte, Servicios
  Externos).
- Arranque automático con el sistema.

## Cómo trabajar

- Arrancar: uvicorn main:app --reload --host 127.0.0.1 --port 8000
- Probar Servicios Externos: http://127.0.0.1:8000/servicios_externos
- Probar Corte Semanal: http://127.0.0.1:8000/corte_semanal
- Si el JSON de configuración se pierde, se regenera con los defaults.
- Migración de datos viejos: python migrar_servicios_externos.py (una vez).
  Después python migrar_tipos_pago.py y python migrar_recuperacion.py.

## Reglas nuevas (Servicios Externos)

1. Una sola tabla servicios_externos. El cierre es por semana ISO en
   servicios_semanas.
2. Estado "pendiente" = fecha_pago vacío. Sin columna booleana.
3. tipo_pago se limpia si no hay fecha_pago.
4. Listas en servicios_externos_config.json (read-write desde la app).
   Tipos de pago fijos, conceptos editables.
5. recuperacion es listbox cerrado: Si, No, N/A.
6. Semana cerrada es inmutable. /actualizar, /eliminar y /marcar-pagado
   responden 409.
7. Al cerrar se guarda snapshot de totales en servicios_semanas.
8. Botón principal dinámico (Cerrar / Reabrir).
9. La tabla muestra una sola semana. Navegación con anterior / siguiente
   o input type week.
10. Árbol de reportes con 5 niveles: Año, Mes, Semana, Concepto, Estado.
11. Ruta con guion bajo: /servicios_externos.
12. Módulo "servicios_externos" en ip_permisos.json.
13. La tabla usa .tabla-scroll, no id propio. Sin table-layout fixed ni
    min-width.
14. El botón eliminar vive en el modal, no en la fila.
15. window.abrirModalReportes = abrirModalReportes al final del IIFE.

## Reglas nuevas (globales)

16. Si un dialog tiene un div de más, el contenido se renderiza inline.
    Verificar con dialog.children.length igual a 1 y
    dialog.querySelector('button[type="submit"]') distinto de null.
17. let con TDZ mata el IIFE. Declarar variables al inicio del IIFE.
18. Las funciones del árbol de reportes viven en el IIFE, no dentro de
    init(). Solo listeners en init().
19. Exponer en window solo lo necesario por onclick, dentro del IIFE.
20. La tabla estándar es .tabla-scroll. No inventar contenedores nuevos.
21. La fila con dblclick tiene cursor pointer y el modal abre con
    showModal().
22. Antes de agregar una columna al tfoot, contar las del thead.

# Sesión de trabajo — 2026-11-03 (VetSuite Web v0.6)

## Resumen

Sesión enfocada en el **módulo Corte Semanal** (`/corte`), que reemplaza el
Excel semanal manual de Baalak y Prado. Se implementó captura diaria,
totales en vivo, Excel con fórmulas vivas usando plantilla, cierre de
semana y permisos por IP.

Se completó:
- Módulo Corte Semanal end-to-end.
- Captura por celda con modal (acepta `2345+679`).
- Layout tipo Excel (conceptos en filas, días en columnas).
- Sub-tabs por bloque (Ingresos / Egresos / Por cobrar / Observaciones).
- Tabs por sucursal (Baalak / Prado).
- Resumen de tarjetas por sucursal activa.
- Generador de Excel desde plantilla (fórmulas vivas).
- Cierre y reapertura de semana.
- Registro del módulo en `ip_permisos.json`.

## Qué se hizo

### 1. Modelo de datos

Dos tablas nuevas en `db.py` (init_db):

- `cortes_diarios` (una fila por día/sucursal, `UNIQUE(fecha, sucursal)`).
- `cortes_semanas` (una fila por semana ISO, `UNIQUE(anio, semana)`).

Campos monetarios como **TEXT** para preservar expresiones tipo `2345+679`.

### 2. Parser seguro de expresiones (`core/corte/expr.py`)

- `evaluar_expr(texto)` → float. Suma segura de `a+b+c`, sin `eval()`.
- `es_expresion(texto)` → bool (si tiene `+` entre dígitos).
- `fmt_monto(float)` → `"$X,XXX.XX"`.

### 3. Helpers de semana ISO (`core/corte/semanas.py`)

- `lunes_de(anio, semana)`, `dias_de(anio, semana)`.
- `semana_actual()`, `semana_de_fecha(date)`.
- `asegurar_semana(conn, anio, semana)` → crea si no existe, devuelve fila.
- `rango_legible(anio, semana)` → `"26 oct al 1 nov 2026"`.

### 4. Backend (`routers/corte.py`)

Endpoints:
- `GET /corte` → página.
- `GET /corte/datos` → JSON con filas + totales (no-store).
- `POST /corte/actualizar` → upsert de celda. `409` si cerrada.
- `GET /corte/excel` → sirve guardado (cerrada) o genera al vuelo (abierta).
- `POST /corte/cerrar` → genera, guarda y cierra.
- `POST /corte/reabrir` → borra Excel y reabre.

### 5. Frontend (`templates/corte.html`)

- Tabs de sucursal (Baalak / Prado).
- Sub-tabs por bloque (Ingresos / Egresos / Por cobrar / Observaciones).
- Tablas tipo Excel con header/footer sticky y columna de conceptos sticky.
- Modal de captura (`<dialog id="modal-celda">`) con total en vivo.
- Modal de cierre (`<dialog id="modal-cerrar">`).
- Botón principal dinámico: "Cerrar semana" (abierta) o "Descargar Excel"
  (cerrada).
- Dropdown "⋯ Más" con "Reabrir semana" (solo si cerrada).
- Doble clic en celda → modal. Enter en modal → guarda y baja. Shift+Enter
  → sube. Escape → cancela.
- Guardado con debounce 400ms en observaciones. En celdas, guardado
  inmediato al confirmar el modal.

### 6. Generador de Excel (`core/corte/excel_corte.py`)

- Usa plantilla `uploads/cortes/plantilla_semanal.xlsx`.
- Offsets relativos al título: `TITULO_FILA = {"Baalak": 2, "Prado": 41}`.
- Filas relativas: `R = {dias: 1, fechas: 2, efectivo_dep: 3, ...}`.
- Solo rellena celdas de captura. Las fórmulas y estilos se conservan del
  original.
- Valores con `+` se escriben como fórmula (`=2345+679`).
- Nombre de hoja: `Sem del <día1> al <día7>`.
- Nombre de archivo: `Semanal Baalak-Prado <Mes>.xlsx` (mes del lunes).
- Archivo guardado al cerrar: `<año>-W<semana> - <nombre_archivo>`.

### 7. Plantilla (`regenerar_plantilla.py`)

Script opcional que regenera `plantilla_semanal.xlsx` desde cero, con
estructura exacta del original. Útil si la plantilla se pierde o corrompe.

### 8. Permisos IP

- `core/permisos_ip.py`: `"corte"` ya está en `_DEFAULT["modulos"]` y en
  `modulo_de_path()`.
- `base.html`: ya tiene el `<li>` de Corte condicionado a
  `{% if 'corte' in __mods %}`.
- En `ip_permisos.json` (producción), agregar `"corte"` a la lista `modulos`
  global y a la entrada de cada IP que lo necesite.

## Bugs resueltos en esta sesión

- **`/corte` daba 404** → faltaba `app.include_router(corte.router)` en
  `main.py`.
- **`modulos_ip is undefined`** → `corte.py` creaba su propio
  `Jinja2Templates` sin los globals. Fix: importar `templates` de
  `templates_shared`.
- **"Error de red" al guardar** → el POST devolvía JSON correcto pero el
  JS explotaba en `pintarTotalesFila`. Fix: el POST ahora devuelve `datos`
  y `totales`; el JS los usa.
- **Efectivo cobrado no se actualizaba** → faltaba pintar esa fila
  calculada. Fix: bloque nuevo en `pintarTodo`.
- **Enter navegaba a la derecha** → se cambió a navegación vertical (baja
  una fila).
- **Doble clic no abría el modal** → el `<dialog>` estaba después del
  `<script>` y `getElementById` devolvía `null`. Fix: delegación de
  eventos + capturar elementos dentro de cada handler.
- **`modal-celda-cerrar-x` explotaba** → faltaba id en el botón ✕.
- **Tabs con letras blancas ilegibles** → conflicto con la regla global de
  `.nav-tabs .nav-link.active` de Recordatorios. Fix: especificidad con
  `ul.nav.nav-tabs.nav-tabs-sub`.
- **PRADO con fechas en "Efectivo cobrado"** → la plantilla tenía la fila
  de fechas corrida. Fix: plantilla regenerada + offsets relativos al
  título (no al bloque).
- **`OFFSET_SUCURSAL` incorrecto** → no era `{"Baalak": 0, "Prado": 41}`
  sino relativo al título: `TITULO_FILA = {"Baalak": 2, "Prado": 41}` y
  `R = {dias: 1, ...}`. Con eso todo cae donde debe.

## Estado actual

### Funcional
- ✅ Módulo **Corte Semanal** completo.
- ✅ Captura día a día con expresiones (`2345+679`).
- ✅ Excel con fórmulas vivas e idéntico al original.
- ✅ Cierre / reapertura de semana.
- ✅ Permisos por IP.
- ✅ Todos los módulos anteriores siguen funcionando (Ingresos, Egresos,
  Recordatorios, Catálogo QVET, Reportes).

### Pendiente (Corte)
- 📝 Validación más estricta al cerrar.
- 📝 Exportar a PDF (opcional).
- 📝 Historial de cierres.

### Pendiente (global, arrastrado)
- 🧹 Limpiar `print()` de debug en `sat/descarga.py` (líneas 142-146).
- 🪟 Documentar instalación en Windows 11.
- 🐛 Revisar `iicio.txt` (archivo huérfano) y borrarlo.
- 🧪 Tests automáticos (Recordatorios, Ingresos, Egresos, Corte).
- ⏰ Arranque automático con el sistema.

## Cómo trabajar

- Arrancar: `uvicorn main:app --reload --host 127.0.0.1 --port 8000`
- Probar Corte: `http://127.0.0.1:8000/corte`
- La plantilla del Corte debe estar en `uploads/cortes/plantilla_semanal.xlsx`.
- Si se pierde o corrompe: `python regenerar_plantilla.py`
- Los Excel cerrados viven en `uploads/cortes/<año>-W<semana> - Semanal...xlsx`.

## Reglas nuevas (Corte)

1. **Montos como TEXT**, se evalúan con `core/corte/expr.py`. Sin `eval()`.
2. **`efectivo_cobrado` es calculado**, no editable.
3. **Excel desde plantilla**, no se genera a mano. Solo se rellenan celdas.
4. **Valores con `+`** se escriben como fórmula en Excel.
5. **Nombre de hoja**: `Sem del <día1> al <día7>`.
6. **Nombre de archivo**: `Semanal Baalak-Prado <Mes>.xlsx` (mes del lunes).
7. **Archivo cerrado**: `<año>-W<semana> - Semanal Baalak-Prado <Mes>.xlsx`.
8. **Semana cerrada = 409** en `/corte/actualizar`.
9. **Reabrir borra el Excel** guardado.
10. **Módulo `"corte"`** en `ip_permisos.json` (global y por IP).

# Sesión de trabajo — 2026-11-01 (VetSuite Web v0.5)

## Resumen

Sesión enfocada en **Catálogo QVET** y **Reportes (árbol)** en Ingresos y
Egresos, más ajustes de UI en Recordatorios y modales.

Se completó:
- Catálogo QVET con consulta + edición + agregar (desde `/ingresos/catalogo`).
- Filtrado client-side del catálogo (input en vivo + chips de categoría).
- Modal de reportes con árbol jerárquico en Ingresos y Egresos.
- Fix del `_total` a nivel raíz en ambos árboles.
- Modales que no se cierran al hacer clic fuera (consistencia).
- Pestaña activa de Recordatorios con color.
- Fix `fmt` vs `fmtMonto` en Ingresos.

## Qué se hizo

### 1. Catálogo QVET (`/ingresos/catalogo`)

**Backend (`routers/ingresos.py`):**
- `GET /ingresos/catalogo` → manda TODOS los items (filtrado real es client-side).
- `POST /ingresos/catalogo/actualizar` → cambia categoría (guarda en `categorias_manuales.json`).
- `POST /ingresos/catalogo/agregar` → agrega producto nuevo.
- `POST /ingresos/catalogo/eliminar` → quita override (vuelve a base o `U`).
- Reutiliza `cargar_catalogo()`, `cargar_excepciones_manuales()`, `agregar_producto_catalogo()`, `borrar_producto_catalogo()`, `recargar_catalogo()`, `normalizar()` de `lector_facturas.py`.

**Template (`templates/catalogo.html`):**
- Input de búsqueda en vivo (debounce 150ms).
- Chips de categoría clickeables (Todas + una por categoría con conteo).
- Tabla con select inline por fila para cambiar categoría.
- Columna "Origen": "Base QVET" o "Corregido".
- Botón ✕ en filas corregidas para quitar el override.
- Modal "➕ Agregar producto".
- `history.replaceState` para URL compartible.

**CSS (`static/style.css`):**
- `.chip-cat`, `.chip-activo`, `.chip-inactivo`.

**Acceso desde:**
- `/ingresos` → botón "📚 Catálogo" (con badge de conteo) + dropdown "⋯ Más".
- `/ingresos/reclasificar` → botón "📚 Ver catálogo completo".

**Reglas del catálogo:**
- `catalogo_qvet.json` → base, curada a mano, read-only desde la app.
- `categorias_manuales.json` → overrides, read-write.
- El parser consulta primero manuales, luego base.
- No se mueve a SQLite: es configuración, no dato transaccional.

### 2. Modal de reportes (árbol)

**Ingresos (`templates/ingresos.html` + `routers/ingresos.py`):**
- Botón "📋 Ver registros".
- `<dialog id="modal-reportes">` con árbol **Año → Mes → Sucursal**.
- Backend `GET /ingresos/arbol` con agregados.
- Año y Mes solo expanden/colapsan (`<details>`).
- Sucursal aplica filtro con clic simple.

**Egresos (`templates/egresos.html` + `routers/egresos.py`):**
- Mismo botón y modal.
- Árbol **Año → Mes → Sucursal → PUE/PPD**.
- Backend `GET /egresos/arbol` con agregados.
- Año y Mes solo expanden/colapsan.
- Sucursal aplica filtro con clic simple.
- PUE/PPD aplican filtro con clic simple. Si `n === 0`, el botón se deshabilita.
- PUE y PPD se muestran **siempre ambos**, aunque uno esté vacío.

**Reglas del árbol:**
- El `_total` debe existir en **tres niveles**: sucursal, mes y raíz.
- Sin el de raíz, el footer del modal muestra 0.
- Los totales se calculan sobre las filas ya filtradas.
- `metodo_pago` normalizado a `PUE` o `PPD` al insertar.
- Filtro SQL para PUE tolerante a `NULL`/`""` con `COALESCE(NULLIF(metodo_pago, ''), 'PUE')`.
- Headers `Cache-Control: no-store` en el JSON para evitar cache del navegador.

**Fix del `_total` raíz (bug resuelto en esta sesión):**
- El backend ponía `_total` dentro de cada año pero no a nivel raíz.
- El JS del modal lee `data._total` (raíz) y no lo encontraba → footer en 0.
- Solución: agregar al final de `arbol_egresos()` y `arbol_ingresos()`:

```python
arbol["_total"] = {
    "n": sum(v["_total"]["n"] for k, v in arbol.items() if k != "_total"),
    "total": round(sum(
        v["_total"]["total"] for k, v in arbol.items() if k != "_total"
    ), 2),
}
```

**Fix `fmt` vs `fmtMonto` (bug resuelto en esta sesión):**
- `ingresos.html` usa `fmt()`.
- `egresos.html` usa `fmtMonto()`.
- Al copiar el JS de Egresos a Ingresos se coló `fmtMonto` → `ReferenceError`.
- Solución: en `ingresos.html`, cambiar `fmtMonto` por `fmt`.

### 3. Modales que no se cierran al clic fuera

**Opción A aplicada (consistencia con Ingresos/Egresos que usan `<dialog>`):**
- `admin_ips.html`: eliminado `modal.addEventListener('click', ...)`.
- `recordatorios.html`:
  - `modalImportar` y `modalReset`: agregado `data-bs-backdrop="static" data-bs-keyboard="false"`.
  - `modalMensaje`: eliminado el listener de clic fuera.
- Ingresos, Egresos, Catálogo: sin cambios (ya usan `<dialog>` sin listener).
- `rechazados.html`, `rechazados_rescatar.html`, `reclasificar.html`, `egresos_historial.html`, `egresos_rechazados.html`: sin modales, sin cambios.

### 4. Pestaña activa de Recordatorios

- En `static/style.css`: `.nav-tabs .nav-link.active` con fondo azul y texto blanco.
- Las tabs vuelven al estilo original de Bootstrap; solo cambia el color del activo.

### 5. Bugs resueltos en esta sesión

- **Catálogo: `Not Found` al abrir `/catalogo`** → era `/ingresos/catalogo` (prefix del router). Reiniciar uvicorn con `--reload`.
- **Catálogo: filtrado no funcionaba al cambiar chip** → backend ahora manda todos los items, filtrado client-side.
- **Recordatorios: modales se cerraban al clic fuera** → `data-bs-backdrop="static"`.
- **Modal reportes Egresos: footer en 0** → faltaba `_total` raíz en `arbol_egresos()`.
- **Modal reportes Ingresos: `fmtMonto is not defined`** → cambiar a `fmt` en `ingresos.html`.
- **Uvicorn sin `--reload`** → los cambios no se aplicaban hasta reiniciar. Ahora siempre arrancar con `--reload`.
- **`qrdev` lanzaba uvicorn sin `--reload`** → matar `qrdev` con `pkill -f qrdev` y arrancar uvicorn manualmente.
- **Cache del navegador en `fetch('/egresos/arbol')`** → agregar `?t=' + Date.now()` o `Cache-Control: no-store` en el endpoint. Se aplicaron ambas.

## Estado actual

### Funcional
- ✅ Módulo **Ingresos** completo.
- ✅ Módulo **Egresos** completo.
- ✅ Módulo **Recordatorios** completo.
- ✅ **Catálogo QVET** con consulta + edición + agregar.
- ✅ **Reportes (árbol)** en Ingresos y Egresos.
- ✅ Rediseño visual con Tabler UI en los tres módulos.
- ✅ Historial del SAT con reprocesamiento.
- ✅ Cambio de sucursal Animalia ↔ Baalak (Egresos) y Central/Prado/Animalia (Recordatorios).
- ✅ Descarga de Gmail (3 modos) + SAT con polling.
- ✅ Procesamiento de XMLs y PDFs.
- ✅ ZIP mensual con estructura de escritorio.
- ✅ Reset por módulo.
- ✅ Persistencia de UI en Recordatorios (tab y scroll).
- ✅ Modales no se cierran al clic fuera.

### Pendiente
- 📝 Actualizar `CONTEXTO.md` con la arquitectura final. **(hecho en esta sesión)**
- 🧹 Limpiar `print()` de debug en `sat/descarga.py` (líneas 142-146).
- 🪟 Documentar instalación en Windows 11.
- 🧪 Pruebas del usuario final en Ingresos, Egresos y Recordatorios.
- 🐛 Revisar `iicio.txt` (archivo huérfano) y borrarlo.

## Cómo trabajar

- Arrancar: `uvicorn main:app --reload --host 127.0.0.1 --port 8000`
- **Siempre con `--reload`** para que los cambios se apliquen sin reiniciar.
- Si usas `qrdev` u otra herramienta que lance uvicorn, **mata el proceso** (`pkill -f qrdev`) y arranca uvicorn manualmente.
- Probar: `http://127.0.0.1:8000/ingresos`, `/egresos`, `/recordatorios`, `/ingresos/catalogo`
- Probar parser de Recordatorios: `python probar_parser.py archivo.xlsx`
- La BD está en `vetsuite.db` (no va a git)
- Los archivos de `uploads/` no van a git
- Configs que NO van a git: `gmail_config.json`, `egresos_config.json`, `recordatorios_config.json`, `catalogo_qvet.json`, `categorias_manuales.json`, `proveedores_sucursal.json`, `solicitud_sat_activa.json`, `jobs_state.json`
- Si se corrompen los archivos de Ingresos: `python reparar_archivos.py`
- Si hay basura en `uploads/facturas/`: `python limpiar_facturas.py`

## Reglas

1. **El PDF es la fuente de productos en Ingresos** (XML = solo cabecera).
2. **El XML es la fuente de todo en Egresos** (no hay PDF).
3. **Los archivos de Ingresos se guardan como `<folio>.xml|.pdf`.**
4. **Los archivos de Egresos se guardan como `<serie>-<folio>.xml`.**
5. **Sucursal de Ingresos por serie**: `S1` → Baalak, `Prados` → Prado.
6. **Sucursal de Egresos por RFC del proveedor** (en `proveedores_sucursal.json`, default Baalak).
7. **Sucursal de Recordatorios por `recordatorios_config.json`** (`BAALAK_CENTRAL`, `BAALAK_PRADO`, `ANIMALIA`).
8. **`datos_json` guarda todos los campos del Excel de Ingresos.**
9. **El ZIP mensual incluye el Excel** con la estructura de escritorio.
10. **El historial del SAT se guarda siempre** (si `guardar_historial_sat: true` en `egresos_config.json`).
11. **El token del SAT expira en 5 min**: obtener uno fresco por paquete.
12. **El SAT devuelve el ZIP en `paquete_b64`**, no en `paquete`.
13. **Reset borra TODO lo del módulo** pero NO lo global.
14. **`base.html` expone `{% block head %}` y `{% block scripts %}`** para que cada página cargue su CSS/JS.
15. **Recordatorios persiste en JSON + `localStorage`** (tab y scroll).
16. **Los archivos listados en la sección "Cómo trabajar" NO van a git.**
17. **El catálogo QVET vive en JSON, no en SQLite.** Es configuración, no dato transaccional.
18. **El catálogo se filtra client-side.** El endpoint manda todos los items; el navegador filtra por texto y chips.
19. **Los árboles de reportes se calculan en el backend.** Solo agregados (conteos y totales), nunca facturas individuales.
20. **`metodo_pago` se normaliza a `PUE` o `PPD` al insertar.** Valores vacíos o `None` → `PUE`.
21. **`_total` en el árbol debe existir en 3 niveles**: sucursal, mes y raíz. Sin el de raíz, el footer del modal sale en 0.
22. **Los modales no se cierran al clic fuera.** Solo con ✕, botón "Cerrar" o Escape.
23. **En `ingresos.html` la función de formato es `fmt`. En `egresos.html` es `fmtMonto`.** No mezclar.
24. **Siempre arrancar uvicorn con `--reload`.** Si otra herramienta (qrdev, npx) lo lanza sin `--reload`, matarla y arrancar manualmente.

## Pendientes (deuda técnica)

- [ ] Tests automáticos del parser de Recordatorios.
- [ ] Tests automáticos del pipeline de Ingresos y Egresos.
- [ ] Documentación de instalación en Windows 11.
- [ ] Arranque automático con el sistema (tarea programada).
- [ ] Endpoint `/egresos/zip` con filtro por rango de fechas (ahora solo por mes).
- [ ] Rotación de snapshots del SAT (borrar los de más de 6 meses).
- [ ] Manejo de XMLs de tipo E (notas de crédito) y P (complementos de pago) si el usuario los necesita.
- [ ] Filtros en vivo (server-side con debounce) en Ingresos y Egresos. Evaluado y descartado por ahora; el modal de reportes cubre la necesidad de "ver por período".

# Sesión de trabajo — 2026-10-30 (VetSuite Web v0.4)

## Resumen

Se completó el módulo de **Recordatorios** al 100% en la web. Se implementó
importación de Excel (citas y vacunas), generación de mensajes con
agrupación inteligente, envío por WhatsApp vía `wa.me`, historial de envíos,
exportación a Excel, reset por módulo, cambio de sucursal con regeneración
de mensajes no enviados y persistencia de UI (tab activo y scroll) en
`localStorage`.

## Qué se hizo

### 1. Parser de Excel (`core/recordatorios/procesar_excel.py`)

- Detección de tipo por **columnas** del encabezado (no por nombre de
  archivo ni de hoja). Soporta múltiples hojas por archivo.
- Columnas de citas: `FECHA, INICIO, TIPO VISITA, PROPIETARIO, MASCOTA,
  TELÉFONO, ASUNTO, AGENDA, ESTADO`.
- Columnas de vacunas: `CLIENTE, TELÉFONO 1, TELÉFONO 2, MASCOTA,
  TIPO DE RECORDATORIO, VACUNA, PRÓXIMA FECHA`.
- Expansión de abreviaturas: `segui→seguimiento, trat→tratamiento,
  mp→medicina preventiva, c/con→consulta, ciru→cirugía, b→baño,
  cp→corte, b y t→baño y transporte, b y cp→baño y corte`, etc.
- Omisión de clientes referidos (`CLIENTE REFERIDO...`, `REFERIDO...`).
- Normalización de teléfonos (quita espacios/guiones, agrega 52 a
  10 dígitos, respeta códigos de otros países).
- Generación de mensajes:
  - **Citas**: agrupa servicios por hora; si >1 mascota o >1 hora,
    agrega aviso de dudas.
  - **Vacunas**: >3 mascotas y mismo conjunto (tipo, vacuna, fecha) →
    agrupa nombres; mismo tipo con fechas/vacunas distintas → agrupa
    por (tipo, fecha); diferencias de tipo → lista por mascota.
    Aviso de dudas cuando hay >1 vacuna, >1 fecha o >1 tipo.

### 2. Backend de Recordatorios

- `core/rutas_recordatorios.py`: rutas a `uploads/recordatorios/` y
  `recordatorios_config.json`.
- `core/recordatorios/sucursales.py`: cargar/guardar sucursal activa.
- `core/recordatorios/historial.py`: envíos con hash del mensaje.
- `core/recordatorios/envio.py`: construir URL `wa.me`.
- `routers/recordatorios.py`: endpoints de importar, marcar, desmarcar,
  WhatsApp, exportar Excel, reset y cambiar sucursal.

### 3. UI de Recordatorios (`templates/recordatorios.html`)

- Dos tabs (Citas / Vacunas) con persistencia del tab activo.
- Scroll por tabla y de página persistidos.
- Selección por **clic en la fila** (radio oculto interno).
- Un solo botón de envío/marcar/desmarcar en la barra superior.
- Modal de mensaje **propio** (no depende de Bootstrap JS).
- Cambio de sucursal automático al elegir en el `<select>`.
- Tabla con `max-height: calc(100vh - 260px)`.

### 4. `base.html` y `static/style.css`

- `base.html` ahora expone `{% block head %}` y `{% block scripts %}`
  para que cada página cargue su CSS/JS sin ensuciar el layout.
- `static/style.css` incluye estilos de `.tabla-sel`, `.sel-row` y
  `.modal-propio`.

### 5. Configuración

- `recordatorios_config.json` con 3 sucursales:
  - `BAALAK_CENTRAL` → "Baalak (Central)"
  - `BAALAK_PRADO` → "Baalak (Prado)"
  - `ANIMALIA` → "Animalia"

### 6. Script de prueba

- `probar_parser.py`: imprime por consola los clientes y mensajes
  generados por el parser, para validar antes de importar en la web.

## Bugs resueltos en Recordatorios

- **Botón 👁 Ver no hacía nada**: el modal dependía de Bootstrap JS y
  el `dataset` se rompía con saltos de línea. Fix: modal propio en
  HTML+CSS+JS vanilla y `getAttribute('data-mensaje')`.
- **Regla intermedia de agrupación no se disparaba**: el `_canon`
  comparaba vacunas con espacios dobles (`DRONTAL  35` vs
  `DRONTAL 35`). Fix: `_normalizar_vacuna` colapsa espacios.
- **AGROTECHNOLOGY (11 mascotas) listaba una por una**: las fechas
  diferían entre mascotas (15 vs 16/10). Fix: agrupar por (tipo, fecha)
  cuando todas comparten el mismo tipo.
- **Cliente referido aparecía**: faltaba filtro. Fix: `_es_cliente_referido`.
- **Abreviaturas sin expandir**: `segui`, `trat`, `mp`, etc. Fix:
  diccionario `ABREVIATURAS` + `_expandir`.

## Estado actual

### Funcional
- ✅ Módulo **Ingresos** completo.
- ✅ Módulo **Egresos** completo.
- ✅ Módulo **Recordatorios** completo.
- ✅ Rediseño visual con Tabler UI en los tres.
- ✅ Historial del SAT con reprocesamiento.
- ✅ Cambio de sucursal Animalia ↔ Baalak (Egresos) y
  Central / Prado / Animalia (Recordatorios).
- ✅ Descarga de Gmail (3 modos) + SAT con polling.
- ✅ Procesamiento de XMLs y PDFs.
- ✅ ZIP mensual con estructura de escritorio.
- ✅ Reset por módulo.
- ✅ Persistencia de UI en Recordatorios (tab y scroll).

### Pendiente
- 📝 Actualizar `CONTEXTO.md` con la arquitectura final. **(hecho en esta sesión)**
- 🧹 Limpiar `print()` de debug en `sat/descarga.py` (líneas 142-146).
- 🪟 Documentar instalación en Windows 11.
- 🧪 Pruebas del usuario final en Ingresos, Egresos y Recordatorios.
- 🐛 Revisar `iicio.txt` (archivo huérfano) y borrarlo.

## Cómo trabajar

- Arrancar: `uvicorn main:app --reload --host 127.0.0.1 --port 8000`
- Probar: `http://127.0.0.1:8000/ingresos`, `/egresos`, `/recordatorios`
- Probar parser de Recordatorios:
  `python probar_parser.py archivo.xlsx`
- La BD está en `vetsuite.db` (no va a git)
- Los archivos de `uploads/` no van a git
- `gmail_config.json`, `egresos_config.json`, `recordatorios_config.json`,
  `catalogo_qvet.json`, `categorias_manuales.json`,
  `proveedores_sucursal.json`, `solicitud_sat_activa.json` y
  `jobs_state.json` NO van a git
- Si se corrompen los archivos de Ingresos: `python reparar_archivos.py`
- Si hay basura en `uploads/facturas/`: `python limpiar_facturas.py`

## Reglas

1. **El PDF es la fuente de productos en Ingresos** (XML = solo cabecera).
2. **El XML es la fuente de todo en Egresos** (no hay PDF).
3. **Los archivos de Ingresos se guardan como `<folio>.xml|.pdf`**.
4. **Los archivos de Egresos se guardan como `<serie>-<folio>.xml`**.
5. **Sucursal de Ingresos por serie**: `S1` → Baalak, `Prados` → Prado.
6. **Sucursal de Egresos por RFC del proveedor** (en
   `proveedores_sucursal.json`, default Baalak).
7. **Sucursal de Recordatorios por `recordatorios_config.json`**
   (`BAALAK_CENTRAL`, `BAALAK_PRADO`, `ANIMALIA`).
8. **`datos_json` guarda todos los campos del Excel de Ingresos**.
9. **El ZIP mensual incluye el Excel** con la estructura de escritorio.
10. **El historial del SAT se guarda siempre** (si
    `guardar_historial_sat: true` en `egresos_config.json`).
11. **El token del SAT expira en 5 min**: obtener uno fresco por paquete.
12. **El SAT devuelve el ZIP en `paquete_b64`**, no en `paquete`.
13. **Reset borra TODO lo del módulo** pero NO lo global.
14. **`base.html` expone `{% block head %}` y `{% block scripts %}`**
    para que cada página cargue su CSS/JS.
15. **Recordatorios persiste en JSON + `localStorage`** (tab y scroll).
16. **Los archivos listados en la sección "Cómo trabajar" NO van a git**.

## Pendientes (deuda técnica)

- [ ] Tests automáticos del parser de Recordatorios.
- [ ] Tests automáticos del pipeline de Ingresos y Egresos.
- [ ] Documentación de instalación en Windows 11.
- [ ] Arranque automático con el sistema (tarea programada).
- [ ] Endpoint `/egresos/zip` con filtro por rango de fechas (ahora
      solo por mes).
- [ ] Rotación de snapshots del SAT (borrar los de más de 6 meses).
- [ ] Manejo de XMLs de tipo E (notas de crédito) y P (complementos
      de pago) si el usuario los necesita.