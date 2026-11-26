(`Última actualización: 2026-11-20` → `2026-11-25`) y agregamos la sección 19 al índice.

# VetSuite Web — Contexto del proyecto

Versión: v0.9.x
Última actualización: 2026-11-20

Documento vivo del proyecto. Refleja el estado actual de la arquitectura,
la base de datos, los flujos y las reglas. El historial de sesiones vive en
CONTEXTO_SESION.md.

## Índice

1. Stack
2. Módulos (estado)
3. Estructura del proyecto
4. Base de datos
5. Flujos por módulo
6. Modal de reportes (árbol jerárquico)
7. Catálogo QVET
8. Corte Semanal
9. Servicios Externos
9.2 Convenios de Pago
9.3 Reportes con árbol en Convenios
10. Observaciones por celda en Corte Semanal
11. Ingresos: filtro de fechas, visor de archivos, re-clasificación
12. UI: iconos, sidebar, tabla full-height
13. Cómo trabajar
14. Reglas de la versión web
15. Reglas de git
16. Pendientes
17. Convenios de Pago (/convenios)
18. Recordatorios: pestaña Libres (plantillas)
19. Cuentas por Cobrar (`/cuentas_por_cobrar`)

---

## 1. Stack

- Python 3.14 + FastAPI + Uvicorn
- SQLite (vetsuite.db)
- Jinja2 para templates
- Tabler UI (CDN) para el diseño visual (basado en Bootstrap 5)
- Tabler Icons (CDN) para los iconos del sidebar y botones
- openpyxl para Excel (Ingresos, Egresos, Recordatorios, Corte)
- pdfplumber para PDFs de Ingresos
- cfdiclient para el SAT (Egresos)
- IMAP (imaplib) para Gmail (Ingresos)
- HTML + CSS + JS vanilla
- Threads daemon para jobs de larga duración (SAT, Gmail, convenios)
- localStorage para persistencia de UI (Recordatorios: tab activo, scroll,
  plantilla activa de Libres)

---

## 2. Módulos (estado)

- Ingresos: completo (Gmail → XML+PDF → BD → Excel → ZIP → catálogo → reportes → visor PDF/XML → filtro de fechas por header Date).
- Egresos: completo (SAT → XML → BD → Excel → ZIP → reportes).
- Recordatorios: completo (Excel → mensajes → WhatsApp wa.me → historial → pestaña Libres con plantillas editables).
- Corte Semanal: completo (captura diaria → totales → Excel → cierre de semana → reportes → observaciones por celda).
- Servicios Externos: completo (captura → filtros → cierre de semana → reportes).
- Catálogo QVET: consulta + edición + agregar (desde /ingresos/catalogo).
- Convenios de Pago: completo (captura → pagos → impresión → alertas → bloqueo → reportes → recordatorios automáticos).
- Reportes (árbol): modal en Ingresos, Egresos, Corte Semanal, Servicios Externos y Convenios.
- Estética y Transportes: no se incluye en la web.

---

## 3. Estructura del proyecto

Archivos en la raíz:

- main.py — FastAPI app + routers
- requirements.txt
- README.md
- CONTEXTO.md
- CONTEXTO_SESION.md
- .gitignore
- vetsuite.db — base de datos SQLite (NO va a git)

Paquete shared/ — módulos transversales a todos los módulos:

- __init__.py
- rutas.py — fuente única de verdad para rutas de archivos (ROOT, JSON_DIR, UPLOADS_DIR, DB_FILE + constantes de cada JSON)
- db.py — SQLite + init_db() + migraciones
- jobs.py — gestor de jobs con persistencia
- templates_shared.py — Jinja2Templates compartido
- uploads_manager.py — rutas de uploads de Ingresos (rechazados, sin_pdf, etc.)
- campos.py — MESES_ES y otras constantes
- jobs_convenios.py — thread daemon del job diario de convenios

Paquete ingresos/ — todo el pipeline de Ingresos:

- __init__.py
- correo_facturas.py — descarga IMAP de Gmail
- correo_utils.py — agrupar XML+PDF por correo
- lector_facturas.py — parser XML+PDF de Ingresos (productos del PDF, cabecera del XML)
- excel_web.py — generador de Excel de Ingresos
- zip_generador.py — ZIP mensual de Ingresos

Paquete egresos/:

- __init__.py
- manager.py — rutas y movimiento de XMLs
- sat_wrapper.py — wrapper de sat/ + config + proveedores
- excel_egresos.py — generador de Excel PUE + PPD
- config_egresos.py — configuración del módulo (lee/escribe desde json/)

Paquete core/:

- permisos_ip.py — módulos válidos, modulo_de_path(), es_admin_ip()
- rutas_egresos.py — rutas de carpetas de Egresos
- rutas_recordatorios.py — rutas de uploads/recordatorios/ y config
- sat_historial.py — snapshots del SAT
- corte_semanal/
  - __init__.py
  - expr.py — parser seguro de expresiones tipo 2345+679
  - semanas.py — helpers ISO week (lunes a domingo)
  - excel_corte.py — generador del Excel del Corte usando plantilla
- recordatorios/
  - __init__.py
  - sucursales.py — sucursal activa y nombres de clínica
  - historial.py — historial de envíos (teléfono|tipo|hash mensaje)
  - envio.py — construir URL de wa.me
  - procesar_excel.py — parser de citas/vacunas
  - convenios_cache.py — carga/guardado de convenios_importada.json
  - convenios_generator.py — lógica de generación de mensajes
  - plantillas.py — CRUD de plantillas libres (SQLite) + renderizar
  - clientes_libres.py — cache JSON de clientes para Libres
  - parser_clientes_libres.py — parser de Excel de clientes (Nombre + Teléfonos)
- servicios_externos/
  - __init__.py
  - config.py — cargar/guardar listas (conceptos, tipos de pago)
  - parser.py — parseo de "Efectivo 24/10/26" para migración
  - semanas.py — wrapper de core/corte_semanal/semanas.py
- convenios/
  - __init__.py
  - numero_a_letras.py — conversor de monto numérico a letra
  - helpers.py — folio, búsqueda de factura, contraseña, alertas

Paquete routers/:

- ingresos.py — incluye /arbol, /catalogo, /ver-pdf, /ver-xml, /reclasificar-sucursales
- rechazados.py
- egresos.py — incluye /arbol
- recordatorios.py — Citas/Vacunas/Convenios/Libres + plantillas + importar unificado
- config_gmail.py
- uploads.py
- corte_semanal.py — Corte Semanal (captura + Excel + cierre + /arbol + obs por celda)
- servicios_externos.py — Servicios Externos (captura + cierre + /arbol)
- admin_ips.py — administración de IPs y permisos (prefix /admin)
- convenios.py — Convenios de Pago (captura + pagos + impresión + alertas + /arbol)

Paquete sat/ (código del SAT de la app de escritorio, adaptado):

- conversion.py, descarga.py, procesar_xml.py, procesar_completo.py,
  guardar_egresos.py, mover_egresos.py

Paquete templates/:

- base.html
- index.html
- ingresos.html
- rechazados.html
- rechazados_rescatar.html
- config_gmail.html
- reclasificar.html
- catalogo.html
- egresos.html
- egresos_rechazados.html
- egresos_historial.html
- recordatorios.html
- corte_semanal.html
- servicios_externos.html
- admin_ips.html
- convenios.html
- convenios_form.html
- convenios_print.html

Paquete static/:

- style.css

Paquete scripts/ — utilidades de mantenimiento:

- __init__.py
- reparar_archivos.py — reparación de archivos huérfanos de Ingresos
- limpiar_facturas.py — limpieza de uploads/facturas/

Carpeta json/ — configuración y estado (NO va a git):

- catalogo_qvet.json
- categorias_manuales.json
- egresos_config.json
- gmail_config.json
- ip_permisos.json
- jobs_state.json
- proveedores_sucursal.json
- proveedores_tc.json (si existe)
- recordatorios_config.json
- servicios_externos_config.json
- solicitud_sat_activa.json (si existe)
- convenios_config.json
- convenios_alertas_vistas.json

Carpeta uploads/ (NO va a git):

- ingresos/<año>/<mes>/<sucursal>/<folio>.xml|.pdf
- egresos/efirma/ — .cer y .key
- egresos/temporales/ — ZIPs en proceso
- egresos/xml/<año>/<mes>/<sucursal>/<metodo>/<forma>/
- egresos/rechazados/<año>/<mes>/
- egresos/sat_historial/<timestamp><id>/
- recordatorios/agenda_importada.json
- recordatorios/vacunas_importada.json
- recordatorios/convenios_importada.json
- recordatorios/libres_clientes.json       # v0.9.x: clientes para pestaña Libres
- recordatorios/historial_recordatorios.json
- recordatorios/reportes/
- corte_semanal/plantilla_semanal.xlsx — plantilla base (NO va a git)
- corte_semanal/<año>-W<semana> - Semanal Baalak-Prado <Mes>.xlsx — Excel cerrados
- correos_procesados.json
- logs/

---

## 4. Base de datos

### Tabla ingresos

    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha TEXT NOT NULL,              -- YYYY-MM-DD
    folio TEXT,
    folio_fiscal TEXT,                -- UUID
    cliente TEXT,
    rfc TEXT,
    total REAL,
    sucursal TEXT,                    -- Baalak | Prado | _sin_sucursal
    notas TEXT,
    datos_json TEXT                   -- JSON con todos los campos del Excel

### Tabla egresos

    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha TEXT NOT NULL,              -- YYYY-MM-DD
    folio TEXT,
    uuid TEXT,
    proveedor TEXT,
    rfc TEXT,
    total REAL,
    sucursal TEXT,                    -- Baalak | Animalia
    metodo_pago TEXT,                 -- PUE | PPD
    forma_pago TEXT,                  -- Efectivo | TC | TD | Transferencia | PPD
    notas TEXT,
    serie TEXT

### Tabla recordatorios (placeholder, sin uso)

    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha TEXT NOT NULL,
    hora TEXT,
    cliente TEXT,
    mascota TEXT,
    telefono TEXT,
    tipo TEXT,                        -- cita | vacuna
    mensaje TEXT,
    enviado INTEGER DEFAULT 0

Nota: Recordatorios web NO usa esta tabla. Persiste en JSON dentro de
uploads/recordatorios/ (excepto las plantillas de Libres, que sí van a BD).
La tabla queda como placeholder de la app de escritorio.

### Tabla cortes_diarios

    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha TEXT NOT NULL,                    -- YYYY-MM-DD
    sucursal TEXT NOT NULL,                 -- Baalak | Prado
    efectivo_depositado TEXT DEFAULT '',
    efectivo_cobrado    TEXT DEFAULT '',
    tarjeta_debito      TEXT DEFAULT '',
    tarjeta_credito     TEXT DEFAULT '',
    transferencia       TEXT DEFAULT '',
    nomina_efectivo     TEXT DEFAULT '',
    gasolina            TEXT DEFAULT '',
    hemograma           TEXT DEFAULT '',
    patologia           TEXT DEFAULT '',
    varios              TEXT DEFAULT '',
    servicios           TEXT DEFAULT '',
    capacitacion        TEXT DEFAULT '',
    por_cobrar_json     TEXT DEFAULT '{}',
    obs_celdas_json     TEXT DEFAULT '{}',  -- v0.8: obs por celda
    observaciones       TEXT DEFAULT '',
    creado_en           TEXT DEFAULT CURRENT_TIMESTAMP,
    actualizado_en      TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(fecha, sucursal)

### Tabla cortes_semanas

    id INTEGER PRIMARY KEY AUTOINCREMENT,
    anio INTEGER NOT NULL,
    semana INTEGER NOT NULL,
    desde TEXT NOT NULL,                    -- lunes YYYY-MM-DD
    hasta TEXT NOT NULL,                    -- domingo YYYY-MM-DD
    estado TEXT NOT NULL DEFAULT 'abierta', -- abierta | cerrada
    excel_path TEXT,
    cerrado_en TEXT,
    UNIQUE(anio, semana)

### Tabla servicios_externos

    id INTEGER PRIMARY KEY AUTOINCREMENT,
    concepto TEXT NOT NULL DEFAULT '',
    fecha TEXT NOT NULL,                    -- YYYY-MM-DD
    cliente TEXT NOT NULL,
    mascota TEXT DEFAULT '',
    recuperacion TEXT DEFAULT '',           -- 'Si' | 'No' | 'N/A'
    fecha_entrega TEXT DEFAULT '',
    total REAL NOT NULL DEFAULT 0,
    fecha_pago TEXT DEFAULT '',             -- '' = pendiente
    tipo_pago TEXT DEFAULT '',              -- 'Efectivo' | 'Transferencia' | 'TC' | 'TD'
    notas TEXT DEFAULT '',
    creado_en TEXT DEFAULT CURRENT_TIMESTAMP,
    actualizado_en TEXT DEFAULT CURRENT_TIMESTAMP

### Tabla servicios_semanas

    id INTEGER PRIMARY KEY AUTOINCREMENT,
    anio INTEGER NOT NULL,
    semana INTEGER NOT NULL,
    desde TEXT NOT NULL,
    hasta TEXT NOT NULL,
    estado TEXT NOT NULL DEFAULT 'abierta',
    cerrado_en TEXT,
    total_pendiente REAL NOT NULL DEFAULT 0,
    total_pagado REAL NOT NULL DEFAULT 0,
    n_registros INTEGER NOT NULL DEFAULT 0,
    UNIQUE(anio, semana)

### Tabla convenios

    id INTEGER PRIMARY KEY AUTOINCREMENT,
    folio TEXT UNIQUE,
    fecha TEXT NOT NULL,
    propietario TEXT NOT NULL,
    telefono TEXT DEFAULT '',
    direccion TEXT DEFAULT '',
    mascota TEXT DEFAULT '',
    nhc TEXT DEFAULT '',
    monto_total REAL NOT NULL DEFAULT 0,
    monto_letra TEXT DEFAULT '',
    fecha_vencimiento TEXT DEFAULT '',
    lugar_pago TEXT DEFAULT 'recepcion',
    cuenta_bancaria TEXT DEFAULT '',
    ingreso_id INTEGER,
    albaran TEXT DEFAULT '',
    factura_numero TEXT DEFAULT '',
    factura_uuid TEXT DEFAULT '',
    pagado_con_tarjeta INTEGER DEFAULT 0,
    estado TEXT NOT NULL DEFAULT 'borrador',  -- borrador|impreso|firmado|pagado|cancelado
    notas TEXT DEFAULT '',
    creado_en TEXT DEFAULT CURRENT_TIMESTAMP,
    actualizado_en TEXT DEFAULT CURRENT_TIMESTAMP

### Tabla convenios_pagos

    id INTEGER PRIMARY KEY AUTOINCREMENT,
    convenio_id INTEGER NOT NULL,
    numero INTEGER NOT NULL,
    fecha TEXT NOT NULL,
    importe REAL NOT NULL DEFAULT 0,
    efectuado INTEGER NOT NULL DEFAULT 0,
    fecha_pago TEXT DEFAULT '',
    albaran TEXT DEFAULT '',
    factura_numero TEXT DEFAULT '',
    factura_uuid TEXT DEFAULT '',
    tipo_pago TEXT DEFAULT '',
    pagado_con_tarjeta INTEGER DEFAULT 0,
    FOREIGN KEY (convenio_id) REFERENCES convenios(id) ON DELETE CASCADE

### Tabla convenios_alertas_vistas

    convenio_id INTEGER NOT NULL,
    fecha_vista TEXT NOT NULL,              -- YYYY-MM-DD
    PRIMARY KEY (convenio_id, fecha_vista)

### Tabla plantillas_libres (v0.9.x)

    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    cuerpo TEXT NOT NULL,                   -- con variables {nombre}, {mascota}, {telefono}, {sucursal}, {fecha}
    activa INTEGER NOT NULL DEFAULT 1,      -- soft-delete (1=activa, 0=borrada)
    creada_en TEXT DEFAULT CURRENT_TIMESTAMP,
    actualizada_en TEXT DEFAULT CURRENT_TIMESTAMP

Notas:
- Soft-delete: borrar = `activa = 0`.
- El Reset de Recordatorios **no** borra esta tabla. Solo se borran con el
  botón 🗑 del modal de plantillas.
- Las variables se reemplazan al renderizar el mensaje por cliente.

---

## 5. Flujos por módulo

### Ingresos

1. Config Gmail (/config/gmail, modal en /ingresos).
2. Descarga de Gmail (no leídos / rango / últimos N días). El filtro de fechas se aplica en Python sobre el header `Date:`, no con `SINCE`/`BEFORE` de IMAP (Gmail los ignora). Pre-filtro en servidor con `X-GM-RAW` (after/before) + verificación en Python.
3. Procesamiento de cada par XML+PDF: cabecera del XML, productos del PDF, datos_json.
4. Renombrado a <folio>.xml / <folio>.pdf.
5. Organización en uploads/ingresos/<año>/<mes>/<sucursal>/.
6. Sucursal por serie del asunto (S1 → Baalak, Prados → Prado) o por `Serie` del XML (fallback).
7. Reclasificación de productos no catalogados.
8. Re-clasificación de sucursales (endpoint `/reclasificar-sucursales`).
9. Excel (/ingresos/excel) con filtros.
10. ZIP mensual con la estructura de escritorio.
11. Reset total del módulo.
12. Reportes: modal con árbol Año → Mes → Sucursal.
13. Catálogo: consulta, edición y agregar productos desde /ingresos/catalogo.
14. Visor: doble clic en fila abre el PDF; Ctrl/Cmd + doble clic abre el XML.

### Egresos

1. Config e.firma (/egresos, modal): subir .cer y .key a uploads/efirma/.
2. Prueba FIEL (AJAX, sin gastar solicitud).
3. Descarga del SAT con rango de fechas libre. Job en thread daemon.
4. Verificación cada 30s hasta estado 3 (terminada).
5. Descarga de paquetes (token fresco por paquete).
6. Procesamiento de cada XML: cabecera, PUE/PPD, forma de pago, observación.
7. Clasificación por proveedor (proveedores_sucursal.json).
8. Organización en uploads/egresos/xml/<año>/<mes>/<sucursal>/<metodo>/<forma>/.
9. Tabla con filtros (sucursal, método, forma) y totales PUE/PPD.
10. Cambio de sucursal (Animalia ↔ Baalak) con movimiento de XML.
11. Excel PUE + PPD separados.
12. ZIP mensual con la estructura de escritorio.
13. Historial del SAT con reprocesamiento.
14. Rechazados (ver / eliminar).
15. Reset total del módulo.
16. Reportes: modal con árbol Año → Mes → Sucursal → PUE/PPD.

### Recordatorios

1. Importar Excel (citas, vacunas o clientes libres) desde el modal. El backend detecta el tipo por columnas o fuerza con `destino=libres`.
2. Detección de tipo por columnas del encabezado (citas/vacunas) o parser de clientes (libres: Nombre + Teléfonos).
3. Expansión de abreviaturas, omisión de referidos, normalización de teléfonos.
4. Agrupación de clientes por teléfono.
5. Generación de mensajes con reglas de agrupación inteligente (citas/vacunas).
6. UI con cuatro tabs (Citas / Vacunas / Convenios / Libres) con persistencia en localStorage.
7. Selección por clic en la fila (radio oculto interno) + doble clic abre la vista previa del mensaje.
8. Botón único de envío/marcar/desmarcar con iconos Tabler (`ti-brand-whatsapp` / `ti-arrow-back-up`).
9. Modal de mensaje propio (independiente de Bootstrap JS).
10. Cambio de sucursal automático (regenera mensajes no enviados de citas/vacunas).
11. Envío por WhatsApp vía wa.me.
12. Historial de envíos (`historial_recordatorios.json`) indexado por `teléfono|tipo|hash(mensaje)`.
13. Exportar Excel con 4 hojas: Citas, Vacunas, Convenios, Libres.
14. Reset del módulo (borra JSONs + historial; **NO** borra plantillas).
15. Pestaña Libres:
    - Plantillas editables (CRUD) guardadas en SQLite (`plantillas_libres`).
    - Plantilla activa persistida en `localStorage` (`vetsuite.recordatorios.plantilla_libres`).
    - Al enviar, el mensaje se renderiza con la plantilla activa.
    - El "enviado" se marca por mensaje exacto: cambiar de plantilla desmarca a los ya enviados con otra.
    - Botón "Gestionar plantillas" visible solo en esta pestaña; abre modal con lista + editor.
    - No hay panel de workspace; la pestaña es una tabla idéntica a Citas/Vacunas/Convenios.

### Corte Semanal

1. Captura diaria por sucursal (Baalak / Prado) en /corte_semanal.
2. Sub-tabs por bloque (Ingresos / Egresos / Por cobrar / Observaciones).
3. Captura por celda con modal (acepta 2345+679).
4. Totales en vivo.
5. Excel con fórmulas vivas usando plantilla (uploads/corte_semanal/plantilla_semanal.xlsx).
6. Cierre de semana (bloquea la edición, guarda Excel).
7. Reapertura de semana (borra el Excel guardado).
8. Reportes: modal con árbol Año → Semana → Sucursal (ingresos, egresos, utilidad).
9. Observaciones por celda (v0.8): egresos y por_cobrar/colaboradores permiten capturar un detalle que se anexa al campo `observaciones` del día.

### Servicios Externos

1. Captura en /servicios_externos.
2. Filtro por semana ISO (navegación con anterior / siguiente o input type week).
3. Filtros client-side por concepto y estado (pendiente / pagado).
4. Doble clic en fila abre modal de edición.
5. Botón "Eliminar" dentro del modal.
6. Cierre de semana (snapshot de totales en servicios_semanas).
7. Reapertura de semana (limpia cerrado_en y totales).
8. Reportes: modal con árbol Año → Mes → Semana → Concepto → Estado.
9. Semana actual por defecto al abrir el módulo.

### Convenios de Pago

1. Captura en /convenios con folio automático.
2. Plan de pagos dinámico + impresión Carta.
3. Alertas de vencimiento con celda pintada (rojo/amarillo).
4. Bloqueo por contraseña cuando hay pagos efectuados.
5. Recordatorios automáticos: job diario en thread daemon.
6. Reportes: modal con árbol Año → Mes → Estado.
7. Filtros híbridos (server-side + client-side) y Excel con 2 hojas.

---

## 6. Modal de reportes (árbol jerárquico)

### Ingresos

- Botón "Ver registros" en la barra de herramientas.
- Abre dialog id modal-reportes con árbol Año → Mes → Sucursal.
- Datos vienen de GET /ingresos/arbol (JSON con agregados).
- Estructura del JSON:

    {
      "2026": {
        "10": {
          "Baalak": {"n": 77, "total": 396076.36},
          "Prado": {"n": 34, "total": 80755.45},
          "_total": {"n": 111, "total": 476831.81}
        },
        "_total": {"n": 111, "total": 476831.81}
      },
      "_total": {"n": 111, "total": 476831.81}
    }

- Importante: el _total a nivel raíz es lo que llena el footer del modal
  ("Total general: X registros · $Y"). Sin él, el footer muestra 0.
- Año y Mes: solo expanden/colapsan (details).
- Sucursal: clic simple aplica filtro (desde=YYYY-MM-01, hasta=YYYY-MM-ÚltimoDía,
  sucursal=Nombre).

### Egresos

- Mismo botón y mismo modal, con un nivel extra: Año → Mes → Sucursal → PUE/PPD.
- Datos vienen de GET /egresos/arbol.
- Estructura del JSON:

    {
      "2026": {
        "10": {
          "Baalak": {
            "PUE": {"n": 97, "total": 244807.83},
            "PPD": {"n": 38, "total": 237062.81},
            "_total": {"n": 135, "total": 481870.64}
          },
          "_total": {"n": 135, "total": 481870.64}
        },
        "_total": {"n": 135, "total": 481870.64}
      },
      "_total": {"n": 135, "total": 481870.64}
    }

- Año y Mes: solo expanden/colapsan.
- Sucursal: clic simple aplica filtro (sin metodo).
- PUE / PPD: clic simple aplica filtro con metodo=PUE o metodo=PPD.
  Si n === 0, el botón se deshabilita.
- PUE y PPD se muestran siempre ambos, aunque uno esté vacío.
- Ambos árboles mandan Cache-Control: no-store en los headers.

### Corte Semanal

- Botón "Ver registros" en la barra de herramientas.
- Abre dialog id modal-reportes-corte con árbol Año → Semana → Sucursal.
- Datos vienen de GET /corte_semanal/arbol.
- Cada sucursal muestra ingresos, egresos y utilidad de la semana.
- Clic en sucursal: navega a /corte_semanal?anio=&semana=.

### Servicios Externos

- Botón "Ver registros" en la barra de herramientas.
- Abre dialog id modal-reportes con árbol Año → Mes → Semana → Concepto → Estado.
- Datos vienen de GET /servicios_externos/arbol.
- Clic en semana: navega a esa semana.
- Clic en concepto: navega a esa semana y filtra por concepto.
- Clic en estado (Pagado / Pendiente): navega a esa semana y filtra por estado.

### Convenios

- Botón "Ver registros" en la barra de herramientas.
- Abre dialog id modal-reportes con árbol Año → Mes → Estado.
- Datos vienen de GET /convenios/arbol.
- Clic en estado: navega a /convenios?estado=&desde=&hasta=&q=.

### Reglas del modal de reportes

1. El _total debe existir en todos los niveles (incluida la raíz). Sin el de
   raíz, el footer sale en 0.
2. Los totales se calculan sobre las filas ya filtradas en listar(), no con
   queries separadas.
3. metodo_pago se normaliza a PUE o PPD al insertar.
4. El filtro SQL para PUE es tolerante a NULL/"" usando
   COALESCE(NULLIF(metodo_pago, ''), 'PUE').
5. En ingresos.html la función de formato se llama fmt. En egresos.html se
   llama fmtMonto. No mezclar.
6. Los modales usan dialog nativo. No se cierran al hacer clic fuera
   (solo con X, botón "Cerrar" o Escape).

---

## 7. Catálogo QVET (/ingresos/catalogo)

- Dos archivos:
  - catalogo_qvet.json — base curada a mano (read-only desde la app).
  - categorias_manuales.json — overrides escritos por la app (read-write).
- El parser consulta primero los manuales, luego la base.
- Endpoints:
  - GET /ingresos/catalogo — página HTML con tabla.
  - POST /ingresos/catalogo/actualizar — cambia categoría (select en fila).
  - POST /ingresos/catalogo/agregar — agrega producto nuevo.
  - POST /ingresos/catalogo/eliminar — quita override (vuelve a base o U).
- Filtrado client-side: el endpoint manda TODOS los items; el navegador filtra
  por texto (debounce 150ms) y por chips de categoría.
- Edición inline: cada fila tiene un select con las categorías. Al cambiar,
  guarda en categorias_manuales.json.
- Chips: "Todas" + una por categoría con conteo. Activo en azul, inactivos en gris.
- Origen: cada fila indica "Base QVET" o "Corregido".
- Quitar override: botón X en filas corregidas; recarga la página.

---

## 8. Corte Semanal (/corte_semanal)

Reemplaza el Excel semanal manual. Captura día a día los ingresos
(efectivo depositado, efectivo cobrado, tarjeta débito, tarjeta crédito,
transferencia), los egresos operativos (nómina, gasolina, hemograma,
patología, varios, servicios, capacitación), los conceptos de "por cobrar"
(12 categorías) y las observaciones. Al cerrar la semana se genera un Excel
idéntico al original (con fórmulas vivas) y se bloquea la edición.

- Montos como TEXT. El usuario puede capturar 2345+679. El total se evalúa
  con core/corte_semanal/expr.py (sin eval).
- Excel desde plantilla (uploads/corte_semanal/plantilla_semanal.xlsx).
- Nombre de hoja: "Sem del <día1> al <día7>".
- Nombre de archivo: "Semanal Baalak-Prado <Mes>.xlsx" (mes del lunes).
- Archivo cerrado: "<año>-W<semana> - Semanal Baalak-Prado <Mes>.xlsx".
- Semana cerrada: POST /corte_semanal/actualizar responde 409.
- Reabrir borra el Excel guardado.
- Excel generado al cerrar, no antes.
- v0.8: observaciones por celda (ver §10).

---

## 9. Servicios Externos (/servicios_externos)

Registro continuo de servicios externos (incineraciones, hemogramas, etc.).

- Conceptos editables desde la UI. Tipos de pago fijos:
  Efectivo, Transferencia, TC, TD.
- recuperacion es listbox cerrado: Si / No / N/A.
- Estado "pendiente" = fecha_pago vacío.
- tipo_pago se limpia si no hay fecha_pago.
- Filtro por semana ISO (input type week + navegación anterior / siguiente).
- Cierre de semana con snapshot de totales (servicios_semanas).
- Semana cerrada es inmutable (409 en actualizar / eliminar / marcar-pagado).
- Reportes con árbol Año → Mes → Semana → Concepto → Estado.
- Semana actual por defecto al abrir el módulo.
- Ruta pública: /servicios_externos (guion bajo).
- Módulo interno: "servicios_externos" en ip_permisos.json.

---

## 9.2 Convenios de Pago (/convenios)

Módulo de reconocimiento de deuda con plan de pagos, impresión Carta y
seguimiento de pagos con bloqueo por contraseña cuando hay pagos
efectuados.

### Modelo de datos

Tres tablas: `convenios`, `convenios_pagos`, `convenios_alertas_vistas`
(ver §4).

### Estados

`borrador` → `impreso` → `firmado` → `pagado` → `cancelado`.

### Reglas

1. Los convenios **no llevan IVA** (servicios médicos veterinarios exentos).
2. Los pagos se guardan con **upsert por `id`**. Los efectuados nunca se
   modifican ni se eliminan desde el formulario.
3. El botón 🗑 vive **dentro del formulario**, no en el listado. Solo
   aparece si `estado == 'borrador'` y no hay pagos efectuados.
4. Cambios estructurales (monto, fecha, propietario, mascota) se
   bloquean si hay pagos efectuados (409).
5. La contraseña de desbloqueo es opcional (`password_hash` vacío →
   modo abierto). En producción debe estar configurada.
6. La búsqueda de factura solo vincula facturas a nombre del cliente
   (no público en general). Primero por RFC, luego por nombre.
7. El UUID de factura se llena desde `ingresos.folio_fiscal` al buscar
   la factura del cliente.
8. La impresión usa iframe oculto con `print()`. Fallback a pestaña
   nueva si el navegador lo bloquea.
9. Doble clic en fila del listado abre editar. Botones de la fila tienen
   `event.stopPropagation()`.
10. La celda de vencimiento se pinta rojo (`celda-vencida`) o amarillo
    (`celda-por-vencer`) según el estado, con los días debajo.
11. El módulo `"convenios"` debe estar en `ip_permisos.json`.
12. El conversor `numero_a_letras` trabaja con centavos enteros para
    evitar errores de punto flotante.
13. Filtros híbridos: `estado`/`desde`/`hasta` server-side, `q`
    client-side con debounce 150ms. El `q` viaja en la URL como hidden.
14. El Excel de convenios respeta los mismos filtros que el listado.

---

## 9.3 Reportes con árbol en Convenios

El botón "Ver registros" en `/convenios` abre un modal con un árbol
**Año → Mes → Estado**.

- Endpoint: `GET /convenios/arbol`.
- Estructura del JSON:

    {
      "2026": {
        "11": {
          "borrador":  {"n": 2, "total": 5000.0},
          "impreso":   {"n": 1, "total": 1200.0},
          "firmado":   {"n": 0, "total": 0.0},
          "pagado":    {"n": 3, "total": 8500.0},
          "cancelado": {"n": 0, "total": 0.0},
          "_total":    {"n": 6, "total": 14700.0}
        },
        "_total": {"n": 6, "total": 14700.0}
      },
      "_total": {"n": 6, "total": 14700.0}
    }

- El `_total` debe existir en **cuatro niveles** (estado, mes, año,
  raíz). Sin el de raíz, el footer del modal sale en 0.
- Clic en un **estado**: cierra el modal y navega a
  `/convenios?estado=<est>&desde=<YYYY-MM-01>&hasta=<último día>&q=`.
- Clic en **año** o **mes**: solo expande/colapsa (no navega).
- El endpoint manda `Cache-Control: no-store`.
- Los estilos se reutilizan de Egresos / Servicios Externos.

---

## 9.4 Recordatorios de Convenios (integración)

El módulo de Recordatorios incluye una **tercera pestaña "Convenios"**
que muestra los mensajes generados automáticamente para convenios
vencidos o por vencer, y permite enviarlos por WhatsApp con el mismo
flujo que Citas y Vacunas.

### Generación

- Un **job diario** (thread daemon en `shared/jobs_convenios.py`) corre
  a la hora configurada en `json/convenios_config.json` →
  `recordatorios.hora` (default `08:00`).
- Si la app estaba apagada a esa hora, el job corre al arrancar (si ya
  pasó la hora y no se generó hoy).
- El job recorre los convenios con `estado NOT IN ('pagado', 'cancelado')`
  y `fecha_vencimiento != ''`.
- Calcula el saldo pendiente. Si `pendiente <= 0.01`, lo salta.
- Calcula `dias = fecha_vencimiento - hoy`:
  - `dias < 0` → tipo `vencido`.
  - `0 <= dias <= dias_por_vencer` → tipo `por_vencer`.
  - `dias > dias_por_vencer` → no genera.
- Genera el mensaje y lo inserta en
  `uploads/recordatorios/convenios_importada.json` con un `id` único
  `conv-<cid>-<YYYY-MM-DD>`.
- **No envía nada solo.** Solo prepara los mensajes.

### Endpoints

| Método | Ruta | Función |
|---|---|---|
| GET | `/recordatorios/convenios/whatsapp/{idx}` | URL + mensaje |
| POST | `/recordatorios/convenios/marcar/{idx}` | Marca enviado |
| POST | `/recordatorios/convenios/desmarcar/{idx}` | Desmarca |
| POST | `/recordatorios/convenios/descartar/{idx}` | Descarta (no se regenera hoy) |
| POST | `/recordatorios/convenios/regenerar` | Fuerza la generación manual |

### Configuración

`json/convenios_config.json`:

    {
      "recordatorios": {
        "activo": true,
        "hora": "08:00",
        "dias_por_vencer": 3
      }
    }

---

## 10. Observaciones por celda en Corte Semanal (v0.8)

Permite anexar detalle a la observación del día desde el modal de captura
de celda, sin tener que ir al tab Observaciones.

### Alcance

- **Egresos** (`nomina_efectivo`, `gasolina`, `hemograma`, `patologia`,
  `varios`, `servicios`, `capacitacion`): el modal muestra un textarea
  "Detalle del gasto". Se anexa al día como `Gasto de $X: <texto>`.
- **Por cobrar / `colaboradores`**: el modal muestra un textarea
  "Desglose del adeudo". Se anexa al día como `Deuda de $X: <texto>`.
- El resto de celdas (ingresos, otras de por_cobrar) **no** muestran textarea.

### Persistencia

- Nueva columna `cortes_diarios.obs_celdas_json` (TEXT, default `'{}'`).
- Estructura:

      {
        "__manual__": "texto libre del tab Observaciones",
        "gasolina": "agua",
        "nomina_efectivo": "sueldos semana",
        "por_cobrar:colaboradores": "$100 de Andrea y $500 de Mimi"
      }

- `__manual__` guarda lo que el usuario escribe en el tab Observaciones.
- El resto de claves son `campo` o `campo:subcampo`.

### Regeneración de `observaciones`

Cada vez que se guarda una celda (o la observación manual), el backend
**relee el valor fresco** de la celda y **regenera** el campo
`observaciones` del día:

1. Primero `__manual__` (si existe).
2. Luego, por cada clave en `obs_celdas_json`, se formatea el texto:
   - Egreso → `Gasto de $X: <texto>`
   - Colaboradores → `Deuda de $X: <texto>`
3. Se unen con `\n`.

Si el usuario **borra** el textarea y guarda, la clave se elimina del JSON
y la línea desaparece de `observaciones`.

Si el usuario **cambia el monto** de la celda, la cantidad en el texto se
**recalcula automáticamente**, pero el texto que escribió se conserva.

### Frontend

- `<dialog id="modal-celda">` tiene un bloque `#modal-celda-obs-wrap`
  (oculto por default) con `<textarea id="modal-celda-obs">`.
- `abrirModal(td)` decide si mostrarlo según `campo`/`subcampo`.
- `aplicarModal()` manda `obs` en el payload de `/actualizar`.
- El tab Observaciones usa `<textarea class="corte-obs">` (no `<input>`).
- Auto-resize en el textarea.

### Migración

En `init_db()`:

1. `PRAGMA table_info(cortes_diarios)` → si no existe `obs_celdas_json`,
   `ALTER TABLE ADD COLUMN`.
2. Para filas con `observaciones != ''` y `obs_celdas_json = '{}'`, se
   siembra `__manual__` con el texto viejo, para no perderlo.

---

## 11. Ingresos: filtro de fechas, visor de archivos, re-clasificación (v0.9)

### Filtro de fechas de Gmail

- **Pre-filtro en servidor con `X-GM-RAW`** (v0.9.x): el `search` de
  IMAP incluye `X-GM-RAW` con `after:`/`before:` para que Gmail
  filtre por fecha en el servidor.
- **No se usa** `SINCE`/`BEFORE` de IMAP estándar. Gmail los ignora
  o los aplica sobre `INTERNALDATE`.
- El `search` de IMAP combina `UNSEEN` (si aplica), `FROM` (si aplica)
  y `X-GM-RAW` (si hay rango de fechas).
- **Filtro de precisión en Python** (v0.9): se conserva el filtro por
  header `Date:` con `parsedate_to_datetime`.
- El filtro Python se aplica **antes** del chequeo de caché y del
  filtro de remitente.
- `info["omitidos_fecha"]` cuenta los correos descartados por fecha.
- **Fallback**: si `X-GM-RAW` no está disponible (proveedor no Gmail),
  el `search` reintenta sin ese criterio.

### Visor PDF/XML

- Endpoints:
  - `GET /ingresos/ver-pdf/{id}` → sirve el PDF `inline`.
  - `GET /ingresos/ver-xml/{id}` → sirve el XML `inline`.
- Helper `_buscar_archivo(row, extension)`:
  1. Busca por folio en la sucursal de la fila.
  2. Fallback por UUID.
  3. Fallback en cualquier sucursal.
- Devuelve `404` si el archivo no está en disco.
- Headers: `Content-Disposition: inline`, `Cache-Control: no-store`.

### Re-clasificación de sucursales

- Endpoint: `POST /ingresos/reclasificar-sucursales`.
- Recorre las facturas con `sucursal` vacía o `_sin_sucursal`.
- Para cada una: busca su XML, lee `Serie` con `leer_xml_factura()`, aplica
  `serie_a_sucursal(serie)`.
- `S1` → Baalak, `PRADO`/`PRADOS` → Prado. Otras series no se tocan.
- Actualiza la BD y mueve los archivos a la carpeta correcta.

### Regex de serie tolerante

El regex en `correo_facturas.py` para extraer la serie del asunto es:

    r"\b(S1|PRADOS?)\b[\/\s\-]*(\d+)"

Normaliza `PRADO` → `PRADOS`. Quita ceros a la izquierda. Si no encuentra
serie conocida, cae a un regex genérico `([A-Za-z0-9]+)\s*-\s*(\d+)`.

---

## 12. UI: iconos, sidebar, tabla full-height (v0.9)

### Tabler Icons

- CDN en `base.html`:

      <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@latest/dist/tabler-icons.min.css">

- Uso: `<i class="ti ti-<nombre>"></i>`.

### Mapeo de iconos

| Contexto | Icono | Clase |
|---|---|---|
| Ingresos (sidebar) | inbox | `ti-inbox` |
| Egresos (sidebar) | send | `ti-send` |
| Corte Semanal (sidebar) | chart-histogram | `ti-chart-histogram` |
| Servicios Externos (sidebar) | tools | `ti-tools` |
| Recordatorios (sidebar) | calendar-event | `ti-calendar-event` |
| Convenios (sidebar) | file-text | `ti-file-text` |
| Permisos IP (sidebar) | shield-lock | `ti-shield-lock` |
| Brand (VetSuite) | paw | `ti-paw` |
| Ver registros | list | `ti-list` |
| Exportar Excel | file-excel | `ti-file-excel` |
| Enviar WhatsApp | brand-whatsapp | `ti-brand-whatsapp` |
| Desmarcar | arrow-back-up | `ti-arrow-back-up` |
| Reset | trash | `ti-trash` |
| Plantillas libres | layout-list | `ti-layout-list` |
| Regenerar (Convenios) | refresh | `ti-refresh` |
| Descartar (Convenios) | x | `ti-x` |

### Color del módulo activo en el sidebar

En `static/style.css`:

    .navbar-vertical .nav-item.active > .nav-link {
        background-color: #206bc4;
        color: #ffffff;
    }
    .navbar-vertical .nav-item.active > .nav-link .nav-link-icon,
    .navbar-vertical .nav-item.active > .nav-link .nav-link-title {
        color: #ffffff;
    }

### Item activo de Permisos IP

- La URL real es `/admin/ips`, pero el nombre interno del módulo es
  `"admin_ips"`.
- El `startswith` en `base.html` debe comparar contra la **URL**:

      {% if request.url.path.startswith('/admin') %}active{% endif %}

### Tabla de Ingresos full-height

En `static/style.css`:

    .page-wrapper > .page-body {
        display: flex; flex-direction: column; min-height: 0;
    }
    .page-body > .container-xl {
        display: flex; flex-direction: column; flex: 1 1 auto; min-height: 0;
    }
    .card.tabla-full {
        flex: 1 1 auto; min-height: 0;
        display: flex; flex-direction: column; margin-bottom: 0;
    }
    .card.tabla-full .tabla-scroll {
        flex: 1 1 auto; min-height: 0;
        max-height: none !important; overflow: auto;
    }

### Doble clic en fila de Ingresos

- `dblclick` normal → abre `/ingresos/ver-pdf/{id}` en pestaña nueva.
- `Ctrl/Cmd + dblclick` → abre `/ingresos/ver-xml/{id}`.

---

## 13. Cómo trabajar

- Arrancar: uvicorn main:app --reload --host 127.0.0.1 --port 8000
- Probar: http://127.0.0.1:8000/ingresos, /egresos, /recordatorios,
  /corte_semanal, /servicios_externos, /convenios, /ingresos/catalogo
- Probar parser de Recordatorios: python probar_parser.py archivo.xlsx
- La BD está en vetsuite.db (no va a git).
- Los archivos de uploads/ no van a git.
- Configs que NO van a git: gmail_config.json, egresos_config.json,
  recordatorios_config.json, catalogo_qvet.json, categorias_manuales.json,
  proveedores_sucursal.json, solicitud_sat_activa.json, jobs_state.json,
  servicios_externos_config.json, convenios_config.json,
  convenios_alertas_vistas.json.
- Si se corrompen los archivos de Ingresos: python scripts/reparar_archivos.py
- Si hay basura en uploads/facturas/: python scripts/limpiar_facturas.py
- Si uvicorn no recarga un cambio de CSS/JS, forzar recarga en el navegador
  con Ctrl+Shift+R (Cmd+Shift+R en Mac). Un `304 Not Modified` en la
  consola es normal.
- Los JSON de configuración viven en `json/`, no en la raíz.
- La carpeta `scripts/` tiene los utilitarios.

---

## 14. Reglas de la versión web

1. El PDF es la fuente de productos en Ingresos. El XML solo aporta cabecera.
2. El XML es la fuente de todo en Egresos. No hay PDF.
3. Archivos de Ingresos: <folio>.xml|.pdf.
4. Archivos de Egresos: <serie>-<folio>.xml.
5. Sucursal de Ingresos por serie: S1 → Baalak, Prados → Prado.
6. Sucursal de Egresos por RFC en proveedores_sucursal.json, default Baalak.
7. Sucursal de Recordatorios por recordatorios_config.json
   (BAALAK_CENTRAL | BAALAK_PRADO | ANIMALIA).
8. datos_json guarda todos los campos del Excel de Ingresos.
9. El ZIP mensual incluye el Excel con la estructura de escritorio.
10. El historial del SAT se guarda siempre (si el flag está activo).
11. El token del SAT expira en 5 min: obtener uno fresco por paquete.
12. El SAT devuelve el ZIP en paquete_b64.
13. Reset borra TODO lo del módulo pero NO lo global.
14. base.html expone block head y block scripts.
15. Recordatorios persiste en JSON + localStorage (tab, scroll, plantilla activa).
16. Los archivos listados en "Cómo trabajar" NO van a git.
17. El catálogo QVET vive en JSON, no en SQLite.
18. El catálogo se filtra client-side.
19. Los árboles de reportes se calculan en el backend (solo agregados).
20. metodo_pago se normaliza a PUE o PPD al insertar.
21. El Corte Semanal usa plantilla, no generación a mano.
22. Los montos del Corte se guardan como TEXT (expresiones 2345+679).
23. El Corte genera el Excel solo al cerrar (o al descargar borrador).
24. Una semana cerrada es inmutable en Corte (409).
25. core/permisos_ip.py reconoce /corte_semanal como módulo "corte".
26. Servicios Externos usa una sola tabla servicios_externos.
27. Estado "pendiente" = fecha_pago = ''.
28. tipo_pago se limpia si no hay fecha_pago.
29. tipos_pago vive en servicios_externos_config.json con los valores fijos.
30. recuperacion es listbox cerrado: Si | No | N/A.
31. Servicios Externos no genera Excel. Es solo control en pantalla.
32. Ruta pública con guion bajo: /servicios_externos. Módulo interno:
    "servicios_externos" en ip_permisos.json.
33. Servicios Externos se cierra por semana ISO (lunes a domingo).
34. Al cerrar se guarda snapshot de totales en servicios_semanas.
35. El filtro de semana reemplaza a "Desde/Hasta" en Servicios Externos.
36. La tabla siempre muestra exactamente una semana.
37. El botón eliminar de Servicios Externos vive dentro del modal.
38. window.abrirModalReportes se define dentro del IIFE.
39. v0.8: `cortes_diarios.obs_celdas_json` guarda las observaciones por
    celda. `__manual__` es la observación libre del día.
40. v0.8: `observaciones` del día se REGENERA a partir de `__manual__` +
    las claves de `obs_celdas_json`. Nunca se anexa a mano.
41. v0.8: formato de las observaciones generadas:
    - Egreso: `Gasto de $X: <texto>`
    - Colaboradores: `Deuda de $X: <texto>`
42. v0.8: si el usuario edita el monto de la celda, la cantidad en la
    observación se recalcula; el texto escrito por el usuario se conserva.
43. v0.8: si el usuario borra el textarea, la línea desaparece de
    `observaciones` (se elimina la clave del JSON).
44. v0.8: el tab Observaciones usa `<textarea>` (no `<input>`).
45. v0.9: el filtro de fechas de Gmail se hace en Python sobre el header
    `Date:` con `parsedate_to_datetime`. NO se usa `SINCE`/`BEFORE`.
46. v0.9: el `search` de IMAP solo lleva `UNSEEN`, `FROM` y `ALL`.
47. v0.9: el filtro de fecha se aplica ANTES del caché y del filtro de
    remitente.
48. v0.9: el regex de serie del asunto es tolerante:
    `\b(S1|PRADOS?)\b[\/\s\-]*(\d+)`.
49. v0.9: `serie_a_sucursal()` normaliza `PRADO` → `PRADOS` y case.
50. v0.9: el endpoint `/reclasificar-sucursales` solo mueve a Baalak/Prado
    cuando el XML dice `S1` o `Prado(s)`.
51. v0.9: el visor de archivos sirve `inline` con `Cache-Control: no-store`.
52. v0.9: doble clic en fila de Ingresos abre PDF; Ctrl/Cmd + doble clic
    abre XML.
53. v0.9: el item activo del sidebar compara `request.url.path` (URL),
    NO el nombre interno del módulo.
54. v0.9: los iconos del sidebar y botones usan Tabler Icons
    (`<i class="ti ti-<nombre>"></i>`), no emojis.
55. v0.9: la tabla de Ingresos usa `.card.tabla-full` + `.tabla-scroll`.
56. v0.9: si uvicorn no recarga CSS/JS, forzar recarga en el navegador.
57. v0.9.x: las rutas de archivos se centralizan en `shared/rutas.py`.
58. v0.9.x: `shared/rutas.py` expone `ROOT`, `JSON_DIR`, `UPLOADS_DIR`,
    `DB_FILE` y una constante por cada JSON de configuración.
59. v0.9.x: los JSON de configuración viven en `json/`.
60. v0.9.x: los módulos transversales (db, jobs, templates_shared,
    uploads_manager, campos) viven en `shared/`.
61. v0.9.x: el pipeline de Ingresos vive en `ingresos/`.
62. v0.9.x: los scripts de mantenimiento viven en `scripts/`.
63. v0.9.x: la navegación con Enter/Shift+Enter en celdas numéricas del
    Corte Semanal es tipo Excel.
64. v0.9.x: el pre-filtro de fecha de Gmail va en `X-GM-RAW`.
65. v0.9.x: `after:` y `before:` son exclusivos. Rango inclusivo:
    `after:<desde - 1 día>` y `before:<hasta + 1 día>`.
66. v0.9.x: el filtro Python por header `Date:` se conserva.
67. v0.9.x: si `X-GM-RAW` no está disponible, reintentar sin ese criterio.
68. v0.9.x: los Convenios de Pago NO llevan IVA.
69. v0.9.x: los pagos de convenio se guardan con upsert por `id`.
70. v0.9.x: si un convenio tiene pagos efectuados, los cambios
    estructurales se rechazan con 409.
71. v0.9.x: la impresión de convenios usa iframe oculto con `print()`.
72. v0.9.x: la celda de vencimiento del listado de convenios se pinta
    rojo (vencido) o amarillo (por vencer).
73. v0.9.x: el job de recordatorios de convenios corre en un thread
    daemon en `shared/jobs_convenios.py`.
74. v0.9.x: un mensaje de recordatorio por convenio por día.
75. v0.9.x: el job no envía nada solo. Solo prepara los mensajes.
76. v0.9.x: el `reset` de Recordatorios borra también
    `convenios_importada.json`.
77. v0.9.x: los mensajes descartados no se regeneran el mismo día.
78. v0.9.x: el historial de envíos de convenios usa
    `historial_recordatorios.json` con `tipo="convenios"`.
79. v0.9.x: si la app estaba apagada a la hora configurada, el job de
    convenios corre al arrancar.
80. v0.9.x: el listado de convenios tiene filtros híbridos.
81. v0.9.x: el Excel de convenios respeta los mismos filtros que el listado.
82. v0.9.x: el UUID de factura se llena desde `ingresos.folio_fiscal`.
83. v0.9.x: el botón eliminar de convenios vive dentro del formulario.
84. v0.9.x: la pestaña Convenios de Recordatorios tiene botones
    "Regenerar" y "Descartar".
85. v0.9.x: los `print()` de `sat/descarga.py` son avisos de progreso.
86. v0.9.x: múltiples `addEventListener('DOMContentLoaded', ...)` en el
    mismo `<script>` son válidos y se acumulan.
87. v0.9.x: la pestaña Libres de Recordatorios usa plantillas de la tabla
    `plantillas_libres` (SQLite). El Reset **no** las borra.
88. v0.9.x: el "enviado" de Libres se marca por `hash(mensaje)`. Cambiar
    de plantilla desmarca a los clientes ya enviados con otra.
89. v0.9.x: la plantilla activa de Libres vive en `localStorage`
    (`vetsuite.recordatorios.plantilla_libres`) y se pasa al backend por
    `?plantilla_libres=<id>`.
90. v0.9.x: `whatsapp`, `marcar` y `desmarcar` son genéricos
    (`{tipo}` = `citas|vacunas|libres`). No hay endpoints duplicados.
91. v0.9.x: el parser de Excel de clientes libres
    (`parsear_excel_clientes`) acepta columnas de teléfono con prefijos
    (`TELÉFONO1`, `TELÉFONO SMS`, etc.) y normaliza formatos sucios.
92. v0.9.x: el Excel de Recordatorios tiene 4 hojas: Citas, Vacunas,
    Convenios, Libres.

---

## 15. Reglas de git

NO van a git:

- vetsuite.db
- uploads/ (todo)
- json/ (toda la carpeta; la config es local)

---

## 16. Pendientes

- [ ] Tests automáticos del parser de Recordatorios.
- [ ] Tests automáticos del pipeline de Ingresos y Egresos.
- [ ] Tests automáticos del parser de expresiones del Corte (expr.py).
- [ ] Tests automáticos del generador de Excel del Corte (excel_corte.py).
- [ ] Tests automáticos del módulo Servicios Externos.
- [ ] Tests automáticos del árbol de reportes de Corte Semanal.
- [ ] Tests automáticos de la regeneración de observaciones.
- [ ] Tests automáticos del filtro de fechas de Gmail y del regex de serie.
- [ ] Tests automáticos del pre-filtro `X-GM-RAW` y del fallback.
- [ ] Tests automáticos del conversor `numero_a_letras`.
- [ ] Tests automáticos del job de convenios.
- [ ] Tests automáticos del CRUD de plantillas libres.
- [ ] Tests automáticos del parser de clientes libres.
- [ ] Exportar a Excel desde Servicios Externos (opcional).
- [ ] Historial de semanas cerradas en Servicios Externos.
- [ ] Endpoint `/egresos/zip` con filtro por rango de fechas.
- [ ] Rotación de snapshots del SAT (borrar los de más de 6 meses).
- [ ] Manejo de XMLs tipo E y P en Egresos.
- [ ] Validación más estricta al cerrar la semana del Corte.
- [ ] Historial de cierres del Corte (lista de semanas cerradas).
- [ ] Sincronizar plantilla activa de Libres entre pestañas del navegador.

---

## 17. Convenios de Pago (/convenios)

(La sección completa está en §9.2 y §9.3.)

---

## 18. Recordatorios: pestaña Libres (v0.9.x)

Permite enviar mensajes libres (no atados a citas/vacunas) usando plantillas
editables.

### Datos

- **Clientes libres**: `uploads/recordatorios/libres_clientes.json`.
  - Se importan con `parsear_excel_clientes()`.
  - Acepta columnas: `Nombre` + `Teléfono1`, `Teléfono2`, `Teléfono SMS`,
    `Celular`, etc.
  - Deduplicación por teléfono.
  - Persiste hasta Reset.
- **Plantillas**: tabla `plantillas_libres` en `vetsuite.db`.
  - CRUD en `core/recordatorios/plantillas.py`.
  - Soft-delete con `activa=0`.
  - **No** se borran con Reset.
- **Historial**: `historial_recordatorios.json` con `tipo="libres"`.
  - La clave es `teléfono|tipo|hash(mensaje)`. Cambiar de plantilla
    desmarca al cliente.
- **Plantilla activa**: `localStorage` (`vetsuite.recordatorios.plantilla_libres`).
  - Se manda por query param `?plantilla_libres=<id>` al `index`.
  - El `index` renderiza el mensaje en el backend con esa plantilla.

### Endpoints

| Método | Ruta | Función |
|---|---|---|
| GET | `/recordatorios/plantillas` | Listar activas |
| POST | `/recordatorios/plantillas` | Crear |
| PUT | `/recordatorios/plantillas/{pid}` | Editar |
| DELETE | `/recordatorios/plantillas/{pid}` | Borrar (soft-delete) |
| GET | `/recordatorios/whatsapp/libres/{idx}?plantilla_id=N` | URL + mensaje renderizado |
| POST | `/recordatorios/marcar/libres/{idx}?plantilla_id=N` | Marcar enviado |
| POST | `/recordatorios/desmarcar/libres/{idx}` | Desmarcar |
| GET | `/recordatorios/libres/stats?plantilla_id=N` | Conteo enviados (opcional) |

> **Nota**: `whatsapp`, `marcar`, `desmarcar` son **genéricos**
> (`{tipo}` = `citas|vacunas|libres`). No hay endpoints duplicados.

### UI

- Pestaña "Libres" idéntica a Citas/Vacunas/Convenios: tabla, selección
  por clic, botón Enviar global, doble clic para ver mensaje.
- Sin panel lateral ni workspace. La tabla ocupa todo el ancho.
- Si no hay clientes libres, la tabla muestra un mensaje con instrucciones.
- Si hay plantilla activa, se muestra un aviso arriba de la tabla con el
  nombre y un enlace "Cambiar".
- **Botón "Gestionar plantillas"** visible solo en esta pestaña. Abre un
  modal con lista + editor + botón "Usar esta plantilla".
- **Reset Recordatorios** siempre visible en la barra de herramientas
  (junto a "Gestionar plantillas" en Libres).

### Reglas

1. Reset NO borra plantillas. Solo se borran con el botón 🗑 del modal.
2. El "enviado" se marca por mensaje exacto. Cambiar de plantilla hace
   que los clientes vuelvan a aparecer como pendientes.
3. La plantilla activa vive en `localStorage` y se pasa por query param.
4. El botón "Gestionar plantillas" solo es visible en la pestaña Libres.
5. El Excel incluye 4 hojas: Citas, Vacunas, Convenios, Libres. La hoja
   Libres refleja la plantilla activa.
6. El parser de Excel de clientes acepta nombre + múltiples columnas de
   teléfono, limpia formatos sucios y descarta números inválidos
   (< 7 dígitos).

---

## 19. Cuentas por Cobrar (`/cuentas_por_cobrar`)

Módulo para gestionar la cobranza de adeudos de clientes. Importa el
listado de deudas de QVET (Excel), agrupa por cliente, permite
registrar gestiones de cobranza (bitácora), enviar WhatsApp con
plantillas configurables, y marcar clientes como institucionales
(cobranza por administración) o convenio (cobranza por convenio de
pago).

### 19.1. Modelo de datos

Cinco tablas en SQLite:

**`cpc_clientes`** (una fila por cliente deudor, agrupado por `IDCLIENTE`):
- `idcliente_qvet` (UNIQUE) — llave natural del Excel de QVET.
- `nombre`, `telefono`, `email`, `rfc`, `sucursal`.
- `telefono_origen`, `email_origen` — `'qvet'` o `'manual'` (política C).
- `es_institucional`, `es_convenio`, `convenio_folio`.
- `monto_total`, `monto_cobrado`, `saldo`, `n_albaranes`.
- `fecha_mas_antigua`, `dias_antiguedad`, `semaforo`.
- `estado`, `prioridad`, `ultimo_contacto`, `proximo_contacto`.
- `notas_internas` (solo admin).
- `importado_en`, `actualizado_en`.

**`cpc_albaranes`** (una fila por albarán adeudado):
- `codigo_albaran` (UNIQUE), `num_albaran`, `idmascota_qvet`,
  `paciente`, `nhc`, `fecha_albaran`, `fecha_factura`,
  `numero_factura`, `observaciones_factura`.
- `total_importe`, `cobrado_linea`, `a_cuenta`, `vales`, `deuda`.
- `cpc_cliente_id` (FK con `ON DELETE CASCADE`).

**`cpc_bitacora`** (una fila por intento de contacto):
- `cpc_cliente_id` (FK), `fecha`, `hora`.
- `tipo_contacto` (llamada, whatsapp, email, visita, sms, otro).
- `resultado` (sin_respuesta, contestado, buzon, numero_equivocado,
  promesa_pago, pago_realizado, no_le_interesa, disputa,
  verificado_en_qvet, es_convenio, institucional).
- `promesa_fecha`, `promesa_monto`, `observaciones`, `usuario`.
- `adjunto` (ruta, reservado para Bloque 4 — no implementado).

**`cpc_adjuntos`** (reservada para Bloque 4 — no implementada).

**`cpc_importaciones`** (historial de cargas de Excel):
- `archivo`, `fecha`, `filas_leidas`, `clientes_nuevos`,
  `clientes_actualizados`, `albaranes_nuevos`,
  `albaranes_actualizados`, `omitidos`.

### 19.2. Estructura de archivos
core/cuentas_por_cobrar/
init.py
parser_qvet.py # parseo del Excel de QVET
calculos.py # semáforo, antigüedad, normalización
config.py # carga/guarda cuentas_por_cobrar_config.json
bitacora.py # CRUD + verificación QVET obligatoria
cruce_convenios.py # cruce con la tabla convenios
whatsapp.py # renderizado de plantillas + URL wa.me

routers/cuentas_por_cobrar.py # ~15 endpoints

templates/cuentas_por_cobrar.html

json/cuentas_por_cobrar_config.json # NO va a git
uploads/cpc/ # NO va a git


### 19.3. Endpoints

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/cuentas_por_cobrar` | Página principal. |
| GET | `/cuentas_por_cobrar/datos` | JSON con filas + totales. Acepta `estado`, `semaforo`, `prioridad`, `desde`, `hasta`, `q`, `solo_vencidas`, `incluir_institucionales`, `incluir_convenios`, `rol`. |
| GET | `/cuentas_por_cobrar/{cid}` | Detalle del cliente + albaranes + bitácora + `tiene_promesa_vigente`. |
| POST | `/cuentas_por_cobrar/importar` | Sube Excel de QVET, parsea, upsert, cruza convenios. |
| POST | `/cuentas_por_cobrar/reverificar-convenios` | Cruza todos los clientes contra convenios. |
| POST | `/cuentas_por_cobrar/{cid}/reverificar-convenio` | Cruza un cliente puntual. |
| POST | `/cuentas_por_cobrar/{cid}/estado` | Cambia estado, prioridad, próximo contacto, notas internas, teléfono, email, RFC. |
| POST | `/cuentas_por_cobrar/{cid}/bitacora` | Agrega entrada a bitácora. |
| POST | `/cuentas_por_cobrar/{cid}/verificar-qvet` | Registra "verificado en QVET". |
| POST | `/cuentas_por_cobrar/{cid}/institucional` | Marca/desmarca institucional. |
| POST | `/cuentas_por_cobrar/limpiar-basura` | Elimina clientes basura (ID inválido o sin albaranes, sin bitácora). |
| GET | `/cuentas_por_cobrar/plantillas` | Lista plantillas WhatsApp. |
| POST | `/cuentas_por_cobrar/plantilla-activa` | Guarda plantilla activa en config. |
| GET | `/cuentas_por_cobrar/{cid}/whatsapp?plantilla=X` | Devuelve `{url, mensaje, telefono, plantilla}`. |
| POST | `/cuentas_por_cobrar/{cid}/whatsapp-enviado` | Registra en bitácora que se envió WhatsApp. |

### 19.4. Flujo de importación

1. Sube el Excel de QVET (botón "Importar Excel").
2. `parser_qvet.py` detecta encabezado por columnas (`IDCLIENTE`,
   `CODIGO ALBARAN`), tolera fechas con/sin hora, agrupa por
   `IDCLIENTE`, omite fila de totales.
3. `_upsert_cliente` hace upsert por `idcliente_qvet`. En clientes
   existentes **NO pisa**: `es_institucional`, `es_convenio`, `estado`,
   `prioridad`, `notas_internas`, `telefono` (si origen `manual`),
   `email` (si origen `manual`).
4. Albaranes que ya no vienen en el Excel → `deuda = 0`.
5. Recalcula `saldo` de todos los clientes.
6. **Cruce con convenios PRIMERO** (para que no se pisen a pagado).
7. Clientes con saldo 0 → `pagado` (excepto institucional, convenio,
   cancelado, disputa).
8. Registra la importación en `cpc_importaciones`.

### 19.5. Estados de un cliente

- `pendiente` — recién importado, sin gestionar.
- `asignada` — asignado a recepción para cobranza.
- `contactado` — ya se contactó (requiere verificación QVET previa).
- `promesa_pago` — el cliente prometió pagar (requiere verificación QVET).
- `pagado` — saldo 0 (automático o manual).
- `no_localizado` — no se pudo contactar.
- `disputa` — el cliente disputa el adeudo.
- `cancelado` — adeudo cancelado por admin.
- `institucional` — cobranza por administración (no recepción).
- `convenio` — cobranza por convenio de pago activo.

**Estados bloqueados sin verificación QVET:** `contactado`,
`promesa_pago`, `pagado`. El primer registro de bitácora con
`resultado='verificado_en_qvet'` desbloquea estos estados.

### 19.6. WhatsApp

Plantillas configurables en `cuentas_por_cobrar_config.json`:

- `recordatorio_amable` — primer contacto, tono suave.
- `recordatorio_firme` — segundo contacto, tono firme.
- `recordatorio_multi` — cliente con varios albaranes.
- `promesa_seguimiento` — seguimiento de promesa (requiere `promesa_fecha` y `promesa_monto`).
- `convenio_notificacion` — cliente con convenio activo.

Placeholders: `{cliente}`, `{saldo}`, `{mascota}`, `{dias}`,
`{n_albaranes}`, `{promesa_fecha}`, `{promesa_monto}`.

Al enviar WhatsApp:
1. Se abre `wa.me` en pestaña nueva.
2. El mensaje se copia al portapapeles.
3. Se registra automáticamente en bitácora (tipo `whatsapp`, resultado vacío).
4. Se recarga el modal para ver la nueva entrada.

**Plantilla activa:** `localStorage` (`vetsuite.cpc.plantilla_activa`) + config server-side.

**Validación:** `promesa_seguimiento` requiere que el cliente tenga
una promesa de pago vigente (`promesa_fecha >= hoy`, `promesa_monto > 0`).
Si no, el backend rechaza el envío con 400.

**Bloqueos del botón WhatsApp:**
- Cliente institucional → deshabilitado.
- Cliente con convenio activo → deshabilitado.
- Cliente sin teléfono → deshabilitado.

### 19.7. Permisos por rol

Dos roles: `admin` y `recepcion`.

**Selector de rol:** `<select>` nativo en la barra superior. Se guarda
en `localStorage` (`vetsuite.rol`) y se manda al backend como query
param `rol` en `/datos`.

**Recepción NO ve:**
- Botón "Importar Excel".
- Botón "Limpiar basura".
- Botón "Reverificar convenios".
- Checkbox "Ver institucionales".
- Notas internas en el modal.
- Botón "Marcar como institucional".
- Clientes institucionales (filtrados en backend).
- Clientes con convenio (filtrados en backend).

**Nota:** el rol es cosmético (no hay autenticación real). Un usuario
malicioso podría mandar `rol=admin` y saltarse la restricción. Para
permisos reales se necesita autenticación (login, sesión, IP-based).
Pendiente para sesión futura.

### 19.8. Configuración — `cuentas_por_cobrar_config.json`

```json
{
  "institucionales": ["CLINICA BAALAK .", "..."],
  "semaforo": {"verde_max": 30, "amarillo_max": 60, "naranja_max": 90},
  "dias_por_vencer": 7,
  "plantillas_whatsapp": { ... },
  "plantilla_activa": "recordatorio_amable",
  "adjuntos": {"max_mb": 5, "retencion_dias": 365, "tipos_permitidos": [...]},
  "reporte_pdf": {"cliente": "Baalak Veterinaria", "logo": "static/logo.png", "firmas": [...]},
  "roles": {"recepcion": [...], "admin": ["*"]}
}

19.9. Pendientes del módulo
Adjuntos en bitácora (Bloque 4): capturas de WhatsApp o
comprobantes de pago. Límite 5 MB, retención 365 días.

Categorías adicionales (colaborador): migrar de
es_institucional (booleano) a categoria (texto:
normal | institucional | colaborador | convenio).

Reportes con árbol (Año → Mes → Estado → Cliente): consistencia
visual con Convenios, Ingresos, Egresos, Corte, Servicios Externos.

Excel de exportación (3 hojas: Clientes, Albaranes, Bitácora).

Reporte PDF de cobranza (formato carta con firmas).

Autenticación real (login, sesión, IP-based) para que el rol no
sea cosmético.

19.10. Reglas del módulo
101. v0.10.x: Cuentas por Cobrar agrupa por `IDCLIENTE` (llave natural
     del Excel de QVET). Un cliente puede tener N albaranes.
102. v0.10.x: Los albaranes se guardan en `cpc_albaranes` con upsert por
     `codigo_albaran`. Reimportar no duplica; actualiza montos.
103. v0.10.x: Reimportar NO pisa `es_institucional`, `es_convenio`,
     `estado`, `prioridad`, `notas_internas`, ni `telefono`/`email` si
     su origen es `manual`.
104. v0.10.x: Si un albarán ya no aparece en el Excel, se marca
     `deuda = 0` y `cobrado_linea = total_importe`. NO se borra.
105. v0.10.x: Si un cliente desaparece del Excel, queda con `saldo = 0`
     y `estado = 'pagado'`. NO se borra.
106. v0.10.x: Los clientes institucionales (lista configurable) se
     marcan automáticamente en el INSERT. En reimportaciones, se
     respeta el valor manual.
107. v0.10.x: Al importar se cruza contra `convenios`. Si hay convenio
     activo (`firmado` o `impreso`), `es_convenio = 1` y
     `estado = 'convenio'` (excepto si ya estaba en `pagado`,
     `cancelado` o `disputa`).
108. v0.10.x: El primer registro de bitácora con
     `resultado='verificado_en_qvet'` es obligatorio antes de marcar
     `contactado`, `promesa_pago` o `pagado`.
109. v0.10.x: `pago_realizado` en bitácora NO cambia montos. Solo
     sugiere al admin marcar el cliente como pagado.
110. v0.10.x: El semáforo de antigüedad (verde/amarillo/naranja/rojo)
     se configura en `cuentas_por_cobrar_config.json`.
111. v0.10.x: La plantilla `promesa_seguimiento` requiere que el cliente
     tenga una promesa de pago vigente registrada en la bitácora.
112. v0.10.x: El botón "Enviar WhatsApp" se deshabilita si el cliente
     es institucional, tiene convenio activo, o no tiene teléfono.
113. v0.10.x: Al enviar WhatsApp, se registra automáticamente una
     entrada en bitácora con tipo='whatsapp' y resultado='' (vacío).
114. v0.10.x: La plantilla activa vive en localStorage
     (`vetsuite.cpc.plantilla_activa`) y en el config server-side.
115. v0.10.x: El selector de rol es un `<select>` nativo (no dropdown de
     Bootstrap). Los valores son `admin` y `recepcion`.
116. v0.10.x: El rol se guarda en localStorage (`vetsuite.rol`) y se
     manda al backend como query param `rol`.
117. v0.10.x: Recepción no ve los botones de admin, ni las notas
     internas, ni el botón de institucional. El backend filtra
     `es_institucional = 0` y `es_convenio = 0` para recepción.
118. v0.10.x: El rol es cosmético (no hay autenticación real). Para
     permisos reales se necesita autenticación (login, sesión,
     IP-based). Pendiente para sesión futura.
119. v0.10.x: El historial de bitácora del modal tiene
     `max-height: 240px` y `overflow-y: auto`. La tabla de albaranes
     tiene `max-height: 220px`. El modal completo usa `height: 85vh`
     con header y footer fijos.
120. v0.10.x: Los badges con fondo de color (`bg-primary`, etc.)
     requieren `text-white` explícito para que el texto se lea.