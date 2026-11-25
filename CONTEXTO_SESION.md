# Sesión de trabajo — 2026-11-19/20 (VetSuite Web v0.9.x — Recordatorios: pestaña Libres)

## Resumen

Se agregó a Recordatorios una pestaña **"Libres"** para enviar mensajes
con plantillas editables (estilo Meta/WhatsApp Business). La pestaña es
idéntica en UX a Citas / Vacunas / Convenios: tabla, selección por clic,
botón Enviar global, doble clic para ver el mensaje.

Se completó:
- Tabla `plantillas_libres` en `shared/db.py` (soft-delete).
- `core/recordatorios/plantillas.py` — CRUD + `renderizar()`.
- `core/recordatorios/clientes_libres.py` — cache JSON.
- `core/recordatorios/parser_clientes_libres.py` — parser de Excel.
- `core/rutas_recordatorios.py` → `LIBRES_CLIENTES_CACHE`.
- `routers/recordatorios.py` → endpoints unificados (`whatsapp`,
  `marcar`, `desmarcar` aceptan `tipo=libres`), `index()` con
  `libres_rich`, exportación Excel con 4 hojas.
- `templates/recordatorios.html` → pestaña Libres, modal de plantillas,
  botón "Gestionar plantillas" contextual, Reset movido a la barra,
  badge de plantilla activa con `text-white`.

## Decisiones de diseño

- Persistencia:
  - Clientes libres → JSON (`uploads/recordatorios/libres_clientes.json`).
  - Plantillas → SQLite (`plantillas_libres`), porque es CRUD con `id`.
  - Historial → JSON compartido con citas/vacunas/convenios (`tipo="libres"`).
- Endpoints genéricos: `whatsapp`, `marcar`, `desmarcar` aceptan
  `tipo=libres`, sin duplicar rutas.
- El "enviado" se marca por **mensaje exacto** (`tel|tipo|hash(mensaje)`),
  así el usuario puede enviar distintas plantillas al mismo cliente.
- La plantilla activa vive en `localStorage` y se pasa por query param
  `?plantilla_libres=<id>` al `index`.
- Reset **no** borra plantillas.
- UI: la pestaña Libres es idéntica a las otras (tabla, selección por
  clic, botón Enviar global, doble clic para ver mensaje).

## Archivos nuevos

- `core/recordatorios/plantillas.py`
- `core/recordatorios/clientes_libres.py`
- `core/recordatorios/parser_clientes_libres.py`

## Archivos modificados

- `shared/db.py` → `CREATE TABLE plantillas_libres`
- `core/rutas_recordatorios.py` → `LIBRES_CLIENTES_CACHE`
- `routers/recordatorios.py` → endpoints unificados, `index()` con
  `libres_rich`, exportación Excel con 4 hojas (Citas, Vacunas,
  Convenios, Libres)
- `templates/recordatorios.html` → pestaña Libres, modal de plantillas,
  botón "Gestionar plantillas" contextual, Reset movido a la barra,
  badge de plantilla activa con `text-white`

## Inconsistencias resueltas

- Libres contaba como enviado con cualquier plantilla → ahora por mensaje
  exacto.
- Reset borraba plantillas (contradecía el mensaje del `confirm`) → ahora
  no.
- Badge de plantilla activa tenía texto oscuro sobre fondo azul → se
  agregó `text-white`.
- `formImport.addEventListener` duplicado → unificado.
- `STATS` vs `STATS_TAB` inconsistente → renombrado a `STATS_TAB`.
- `_telefonos_enviados_por_tipo` se usaba para la tabla → ahora solo para
  el Excel (resumen histórico).
- `index()` consultaba el historial dentro del loop de clientes → ahora
  una sola lectura.

## Estado actual

### Funcional
- ✅ Pestaña Libres con plantillas editables.
- ✅ Reset conserva plantillas.
- ✅ Exportar Excel con 4 hojas.
- ✅ Todos los módulos anteriores siguen funcionando.

### Pendiente (Libres)
- 📝 Tests del CRUD de plantillas.
- 📝 Tests del parser de clientes.
- 📝 Sincronizar plantilla activa entre pestañas del navegador.

## Cómo trabajar

- Arrancar: `uvicorn main:app --reload --host 127.0.0.1 --port 8000`
- Probar: `http://127.0.0.1:8000/recordatorios` → tab Libres.
- Importar Excel de clientes: botón "Importar listas" en la barra.
- Crear/editar plantillas: "Más" o "Gestionar plantillas" (solo en Libres).
- Enviar: seleccionar cliente en la tabla → botón "Enviar".

## Reglas nuevas (Recordatorios / Libres)

93. v0.9.x: la pestaña Libres usa plantillas de la tabla
    `plantillas_libres` (SQLite). El Reset **no** las borra.
94. v0.9.x: el "enviado" de Libres se marca por `hash(mensaje)`. Cambiar
    de plantilla desmarca a los clientes ya enviados con otra.
95. v0.9.x: la plantilla activa de Libres vive en `localStorage`
    (`vetsuite.recordatorios.plantilla_libres`) y se pasa al backend por
    `?plantilla_libres=<id>`.
96. v0.9.x: `whatsapp`, `marcar` y `desmarcar` son genéricos
    (`{tipo}` = `citas|vacunas|libres`). No hay endpoints duplicados.
97. v0.9.x: el parser de Excel de clientes libres
    (`parsear_excel_clientes`) acepta columnas de teléfono con prefijos
    (`TELÉFONO1`, `TELÉFONO SMS`, etc.) y normaliza formatos sucios.
98. v0.9.x: el Excel de Recordatorios tiene 4 hojas: Citas, Vacunas,
    Convenios, Libres.
99. v0.9.x: el botón "Gestionar plantillas" solo es visible en la
    pestaña Libres.
100. v0.9.x: el badge de plantilla activa usa `bg-primary text-white`.
118. v0.10.x: Los estilos de Cuentas por Cobrar viven en
     static/style.css (sección "Cuentas por Cobrar"). El template
     no lleva <style> inline salvo casos muy puntuales (ej. un
     ancho específico de un modal que no se reusa). Los chips,
     semáforos y filas atenuadas son reutilizables: si otro módulo
     los necesita, se reusan las mismas clases.
119. v0.10.x: El cruce CPC ↔ Convenios es por nombre normalizado
     (mayúsculas, sin acentos, sin puntos, colapsando espacios).
     Los estados activos son 'firmado' e 'impreso'.
120. v0.10.x: Los clientes institucionales no se cruzan con convenios.
121. v0.10.x: Si un cliente tenía convenio activo y se cancela, el
     siguiente cruce lo desmarca y regresa el estado a 'pendiente'
     (solo si el estado actual era 'convenio').
122. v0.10.x: El cruce corre automáticamente al final de /importar y
     manualmente con el botón "Reverificar convenios".
123. v0.10.x: Las transiciones de estado de convenios son:
     - borrador  → impreso, cancelado
     - impreso   → firmado, borrador, cancelado
     - firmado   → pagado, cancelado
     - pagado    → (terminal, no permite cambios)
     - cancelado → (terminal, no permite cambios)
124. v0.10.x: No se puede pasar a 'pagado' si hay pagos pendientes
     (validado en backend, 409).
125. v0.10.x: Los estados 'pagado' y 'cancelado' son terminales: no
     permiten transición a otro estado. Si se intenta, el backend
     devuelve 409.
126. v0.10.x: El endpoint /convenios/{cid}/estado valida las
     transiciones con `_validar_transicion()` y devuelve 409 con
     mensaje descriptivo si la transición no es válida.
127. v0.10.x: El selector de estado en el formulario deshabilita las
     opciones no permitidas según el estado actual. Si el usuario
     cancela el confirm, el select revierte al estado anterior.
128. v0.10.x: En Jinja2, una variable solo existe dentro del `{% for %}`
     que la define. Si ves `{{ a.id }}` fuera de un `{% for a in ... %}`,
     es un bug. El listado de convenios tuvo ese bug en la barra de
     herramientas (línea 58) y se corrigió moviendo los botones
     individuales al loop del header o eliminándolos.
129. v0.10.x: Los badges con `bg-primary`, `bg-danger`, `bg-success` y
     `bg-warning` en Tabler requieren `text-white` explícito para que
     el texto se vea (excepto `bg-warning`, que necesita
     `text-dark`). Sin esto, el texto hereda el color oscuro por
     defecto y no se lee sobre el fondo de color.
130. v0.10.x: Un cliente de Cuentas por Cobrar puede ser "institucional"
     (lo lleva administración) o "convenio" (tiene un convenio de pago
     activo), pero NO ambos. Al marcar institucional se limpia el
     convenio, y al marcar convenio se limpia el institucional.
131. v0.10.x: Solo admin puede marcar/desmarcar institucional. En la
     UI actual el botón está visible para todos; se ocultará a
     recepción cuando implementemos permisos por rol (Bloque 5).
132. v0.10.x: Al marcar institucional, el estado pasa a 'institucional'.
     Al desmarcar, pasa a 'pendiente' y se re-cruza contra convenios.
133. v0.10.x: Un cliente institucional no puede cambiar de estado a
     otro que no sea 'institucional' (excepto desmarcándolo primero).
134. v0.10.x: Los cambios de institucional se registran en bitácora
     con tipo='otro', resultado='institucional', observaciones
     descriptivas.
135. v0.10.x: El listado de Cuentas por Cobrar NO muestra clientes
     institucionales por defecto. Hay un checkbox "Ver institucionales"
     que los incluye (solo visible para admin en el futuro).
136. v0.10.x: El `_upsert_cliente` de Cuentas por Cobrar NO pisa
     `es_institucional` ni `es_convenio` en el UPDATE. Solo los
     establece en el INSERT (clientes nuevos). Las decisiones
     manuales del admin y el cruce con convenios se respetan en
     cada reimportación.
137. v0.10.x: Si un cliente tiene `estado = 'institucional'` pero
     `es_institucional = 0` (estado inconsistente por un bug
     anterior), el script de sincronización lo corrige con:
     UPDATE cpc_clientes SET es_institucional = 1
     WHERE estado = 'institucional' AND es_institucional = 0.
138. v0.10.x: El bloque de "saldo 0 → pagado" excluye
     `es_institucional = 1` y los estados `pagado`, `cancelado`,
     `convenio`, `disputa`, `institucional`.
139. v0.10.x: El endpoint `/datos` de Cuentas por Cobrar NO filtra
     `es_convenio` por defecto. Los convenios se ven en el listado
     (atenuados). El filtro se activará con permisos por rol
     (Bloque 5).
140. v0.10.x: Los badges con fondo de color (`bg-primary`, etc.)
     requieren `text-white` explícito en el template para que el
     texto se lea. Aplica a Cuentas por Cobrar y a cualquier otro
     módulo que use Tabler.
141. v0.10.x: Cuando se implementen las categorías adicionales
     (colaborador), migrar de `es_institucional` (booleano) a
     `categoria` (texto: normal | institucional | colaborador |
     convenio). Por ahora el booleano + `es_convenio` cubren el caso.
142. v0.10.x: El módulo de Cuentas por Cobrar tiene WhatsApp integrado
     con plantillas configurables en `cuentas_por_cobrar_config.json`.
     Las plantillas disponibles son: recordatorio_amable, recordatorio_firme,
     recordatorio_multi, promesa_seguimiento, convenio_notificacion.
143. v0.10.x: Los placeholders de las plantillas son: {cliente},
     {saldo}, {mascota}, {dias}, {n_albaranes}, {promesa_fecha},
     {promesa_monto}.
144. v0.10.x: La plantilla activa vive en localStorage
     (`vetsuite.cpc.plantilla_activa`) y en el config server-side.
     Al cambiarla en el dropdown, se actualiza en ambos.
145. v0.10.x: Al enviar un WhatsApp, se registra automáticamente una
     entrada en bitácora con tipo='whatsapp' y resultado='' (vacío).
     El usuario completa el resultado después.
146. v0.10.x: El botón "Enviar WhatsApp" se deshabilita si el cliente
     es institucional, tiene convenio activo, o no tiene teléfono.
147. v0.10.x: La URL de WhatsApp se construye con `normalizar_telefono`
     y se agrega el prefijo `52` si son 10 dígitos sin lada.

# Sesión de trabajo — 2026-11-17 (VetSuite Web v0.9.x — deuda técnica del refactor)

## Resumen

Sesión de **cierre de la deuda técnica del refactor de estructura**
(2026-11-08). Se completaron los dos pendientes que quedaban:

1. **Blindar `Path(__file__)`** — todos los `Path(__file__)` del proyecto
   (fuera de `shared/rutas.py` y de `scripts/`) fueron reemplazados por
   constantes de `shared.rutas`.
2. **Consolidar la config de Egresos** — `egresos/config_egresos.py` y
   `egresos/sat_wrapper.py` leían **archivos distintos**
   (`config_egresos.json` fantasma vs `egresos_config.json` real) y
   duplicaban lógica. Ahora hay una sola fuente de verdad.

Sin cambios de funcionalidad. Solo mantenibilidad.

Se completó:
- `Path(__file__)` reemplazados en 9 archivos del proyecto.
- Constantes nuevas en `shared/rutas.py`: `CORTE_SEMANAL_DIR`,
  `EGRESOS_DIR`, `EGRESOS_CONTABILIDAD_DIR`, `SAT_HISTORIAL_DIR`.
- `CONFIG_EGRESOS` en `shared.rutas` quedó como **alias** de
  `EGRESOS_CONFIG` (compatibilidad hacia atrás).
- `sat_wrapper.py` ya no reimplementa `cargar_config`,
  `cargar_solicitud_activa`, `cargar_proveedores_sucursal`, etc.;
  ahora importa de `config_egresos.py`.
- Nuevo helper `get_fiel()` en `config_egresos.py` que devuelve
  `{rfc, cer, key, pwd}` listo para `sat.descarga`.
- `core/sat_historial.py` ahora usa `historial_sat_activo()` de
  `config_egresos.py` (respeta también la env var `VET_SUITE_HISTORIAL=1`).

## Qué se hizo

### 1. `shared/rutas.py` — constantes nuevas

Al final del archivo:

    # --- Corte Semanal ---
    CORTE_SEMANAL_DIR         = UPLOADS_DIR / "corte_semanal"

    # --- Egresos (carpetas) ---
    EGRESOS_DIR               = UPLOADS_DIR / "egresos"
    EGRESOS_CONTABILIDAD_DIR  = EGRESOS_DIR / "contabilidad"
    SAT_HISTORIAL_DIR         = EGRESOS_DIR / "_sat_historial"

Y en la sección "Egresos":

    CONFIG_EGRESOS = EGRESOS_CONFIG   # alias histórico

### 2. Reemplazos de `Path(__file__)` (9 archivos)

| Archivo | Antes | Después |
|---|---|---|
| `main.py` | `BASE = Path(__file__).parent` | `from shared.rutas import ROOT as BASE` |
| `routers/egresos.py` | `BASE_DIR = Path(__file__).parent.parent` | `from shared.rutas import ROOT as BASE_DIR` |
| `routers/corte_semanal.py` | `RUTA_CORTES = Path(__file__)...` | `from shared.rutas import CORTE_SEMANAL_DIR as RUTA_CORTES` |
| `routers/rechazados.py` | `BASE_DIR = Path(__file__).parent.parent` | `from shared.rutas import ROOT as BASE_DIR` |
| `core/rutas_recordatorios.py` | `BASE_DIR = Path(__file__)...` | `from shared.rutas import ROOT as BASE_DIR` |
| `core/sat_historial.py` | `HISTORIAL_DIR = ...` | `from shared.rutas import SAT_HISTORIAL_DIR as HISTORIAL_DIR` |
| `core/corte_semanal/excel_corte.py` | `parents[2] / "uploads"...` | `from shared.rutas import ROOT` |
| `core/rutas_egresos.py` | `BASE_DIR = Path(__file__)...` | `from shared.rutas import EGRESOS_CONTABILIDAD_DIR, EGRESOS_DIR` |
| `egresos/manager.py` | `BASE_DIR = Path(__file__).parent.parent` | `from shared.rutas import ROOT as BASE_DIR` |
| `sat/procesar_xml.py` | `_raiz = Path(__file__).parent.parent` | `from shared.rutas import ROOT as _raiz` |

**Excepción:** los `scripts/limpiar_facturas.py` y
`scripts/reparar_archivos.py` conservan su `Path(__file__)` porque es
bootstrap de `sys.path` (para que el script corra desde cualquier cwd),
no una ruta de datos.

### 3. `egresos/config_egresos.py` — única fuente de config

- Importa `EGRESOS_CONFIG` (el archivo real), no `CONFIG_EGRESOS`.
- `CONFIG_EGRESOS_DEFAULT` incluye `guardar_historial_sat`.
- Nuevo helper `get_fiel()`.

### 4. `egresos/sat_wrapper.py` — sin duplicados

- **Eliminadas:** `cargar_config`, `guardar_config`,
  `cargar_solicitud_activa`, `guardar_solicitud_activa`,
  `limpiar_solicitud_activa`, `cargar_proveedores_sucursal`,
  `guardar_proveedores_sucursal` (todas viven ahora en
  `config_egresos.py`).
- **Importadas** desde `egresos.config_egresos` con alias para no romper
  a los consumidores (`cargar_config = cargar_config_egresos`, etc.).
- **Conserva:** `probar_fiel`, `solicitar_descarga`,
  `verificar_solicitud`, `descargar_paquetes`, `procesar_xmls`,
  `guardar_facturas_egresos`, `marcar_animalia`.
- Reexporta `get_fiel` desde `config_egresos`.

### 5. `core/sat_historial.py` — usa el helper correcto

- `_historial_activo()` ahora llama a
  `config_egresos.historial_sat_activo()` (respeta env var
  `VET_SUITE_HISTORIAL=1` + `guardar_historial_sat` del JSON).

## Bugs latentes resueltos

- **Dos configs distintas:** `config_egresos.py` leía
  `json/config_egresos.json` (que probablemente no existía) y
  `sat_wrapper.py` leía `json/egresos_config.json` (el real). Si el
  usuario guardaba la FIEL desde un endpoint que usaba `config_egresos`,
  `sat_wrapper` no la veía. Fix: un solo archivo (`egresos_config.json`)
  y una sola implementación (`config_egresos.py`).
- **`favicon()` en `main.py`** dependía del cwd (`Path("static/favicon.ico")`).
  Fix: `BASE / "static" / "favicon.ico"` con `BASE` de `shared.rutas`.
- **`sat_historial` no respetaba `VET_SUITE_HISTORIAL`.** Fix: usa
  `historial_sat_activo()` que sí lo respeta.

## Estado actual

### Funcional
- ✅ Todos los módulos funcionan igual (sin cambios de comportamiento).
- ✅ Todos los `Path(__file__)` de datos centralizados en
  `shared/rutas.py`.
- ✅ Una sola fuente de verdad para la config de Egresos.
- ✅ `historial_sat_activo()` respeta la env var.

### Pendiente (deuda técnica)
- Limpiar imports huérfanos en `sat_wrapper.py` (`datetime` ya no se usa
  a nivel módulo). Cosmético.

### Pendiente (global, arrastrado)
- 🧪 Tests automáticos (el más grande).
- ⏰ Arranque automático en macOS (ya con `launchd`).

## Cómo trabajar

- Arrancar: `uvicorn main:app --reload --host 127.0.0.1 --port 8000`
- Verificar imports: `python -c "import main"`
- Verificar constantes: `python -c "from shared.rutas import *"`
- Verificar que no quedan `Path(__file__)` de datos:
  `grep -rn "Path(__file__)" --include="*.py" . | grep -v "__pycache__" | grep -v "venv/" | grep -v "scripts/"`
  (solo debe salir `shared/rutas.py`)
- Probar `/egresos` (config FIEL + probar FIEL + descarga) para validar
  que `sat_wrapper` sigue funcionando con los imports consolidados.

## Reglas nuevas (deuda técnica resuelta)

1. Todo `Path(__file__)` de datos vive en `shared/rutas.py`. El resto del
   código importa constantes.
2. Los `scripts/*.py` conservan su `Path(__file__)` de bootstrap de
   `sys.path`.
3. `json/egresos_config.json` es el **único** archivo de config de
   Egresos. `CONFIG_EGRESOS` en `shared.rutas` es un alias de
   `EGRESOS_CONFIG` por compatibilidad.
4. `egresos/config_egresos.py` es la **única** fuente de config de
   Egresos. `sat_wrapper.py` no lee JSON; importa de ahí.
5. `sat_wrapper.py` reexporta `cargar_config`, `guardar_config`,
   `cargar_solicitud_activa`, etc. con alias para no romper a los
   consumidores. Si en el futuro se migran los imports, se pueden
   eliminar los alias.
6. `core/sat_historial.py` usa `config_egresos.historial_sat_activo()`,
   que respeta `VET_SUITE_HISTORIAL=1` + `guardar_historial_sat`.

# Sesión de trabajo — 2026-11-17 (VetSuite Web v0.9.x — cierre de Convenios: reportes con árbol)

## Resumen

Se completó el último pendiente del módulo **Convenios de Pago**: el
modal de reportes con árbol jerárquico `Año → Mes → Estado`. Con esto el
módulo queda cerrado al 100% y visualmente consistente con Ingresos,
Egresos, Corte Semanal y Servicios Externos.

Se completó:
- Endpoint `GET /convenios/arbol` (árbol Año → Mes → Estado con `_total`
  en cada nivel, incluida la raíz).
- Botón "Ver registros" en la barra de herramientas de `/convenios`.
- `<dialog id="modal-reportes">` con árbol Año → Mes → Estado.
- Clic en estado: navega a `/convenios?estado=&desde=&hasta=&q=`
  respetando los filtros híbridos ya implementados.

## Qué se hizo

### 1. Backend — `routers/convenios.py`

- Endpoint `GET /convenios/arbol`.
- Agrupa por `fecha[:4]` (año) y `fecha[5:7]` (mes) y `estado`.
- Calcula `n` y `total` (suma de `monto_total`) por estado.
- `_total` en tres niveles: estado → mes → año → raíz.
- Header `Cache-Control: no-store`.
- El `_total` raíz es obligatorio (regla 21 de CONTEXTO.md): sin él, el
  footer del modal sale en 0.

### 2. Frontend — `templates/convenios.html`

- Botón "Ver registros" (icono Tabler `ti-list`) junto a "Exportar Excel".
- `<dialog id="modal-reportes">` con:
  - Header con título y botón ✕.
  - Body con `<div id="arbol-reportes">`.
  - Footer con `<span id="arbol-resumen">` para el total general.
- JS del árbol:
  - `abrirModalReportes()` — fetch a `/convenios/arbol`, renderiza.
  - `nodoAnioConv()` — `<details>` expandible, muestra `_total` del año.
  - `nodoMesConv()` — `<details>` expandible, muestra `_total` del mes
    e itera sobre los 5 estados posibles.
  - `nodoEstadoConv()` — botón hoja; clic navega a `/convenios` con
    `estado`, `desde` (primer día del mes) y `hasta` (último día del
    mes) como query params.
- `window.abrirModalReportes = abrirModalReportes` al final (regla 15
  de Servicios Externos).
- Helper `fmtMonto` agregado al `<script>` (no existía en
  `convenios.html`).

### 3. Estilos

- No se tocó `static/style.css`. Se reutilizan las clases existentes
  `.arbol-reportes`, `.nodo-sucursal-btn` y `.nodo-hoja` de Egresos y
  Servicios Externos.

## Bugs resueltos en esta sesión

- **Ninguno.** Todo se implementó siguiendo el patrón de
  `servicios_externos` y no hubo incidentes.

## Estado actual

### Funcional
- ✅ Módulo **Convenios de Pago completo al 100%** (captura, pagos,
  impresión, alertas, bloqueo, eliminación, filtros, Excel, UUID,
  recordatorios automáticos, **reportes con árbol**).
- ✅ Todos los módulos anteriores siguen funcionando.

### Pendiente (Convenios)
- Ninguno.

### Pendiente (global, arrastrado)
- 🧪 Tests automáticos (el más grande, requiere sesión dedicada).
- ⏰ Arranque automático con el sistema en macOS (ya implementado por
  el usuario con `launchd`).

## Cómo trabajar

- Arrancar: `uvicorn main:app --reload --host 127.0.0.1 --port 8000`
- Probar árbol de Convenios: `http://127.0.0.1:8000/convenios` →
  botón "Ver registros".
- Endpoint directo: `http://127.0.0.1:8000/convenios/arbol` (debe
  devolver JSON con `_total` en cada nivel, incluida la raíz).

## Reglas nuevas (Convenios / Reportes)

1. El árbol de Convenios tiene tres niveles: **Año → Mes → Estado**.
2. Los estados visibles son los mismos que el `<select>` del listado:
   `borrador`, `impreso`, `firmado`, `pagado`, `cancelado`.
3. `_total` debe existir en los cuatro niveles (estado, mes, año,
   raíz). Sin el de raíz, el footer sale en 0.
4. Clic en estado navega a `/convenios?estado=&desde=&hasta=&q=`
   con `desde = primer día del mes` y `hasta = último día del mes`.
5. El endpoint manda `Cache-Control: no-store`.
6. Los estilos del árbol se reutilizan de Egresos / Servicios Externos
   (`.arbol-reportes`, `.nodo-sucursal-btn`, `.nodo-hoja`).
7. `window.abrirModalReportes = abrirModalReportes` al final del
   `<script>` (mismo patrón que Servicios Externos).

# Sesión de trabajo — 2026-11-16 (VetSuite Web v0.9.x — cierre de Convenios)

## Resumen

Sesión de cierre del módulo **Convenios de Pago**. Se completaron los
pendientes que quedaban de la sesión anterior: filtros híbridos en el
listado, exportar a Excel, UUID de factura desde Ingresos, eliminación
condicionada desde el formulario, botones Regenerar/Descartar en la
pestaña Convenios de Recordatorios, y limpieza de pendientes globales.

Se completó:
- Filtros híbridos en `/convenios` (estado/fechas server-side, texto
  client-side).
- Endpoint `GET /convenios/excel` con dos hojas (Convenios y Pagos).
- UUID de factura automático desde `ingresos.folio_fiscal`.
- Botón Eliminar dentro del formulario, condicionado a borrador sin
  pagos efectuados.
- Botones Regenerar/Descartar en la pestaña Convenios de Recordatorios.
- Limpieza de pendientes: `print()` de `sat/descarga.py` no aplica
  (son avisos, no debug); `iicio.txt` borrado.

## Qué se hizo

### 1. Filtros híbridos en el listado

- `listado()` acepta query params `estado`, `desde`, `hasta`, `q`.
- `estado`, `desde`, `hasta` se aplican en SQL (server-side).
- `q` se aplica en el cliente con debounce 150ms sobre las filas ya
  cargadas.
- El `q` viaja en la URL como hidden para preservarse al cambiar los
  filtros server-side.
- La URL es compartible.

### 2. Exportar a Excel

- Endpoint `GET /convenios/excel?estado=&desde=&hasta=&q=`.
- Respeta los mismos filtros que el listado.
- Dos hojas:
  - "Convenios": folio, fecha, propietario, teléfono, mascota, NHC,
    monto total, pagado, pendiente, vencimiento, estado, lugar de pago,
    notas.
  - "Pagos": folio del convenio, propietario, # pago, fecha, importe,
    efectuado, fecha de pago, albarán, factura, UUID, tipo de pago.
- Formato de moneda, encabezados azules, primera fila congelada,
  anchos de columna predefinidos.
- Nombre: `Convenios_YYYY-MM-DD_HHMM.xlsx`.

### 3. UUID de factura

- `buscar_ingreso_por_cliente()` devuelve `folio_fiscal` del ingreso.
- El JS de `buscarFacturaFila(tr)` llena el hidden `.pago-factura-uuid`
  con `ing.folio_fiscal`.
- Se guarda en `convenios_pagos.factura_uuid`.
- Se muestra como texto pequeño debajo del número de factura.
- Se exporta en la hoja "Pagos" del Excel.

### 4. Eliminar convenio desde el formulario

- El botón 🗑 se movió del listado al formulario.
- Solo aparece si `conv.estado == 'borrador'` y `not tiene_efectuados`.
- Pide confirmación con `confirm()`.
- Llama a `POST /convenios/{cid}/eliminar` y redirige al listado.
- El listado ya no tiene botón eliminar; la eliminación es exclusiva
  del formulario.

### 5. Botones Regenerar/Descartar en pestaña Convenios

- "Regenerar" llama a `POST /recordatorios/convenios/regenerar` y
  muestra un alert con el resultado.
- "Descartar" llama a `POST /recordatorios/convenios/descartar/{idx}`
  del item seleccionado. Solo se habilita si el item no está enviado.
- Ambos botones solo son visibles en la pestaña Convenios de
  Recordatorios. Se ocultan (junto con el separador) al cambiar a
  Citas o Vacunas.

### 6. Limpieza de pendientes

- Los `print()` de `sat/descarga.py` son avisos de progreso y errores,
  no debug. No se borran.
- `iicio.txt` ya no existía; se eliminó la línea de pendientes del
  contexto.

## Bugs resueltos en esta sesión

- **`factura_uuid` no se llenaba**: `buscar_ingreso_por_cliente()` no
  devolvía `folio_fiscal`. Fix: agregar `folio_fiscal` al SELECT y al
  dict de retorno.
- **Múltiples `DOMContentLoaded`**: se aclaró que son válidos y se
  acumulan. No se reemplazan entre sí.

## Estado actual

### Funcional
- ✅ Módulo Convenios de Pago completo (captura, impresión, alertas,
  bloqueo, eliminación, filtros, Excel, UUID).
- ✅ Recordatorios de convenios (job diario 08:00 + pestaña Convenios
  con botones Regenerar/Descartar).
- ✅ Todos los módulos anteriores siguen funcionando.

### Pendiente (Convenios)
- 📝 Reportes con árbol (Año → Mes → Estado) — opcional, consistencia
  visual con los demás módulos.

### Pendiente (global, arrastrado)
- 🧪 Tests automáticos (el más grande, requiere sesión dedicada).
- ⏰ Arranque automático con el sistema en macOS (ya implementado por
  el usuario con `launchd`).

## Cómo trabajar

- Arrancar: `uvicorn main:app --reload --host 127.0.0.1 --port 8000`
- Probar Convenios: `http://127.0.0.1:8000/convenios`
- Probar Recordatorios: `http://127.0.0.1:8000/recordatorios`
- Exportar Excel: clic en "Exportar Excel" en `/convenios` (respeta
  filtros).
- Forzar generación de recordatorios sin esperar al job:
  `curl -X POST http://127.0.0.1:8000/recordatorios/convenios/regenerar`

## Reglas nuevas (cierre de Convenios)

1. Filtros híbridos: estado/fechas server-side, texto client-side con
   debounce. El `q` viaja en la URL como hidden.
2. El Excel de convenios respeta los mismos filtros que el listado.
3. El UUID de factura se llena desde `ingresos.folio_fiscal` al buscar
   la factura del cliente.
4. El botón eliminar vive dentro del formulario, no en el listado.
5. Los botones Regenerar/Descartar solo son visibles en la pestaña
   Convenios de Recordatorios.
6. Los `print()` de `sat/descarga.py` son avisos de progreso, no debug.
7. Múltiples `DOMContentLoaded` en el mismo `<script>` se acumulan, no
   se reemplazan.

# Sesión de trabajo — 2026-11-15 (VetSuite Web v0.9.x — recordatorios automáticos de convenios)

## Resumen

Se cerró el ciclo del módulo **Convenios de Pago** integrando la
generación automática de recordatorios por WhatsApp. Un thread daemon
corre una vez al día a la hora configurada, revisa los convenios
vencidos o por vencer con saldo pendiente, y deja los mensajes listos
en una tercera pestaña "Convenios" del módulo de Recordatorios.

Se completó:
- `core/recordatorios/convenios_cache.py` — carga/guardado del JSON.
- `core/recordatorios/convenios_generator.py` — lógica de generación.
- `shared/jobs_convenios.py` — thread daemon con scheduler diario.
- `main.py` — arranque del thread al inicio de la app.
- `routers/recordatorios.py` — 5 endpoints nuevos + carga en `index()`.
- `templates/recordatorios.html` — tercera pestaña "Convenios".
- `json/convenios_config.json` — sección `recordatorios`.
- `core/rutas_recordatorios.py` — `CONVENIOS_CACHE`.

## Qué se hizo

### 1. Generación de mensajes (`convenios_generator.py`)

- Recorre convenios con `estado NOT IN ('pagado', 'cancelado')` y
  `fecha_vencimiento != ''`.
- Calcula saldo pendiente (`monto_total - suma pagos efectuados`).
- Calcula `dias = fecha_vencimiento - hoy`:
  - `< 0` → vencido.
  - `0..dias_por_vencer` → por vencer.
  - `> dias_por_vencer` → no genera.
- Genera mensaje y lo inserta con `id = conv-<cid>-<YYYY-MM-DD>`.
- Devuelve `{nuevos, omitidos, total}`.

### 2. Job diario (`shared/jobs_convenios.py`)

- Thread daemon, arranca con `iniciar()` desde `main.py`.
- Lee `json/convenios_config.json` → `recordatorios` cada ciclo.
- Duerme hasta la próxima hora configurada.
- Al arrancar, si ya pasó la hora y no se ejecutó hoy, corre de
  inmediato.
- No usa `shared/jobs.py` (ese es para jobs manuales con progreso).

### 3. Endpoints en `routers/recordatorios.py`

- `GET /recordatorios/convenios/whatsapp/{idx}` — URL + mensaje.
- `POST /recordatorios/convenios/marcar/{idx}` — marca enviado.
- `POST /recordatorios/convenios/desmarcar/{idx}` — desmarca.
- `POST /recordatorios/convenios/descartar/{idx}` — descarta (no se
  regenera hoy).
- `POST /recordatorios/convenios/regenerar` — fuerza la generación.

El `index()` carga `convenios_importada.json`, filtra descartados,
enriquece con `enviado` (consultando `historial.ya_fue_enviado`) y
pasa `convenios_rich` al template.

### 4. Frontend (`recordatorios.html`)

- Tercera pestaña "Convenios" con contador.
- Tabla con: ✔ | Cliente | Teléfono | Mascota | Folio | Saldo | Vencimiento | Días | Tipo.
- Mismos handlers que Citas/Vacunas: clic en fila selecciona, doble clic
  muestra mensaje, botón único Enviar/Desmarcar funciona genérico.
- Persistencia de tab activo extendida a `convenios`.

### 5. Configuración (`convenios_config.json`)

    {
      "recordatorios": {
        "activo": true,
        "hora": "08:00",
        "dias_por_vencer": 3
      }
    }

## Bugs resueltos en esta sesión

- **Ninguno.** Todo se implementó sin bugs. Los puntos frágiles fueron:
  - El nombre exacto de `CONVENIOS_CONFIG` en `shared/rutas.py`.
  - El nombre exacto de `UPLOADS_DIR` en `rutas_recordatorios.py`.
  - El JS del tab activo en `recordatorios.html` (se generalizó con
    `data-bs-target` para no hardcodear `vacunas` vs `convenios`).

## Estado actual

### Funcional
- ✅ Job diario de recordatorios de convenios.
- ✅ Tercera pestaña "Convenios" en Recordatorios.
- ✅ Envío por WhatsApp con el mismo flujo que Citas/Vacunas.
- ✅ Reset borra también `convenios_importada.json`.
- ✅ Todos los módulos anteriores siguen funcionando.

### Pendiente (Convenios / Recordatorios)
- 📝 Botón "Regenerar" en la pestaña Convenios (hoy solo por `curl`).
- 📝 Botón "Descartar" en cada fila (endpoint ya existe, falta UI).
- 📝 Filtros en el listado de convenios.
- 📝 Reportes con árbol en Convenios.
- 📝 Exportar a Excel los convenios.

### Pendiente (global, arrastrado)
- 🧪 Tests automáticos.
- ⏰ Arranque automático con el sistema (hoy el job corre solo si la
  app está abierta; para que corra con la app cerrada hace falta una
  tarea programada de Windows que arranque uvicorn al inicio).

## Cómo trabajar

- Arrancar: `uvicorn main:app --reload --host 127.0.0.1 --port 8000`
- Verificar que el job arrancó: buscar en consola `[convenios_job] Thread iniciado`.
- Forzar la generación sin esperar a las 08:00:
  `curl -X POST http://127.0.0.1:8000/recordatorios/convenios/regenerar`
- Probar la pestaña: `http://127.0.0.1:8000/recordatorios` → tab Convenios.
- Cambiar la hora del job: editar `json/convenios_config.json` →
  `recordatorios.hora` y reiniciar uvicorn.
- Desactivar el job temporalmente: `recordatorios.activo = false` y
  reiniciar.

## Reglas nuevas (Recordatorios / Convenios)

1. El job de recordatorios de convenios corre en un thread daemon en
   `shared/jobs_convenios.py`, separado de `shared/jobs.py`.
2. Un mensaje por convenio por día. El `id = conv-<cid>-<YYYY-MM-DD>`
   lo garantiza. Al día siguiente, si sigue vencido, se genera uno
   nuevo.
3. El job no envía nada solo. Solo prepara los mensajes. El envío es
   manual desde la pestaña Convenios.
4. El `reset` de Recordatorios borra también `convenios_importada.json`.
5. Los mensajes descartados (`descartado: true`) no se regeneran el
   mismo día. Al día siguiente sí.
6. El historial de envíos de convenios usa `historial_recordatorios.json`
   con `tipo="convenios"`. Es genérico, no requiere cambios.
7. Si la app estaba apagada a la hora configurada, el job corre al
   arrancar (si ya pasó la hora y no se generó hoy).

# Sesión de trabajo — 2026-11-14/15 (VetSuite Web v0.9.x — módulo Convenios de Pago)

## Resumen

Se implementó desde cero el módulo **Convenios de Pago** (`/convenios`).
Permite generar un convenio de pago (reconocimiento de deuda) con el
cliente, con plan de pagos dinámico, imprimirlo en formato Carta (sin
abrir pestaña nueva) y dar seguimiento a los pagos con bloqueo por
contraseña una vez que hay pagos efectuados.

Se completó:
- Tablas `convenios`, `convenios_pagos`, `convenios_alertas_vistas`.
- Módulo `core/convenios/` (`numero_a_letras.py`, `helpers.py`).
- Router `/convenios` con 12 endpoints.
- Templates `convenios.html`, `convenios_form.html`, `convenios_print.html`.
- Config `json/convenios_config.json` (datos de la clínica + contraseña).
- Permiso `"convenios"` en `ip_permisos.json`.
- Item en el sidebar con icono `ti-file-text`.
- Estilos en `static/style.css` (sección Convenios).
- Bloqueo de pagos efectuados + contraseña opcional.
- Impresión vía iframe oculto (sin pestaña visible).
- Alertas de vencimiento con celda pintada (rojo/amarillo + días).

## Qué se hizo

### 1. Modelo de datos

Tres tablas nuevas en `shared/db.py`:

- `convenios` (una fila por convenio).
- `convenios_pagos` (una fila por pago, con `albaran`, `factura_numero`,
  `factura_uuid`, `tipo_pago`, `pagado_con_tarjeta`).
- `convenios_alertas_vistas` (marca de "visto hoy" por convenio).

Migración idempotente: si `convenios_pagos` ya existe sin las columnas
nuevas, se agregan con `ALTER TABLE`.

### 2. Conversor de monto a letra (`core/convenios/numero_a_letras.py`)

- Trabaja con centavos enteros para evitar errores de punto flotante.
- `numero_a_letras(5500)` → `"CINCO MIL QUINIENTOS PESOS 00/100 M.N."`.
- `numero_a_letras(1234567.89)` → `"UN MILLÓN DOSCIENTOS TREINTA Y
  CUATRO MIL QUINIENTOS SESENTA Y SIETE PESOS 89/100 M.N."`.

### 3. Helpers (`core/convenios/helpers.py`)

- `generar_folio(conn)` — `CONV-<año>-<consecutivo 4 dígitos>`.
- `buscar_ingreso_por_cliente(conn, nombre, rfc)` — busca factura en
  `ingresos` a nombre del cliente (no público en general).
- `calcular_estado_pago(conn, cid)` — total, pagado, pendiente,
  n_pagos, n_pagados.
- `cargar_alertas_vistas()` / `marcar_alerta_vista(cid)` — set de
  convenios vistos hoy.
- `fecha_legible(iso)` — `"30 de septiembre de 2026"`.
- `password_configurada()` — lee `password_hash` de la config.
- `verificar_password(pwd)` — SHA256 del password contra el hash.
- `convenio_tiene_pagos_efectuados(conn, cid)` — bool.

### 4. Router (`routers/convenios.py`)

- `GET /convenios` — listado con alertas.
- `GET /convenios/nuevo` — formulario vacío.
- `GET /convenios/{cid}/editar` — formulario con pagos.
- `GET /convenios/{cid}/imprimir` — template Carta.
- `GET /convenios/numero-a-letras?monto=N` — letra del monto.
- `GET /convenios/buscar-cliente?q=&rfc=` — busca factura.
- `POST /convenios/guardar` — crear/actualizar con upsert de pagos.
- `POST /convenios/{cid}/estado` — cambiar estado.
- `POST /convenios/{cid}/pago/{pid}/marcar` — marcar pago.
- `POST /convenios/{cid}/eliminar` — eliminar (borrador sin pagos).
- `POST /convenios/{cid}/alerta-vista` — marcar alerta.
- `POST /convenios/verificar-password` — validar contraseña.

### 5. Frontend

- `convenios.html` — listado con bandeja de alertas, tabla con celda
  de vencimiento pintada, doble clic para editar, botón 🖨 con iframe.
- `convenios_form.html` — formulario con plan de pagos dinámico,
  búsqueda de factura por fila, modo bloqueado si hay pagos efectuados,
  botón "Desbloquear" con contraseña.
- `convenios_print.html` — formato Carta, sin IVA, con tabla de pagos,
  firmas (tutor y personal), auto-print opcional con `?auto=1`.

### 6. Impresión sin pestaña visible

`imprimirConvenio(id)` crea un `<iframe>` en el DOM con:
- `position: fixed`, `width/height: 1px`, `opacity: 0`,
  `pointer-events: none`.
- `src = /convenios/{id}/imprimir`.
- `onload` → `iframe.contentWindow.focus(); print()`.
- `afterprint` → remove el iframe.
- Fallback a `window.open(..., '_blank')` si `print()` falla.

### 7. Bloqueo de pagos efectuados

- Los pagos con `efectuado=1` se muestran como solo lectura (inputs
  disabled, sin botón 🗑).
- Si el convenio tiene al menos un pago efectuado, el formulario entra
  en modo bloqueado (todos los campos disabled, excepto los pagos
  pendientes).
- Botón "Desbloquear" pide contraseña (si `password_hash` está
  configurado).
- El backend rechaza (409) cambios estructurales (monto, fecha,
  propietario, mascota) cuando hay pagos efectuados.
- El backend rechaza (409) eliminar convenios con pagos efectuados.

## Bugs resueltos en esta sesión

- **Pagos no se guardaban al editar**: el `for i, p in enumerate(pagos, 1)`
  estaba indentado dentro del `else` (solo se ejecutaba al crear). Fix:
  moverlo fuera del `if/else` y hacer upsert por `id`.
- **`DELETE FROM convenios_pagos` al editar borraba los pagos
  efectuados**: Fix: eliminar solo los no efectuados que ya no vienen
  en el payload.
- **`TypeError: Object of type Row is not JSON serializable`** en
  `editar`: `pagos` se pasaba como `Row` al template y `tojson` tronaba.
  Fix: `pagos = [dict(p) for p in pagos_rows]`. `conv` se queda como
  `Row` porque Jinja2 necesita `.campo`.
- **`jinja2.exceptions.UndefinedError: 'c' is undefined`** en
  `convenios_form.html` línea 14: el botón de imprimir usaba `{{ c.id }}`
  pero en el formulario la variable es `conv`. Fix: `{{ conv.id }}`.
- **`{{ pagos|tojson if pagos else '[]' }}`** devolvía un string `'[]'`
  cuando no había pagos, y el JS hacía `PAGOS_INICIALES.forEach(...)`
  sobre un string. Fix: `{{ pagos|tojson }}` (el filtro `tojson` ya
  devuelve `[]` para lista vacía).
- **`numero_a_letras(1234567.89)`** daba `...SESENTA Y OCHO PESOS
  -11/100 M.N.` por error de punto flotante. Fix: trabajar con
  centavos enteros (`round(monto * 100)` y `divmod`).

## Estado actual

### Funcional
- ✅ Módulo Convenios de Pago completo.
- ✅ Folio automático, plan de pagos dinámico, monto en letra.
- ✅ Búsqueda de factura del cliente en `ingresos`.
- ✅ Impresión Carta sin pestaña visible.
- ✅ Alertas de vencimiento con celda pintada.
- ✅ Bloqueo de pagos efectuados + contraseña opcional.
- ✅ Todos los módulos anteriores siguen funcionando.

### Pendiente (Convenios)
- 📝 Generación automática de recordatorios de convenios vencidos
  (insertar en `uploads/recordatorios/` y enviar por WhatsApp).
- 📝 Job diario de vencidos (fase 2 del punto anterior).
- 📝 Filtros en el listado (estado, rango de fechas, cliente).
- 📝 Reportes con árbol (Año → Mes → Estado).
- 📝 Exportar a Excel.

### Pendiente (global, arrastrado)
- 🧪 Tests automáticos (Recordatorios, Ingresos, Egresos, Corte,
  Servicios Externos, Convenios).
- ⏰ Arranque automático con el sistema.

## Cómo trabajar

- Arrancar: `uvicorn main:app --reload --host 127.0.0.1 --port 8000`
- Probar Convenios: `http://127.0.0.1:8000/convenios`
- La config vive en `json/convenios_config.json`.
- Para activar la contraseña:
  `python -c "import hashlib; print(hashlib.sha256('TU_CONTRASEÑA'.encode()).hexdigest())"`
  y pegar el resultado en `seguridad.password_hash`.
- Si se corrompe `convenios_alertas_vistas.json`, se puede borrar sin
  problema (se regenera vacío).

## Reglas nuevas (Convenios de Pago)

72. Los convenios NO llevan IVA (servicios médicos veterinarios exentos).
73. Los pagos se guardan con upsert por `id`. Los efectuados nunca se
    modifican ni se eliminan desde el formulario.
74. El botón 🗑 del listado solo aparece si `estado == 'borrador'` y no
    hay pagos efectuados.
75. Cambios estructurales (monto, fecha, propietario, mascota) se
    bloquean si hay pagos efectuados (409).
76. La contraseña de desbloqueo es opcional (`password_hash` vacío →
    modo abierto). En producción debe estar configurada.
77. La búsqueda de factura solo vincula facturas a nombre del cliente
    (no público en general). Primero por RFC, luego por nombre.
78. `pagado_con_tarjeta` se deriva del tipo de pago (`Tarjeta *`).
79. La impresión usa iframe oculto con `print()`. Fallback a pestaña
    nueva si el navegador lo bloquea.
80. Doble clic en fila del listado abre editar. Botones de la fila
    tienen `event.stopPropagation()`.
81. La celda de vencimiento se pinta rojo (`celda-vencida`) o amarillo
    (`celda-por-vencer`) según el estado, con los días debajo.
82. El módulo `"convenios"` debe estar en `ip_permisos.json`.
83. El conversor `numero_a_letras` trabaja con centavos enteros para
    evitar errores de punto flotante.

# Sesión de trabajo — 2026-11-10 (VetSuite Web v0.9.x — pre-filtro de fechas en Gmail vía X-GM-RAW)

## Resumen

Optimización del filtro de fechas de descarga de Gmail en Ingresos. Antes
el `search` de IMAP traía **toda** la etiqueta (solo con `UNSEEN`/`FROM`/`ALL`)
y el filtro de fechas se hacía en Python sobre el header `Date:`. Eso
escala O(N etiqueta) en descarga de `RFC822` (lo más caro). Ahora Gmail
pre-filtra en el servidor con `X-GM-RAW` (`after:`/`before:`), y el filtro
en Python queda solo como verificación de precisión.

Se completó:
- `X-GM-RAW` con `after:`/`before:` en el `search` de IMAP.
- Respeto de la exclusividad de `after:`/`before:` (`desde - 1 día`,
  `hasta + 1 día`).
- Filtro Python por header `Date:` conservado como red de seguridad
  (X-GM-RAW usa la fecha interna de Gmail, que puede diferir del header
  en correos reenviados o migrados).
- Fallback al comportamiento anterior si `X-GM-RAW` no está disponible
  (otros proveedores IMAP).
- `info["omitidos_fecha"]` ahora debería ser ~0 en condiciones normales.

## Qué se hizo

### 1. Pre-filtro IMAP con X-GM-RAW

`X-GM-RAW` es una extensión IMAP de Gmail que permite pasarle la sintaxis
de búsqueda nativa de Gmail (la misma del buscador web). Se usa para
pre-filtrar por fecha en el servidor:

    criterios.extend(["X-GM-RAW", f'"{gmail_query}"'])

Donde `gmail_query` se arma con `after:`/`before:`:

    after:<fecha_desde - 1 día>    # exclusivo → incluye fecha_desde
    before:<fecha_hasta + 1 día>   # exclusivo → incluye fecha_hasta

**Importante:** `after:` y `before:` son **exclusivos**. Si el usuario
pide `desde=2026-11-05`, hay que mandar `after:2026/11/04`. Si pide
`hasta=2026-11-05`, hay que mandar `before:2026/11/06`. Errar esto
pierde el día del borde.

### 2. Por qué NO se usa SINCE/BEFORE de IMAP estándar

Gmail **ignora** `SINCE`/`BEFORE` de IMAP estándar (o los aplica sobre
`INTERNALDATE`, la fecha de entrega, que no es el header `Date:`). Por
eso el pre-filtro va en `X-GM-RAW`, que sí es el motor nativo de Gmail
y respeta la sintaxis `after:`/`before:`.

### 3. Filtro Python conservado

El filtro por header `Date:` con `parsedate_to_datetime` se mantiene.
Razón: `X-GM-RAW` con `after:`/`before:` usa la fecha **interna** de
Gmail, que para correos recientes coincide casi siempre con el header
`Date:`, pero puede diferir en correos reenviados o migrados. El filtro
Python es la verificación de precisión final.

### 4. Fallback

Si `X-GM-RAW` no está disponible (otros proveedores IMAP, o Gmail
cambiara la extensión), el `search` debe reintentar sin ese criterio
y caer al comportamiento anterior (traer todo y filtrar en Python).
Esto mantiene la compatibilidad sin romper el flujo.

## Bugs resueltos en esta sesión

- **Descarga de Gmail leía toda la etiqueta y filtraba en Python**:
  O(N etiqueta) en descarga de `RFC822`. Fix: pre-filtro en servidor
  con `X-GM-RAW` (`after:`/`before:`), y filtro Python como verificación.
- **Bordes del rango perdían un día**: `after:`/`before:` son exclusivos.
  Fix: `desde - 1 día` y `hasta + 1 día`.

## Estado actual

### Funcional
- ✅ Ingresos con pre-filtro de fechas en servidor (`X-GM-RAW`).
- ✅ Filtro Python por `Date:` conservado como verificación.
- ✅ Fallback si `X-GM-RAW` no está disponible.
- ✅ Todos los módulos anteriores siguen funcionando (Egresos,
  Recordatorios, Servicios Externos, Corte Semanal, Catálogo QVET).

### Pendiente (Ingresos)
- Medir rendimiento con rango de 3-4 días y comparar con el
  comportamiento anterior (todo el buzón).
- Tests automáticos del pre-filtro (bordes de `after:`/`before:`) y
  del fallback.

### Pendiente (global, arrastrado)
- Tests automáticos (Recordatorios, Ingresos, Egresos, Corte,
  Servicios Externos).
- Documentación de instalación en Windows 11.
- Arranque automático con el sistema.

## Cómo trabajar

- Arrancar: `uvicorn main:app --reload --host 127.0.0.1 --port 8000`
- Probar Ingresos: `http://127.0.0.1:8000/ingresos`
- Para validar el pre-filtro: descargar con un rango de un solo día
  (`desde = hasta`) y verificar que entra exactamente ese día.
- Revisar el log generado por `_ruta_log()`: debe aparecer la línea
  `Pre-filtro Gmail (X-GM-RAW): after:... before:...`.
- `info["omitidos_fecha"]` ahora debería ser ~0. Si sube, revisar
  bordes de `after:`/`before:` o desfase fecha interna Gmail vs
  header `Date:`.

## Reglas nuevas (Ingresos / Gmail)

68. El pre-filtro de fecha de Gmail va en `X-GM-RAW` con
    `after:`/`before:`. NO en `SINCE`/`BEFORE` de IMAP estándar
    (Gmail los ignora).
69. `after:` y `before:` son exclusivos. Para un rango inclusivo
    `[desde, hasta]`, mandar `after:desde - 1 día` y
    `before:hasta + 1 día`.
70. El filtro Python por header `Date:` se conserva como verificación
    de precisión (X-GM-RAW usa la fecha interna de Gmail, que puede
    diferir del header en correos reenviados).
71. Si `X-GM-RAW` falla (proveedor no Gmail), reintentar sin ese
    criterio y caer al comportamiento anterior (traer todo y filtrar
    en Python).

# Sesión de trabajo — 2026-11-10 (VetSuite Web v0.9.x — bug de servicios externos y corte semanal)
Bug resuelto: el "Ver registros" de Servicios Externos mostraba la semana 44 para registros del 5 de noviembre (que es semana ISO 45). Causa: el endpoint /servicios_externos/arbol agrupaba con strftime('%W', fecha) de SQLite, que no es ISO 8601. Fix: agrupar por semana en Python con semana_de_fecha(), igual que el resto del módulo.

# Sesión de trabajo — 2026-11-08 (VetSuite Web v0.9.x — refactor de estructura)

## Resumen

Sesión de **reorganización de carpetas**. Se movieron los archivos sueltos
de la raíz a sus paquetes correspondientes, se centralizaron las rutas de
archivos en `shared/rutas.py`, y se aislaron los JSON de configuración en
`json/`. Sin cambios de funcionalidad.

Se completó:
- `shared/` con módulos transversales (db, jobs, templates_shared, uploads_manager, campos, rutas).
- `ingresos/` con todo el pipeline de Ingresos.
- `json/` con los 9 JSON de configuración.
- `scripts/` con los utilitarios de mantenimiento.
- `egresos/config_egresos.py` (antes en `config/`).
- Eliminación de la carpeta `config/`.
- `shared/rutas.py` como fuente única de verdad de rutas.

## Estructura final

(ver CONTEXTO.md §3)

## Archivos movidos

| Antes | Después |
|---|---|
| `db.py` | `shared/db.py` |
| `jobs.py` | `shared/jobs.py` |
| `templates_shared.py` | `shared/templates_shared.py` |
| `uploads_manager.py` | `shared/uploads_manager.py` |
| `config/campos.py` | `shared/campos.py` |
| `correo_facturas.py` | `ingresos/correo_facturas.py` |
| `correo_utils.py` | `ingresos/correo_utils.py` |
| `lector_facturas.py` | `ingresos/lector_facturas.py` |
| `excel_web.py` | `ingresos/excel_web.py` |
| `zip_generador.py` | `ingresos/zip_generador.py` |
| `config/config_egresos.py` | `egresos/config_egresos.py` |
| `reparar_archivos.py` | `scripts/reparar_archivos.py` |
| `limpiar_facturas.py` | `scripts/limpiar_facturas.py` |
| 9 JSON en raíz | `json/*.json` |

## Bugs resueltos

- **`ModuleNotFoundError: No module named 'excel_web'`** al mover
  `zip_generador.py` a `ingresos/`: el import `from excel_web import ...`
  no fue capturado por el `sed` inicial. Fix: `from ingresos.excel_web import ...`.
- **`scripts/reparar_archivos.py` importaba `from lector_facturas import ...`**:
  roto tras mover `lector_facturas.py` a `ingresos/`. Fix:
  `from ingresos.lector_facturas import ...`.
- **`DB_PATH` en `scripts/reparar_archivos.py`** apuntaba a `scripts/vetsuite.db`
  tras el `git mv`. Fix: `from shared.rutas import DB_FILE as DB_PATH`.
- **`sys.path.insert` después del import de `shared`** en
  `scripts/limpiar_facturas.py`. Fix: moverlo antes de cualquier import
  del proyecto.
- **`config/` no se podía borrar** por `config/__pycache__/`. Fix:
  `rm -rf config/`.
- **`sat_wrapper.BASE_DIR`** apuntaba a `BASE_DIR / "egresos_config.json"`
  y otros; al centralizar, todos los JSON de Egresos ahora viven en `json/`.

## Estado actual

### Funcional
- ✅ Todos los módulos importan sin error (`import main` + test de imports completo).
- ✅ Todas las constantes de `shared.rutas` resuelven a archivos existentes.
- ✅ Sin JSON sueltos en la raíz.
- ✅ Sin `config/`.
- ✅ 6 commits pusheados a `origin/main`.

### Pendiente (post-refactor)
- 📝 Verificar en runtime cada módulo (uvicorn + navegador).
- 🧹 Revisar `code.txt` en la raíz y decidir si borrar.
- 🧹 Confirmar `.DS_Store` en `.gitignore`.
- 📝 Actualizar `README.md` si menciona `python reparar_archivos.py` (ahora `python scripts/reparar_archivos.py`).

### Pendiente (deuda técnica del refactor)
- 🔧 Blindar los 14 `Path(__file__)` restantes con `shared.rutas`.
- 🔧 Consolidar `egresos/config_egresos.py` y `egresos/sat_wrapper.py`
  (duplican lógica de configuración leyendo archivos distintos).

### Pendiente (global, arrastrado)
- 🧪 Tests automáticos (Recordatorios, Ingresos, Egresos, Corte, Servicios Externos).
- 🪟 Documentación de instalación en Windows 11.
- ⏰ Arranque automático con el sistema.

## Reglas nuevas (estructura / refactor)

68. Las rutas de archivos se centralizan en `shared/rutas.py`.
69. Los JSON de configuración viven en `json/`.
70. Los módulos transversales (db, jobs, templates_shared, uploads_manager, campos) viven en `shared/`.
71. El pipeline de Ingresos vive en `ingresos/`.
72. Los scripts de mantenimiento viven en `scripts/`.
73. `egresos/config_egresos.py` vive en `egresos/`.
74. `config/` ya no existe.
75. Cuando muevas un archivo de carpeta, revisa `Path(__file__)` y los imports que lo referencian.

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
- Tests automáticos (Recordatorios, Ingresos, Egresos, Corte, Servicios
  Externos).

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
- Tests automáticos (Recordatorios, Ingresos, Egresos, Corte, Servicios
  Externos).

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
- Tests automáticos (Recordatorios, Ingresos, Egresos, Corte, Servicios
  Externos).

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
- 🧪 Tests automáticos (Recordatorios, Ingresos, Egresos, Corte).

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
- 🧪 Pruebas del usuario final en Ingresos, Egresos y Recordatorios.

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
- 🧪 Pruebas del usuario final en Ingresos, Egresos y Recordatorios.

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