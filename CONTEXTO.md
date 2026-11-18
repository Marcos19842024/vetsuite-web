# VetSuite Web — Contexto del proyecto

Versión: v0.9.x
Última actualización: 2026-11-17

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
- Threads daemon para jobs de larga duración (SAT, Gmail)
- localStorage para persistencia de UI (Recordatorios: tab activo y scroll)

---

## 2. Módulos (estado)

- Ingresos: completo (Gmail → XML+PDF → BD → Excel → ZIP → catálogo → reportes → visor PDF/XML → filtro de fechas por header Date).
- Egresos: completo (SAT → XML → BD → Excel → ZIP → reportes).
- Recordatorios: completo (Excel → mensajes → WhatsApp wa.me → historial).
- Corte Semanal: completo (captura diaria → totales → Excel → cierre de semana → reportes → observaciones por celda).
- Servicios Externos: completo (captura → filtros → cierre de semana → reportes).
- Catálogo QVET: consulta + edición + agregar (desde /ingresos/catalogo).
- Reportes (árbol): modal en Ingresos, Egresos, Corte Semanal y Servicios Externos.
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
- jobs.py — gestor de jobs manuales (SAT, Gmail)
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
  - sucursales.py
  - historial.py
  - envio.py
  - procesar_excel.py
- servicios_externos/
  - __init__.py
  - config.py — cargar/guardar listas (conceptos, tipos de pago)
  - parser.py — parseo de "Efectivo 24/10/26" para migración
  - semanas.py — wrapper de core/corte_semanal/semanas.py

- core/recordatorios/
  - __init__.py
  - sucursales.py
  - historial.py
  - envio.py
  - procesar_excel.py
  - convenios_cache.py       # carga/guardado de convenios_importada.json
  - convenios_generator.py   # lógica de generación de mensajes

- convenios/
  - __init__.py
  - numero_a_letras.py — conversor de monto numérico a letra
  - helpers.py — folio, búsqueda de factura, contraseña, alertas

Paquete routers/:

- ingresos.py — incluye /arbol, /catalogo, /ver-pdf, /ver-xml, /reclasificar-sucursales
- rechazados.py
- egresos.py — incluye /arbol
- recordatorios.py
- config_gmail.py
- uploads.py
- corte_semanal.py — Corte Semanal (captura + Excel + cierre + /arbol + obs por celda)
- servicios_externos.py — Servicios Externos (captura + cierre + /arbol)
- admin_ips.py — administración de IPs y permisos (prefix /admin)

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
- config_egresos.json (si existe)
- egresos_config.json
- gmail_config.json
- ip_permisos.json
- jobs_state.json
- observaciones_egresos.json (si existe)
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
- recordatorios/historial_recordatorios.json
- recordatorios/reportes/
- corte_semanal/plantilla_semanal.xlsx — plantilla base (NO va a git)
- corte_semanal/<año>-W<semana> - Semanal Baalak-Prado <Mes>.xlsx — Excel cerrados
- correos_procesados.json
- logs/
- uploads/recordatorios/
  - agenda_importada.json
  - vacunas_importada.json
  - convenios_importada.json    # v0.9.x: mensajes de convenios
  - historial_recordatorios.json
  - reportes/

- convenios.py — Convenios de Pago (captura + pagos + impresión + alertas)
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
uploads/recordatorios/. La tabla queda como placeholder de la app de
escritorio.

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
    estado TEXT NOT NULL DEFAULT 'abierta', -- abierta | cerrada
    cerrado_en TEXT,
    total_pendiente REAL NOT NULL DEFAULT 0,
    total_pagado REAL NOT NULL DEFAULT 0,
    n_registros INTEGER NOT NULL DEFAULT 0,
    UNIQUE(anio, semana)

---

## 5. Flujos por módulo

### Ingresos

1. Config Gmail (/config/gmail, modal en /ingresos).
2. Descarga de Gmail (no leídos / rango / últimos N días). El filtro de fechas se aplica en Python sobre el header `Date:`, no con `SINCE`/`BEFORE` de IMAP (Gmail los ignora).
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

1. Importar Excel (citas y/o vacunas) desde el modal.
2. Detección de tipo por columnas del encabezado.
3. Expansión de abreviaturas, omisión de referidos, normalización de teléfonos.
4. Agrupación de clientes por teléfono.
5. Generación de mensajes con reglas de agrupación inteligente.
6. UI con dos tabs (Citas / Vacunas) con persistencia en localStorage.
7. Selección por clic en la fila (radio oculto interno).
8. Botón único de envío/marcar/desmarcar con iconos Tabler (`ti-brand-whatsapp-filled` / `ti-x`).
9. Modal de mensaje propio (independiente de Bootstrap JS).
10. Cambio de sucursal automático (regenera mensajes no enviados).
11. Envío por WhatsApp vía wa.me.
12. Historial de envíos (historial_recordatorios.json).
13. Exportar Excel.
14. Reset del módulo.

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

- Convenios de Pago: completo (captura → pagos → impresión Carta → alertas de vencimiento → bloqueo con contraseña).
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
- Abre dialog id modal-reportes con árbol
  Año → Mes → Semana → Concepto → Estado.
- Datos vienen de GET /servicios_externos/arbol.
- Clic en semana: navega a esa semana.
- Clic en concepto: navega a esa semana y filtra por concepto.
- Clic en estado (Pagado / Pendiente): navega a esa semana y filtra por estado.

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

## 9.1 Recordatorios de Convenios (integración)

El módulo de Recordatorios incluye una **tercera pestaña "Convenios"**
que muestra los mensajes generados automáticamente para convenios
vencidos o por vencer, y permite enviarlos por WhatsApp con el mismo
flujo que Citas y Vacunas.

## 9.2 Convenios de Pago (/convenios)

Módulo de reconocimiento de deuda con plan de pagos, impresión Carta y
seguimiento de pagos con bloqueo por contraseña cuando hay pagos
efectuados.

### Modelo de datos

Tres tablas:

- `convenios` — cabecera (folio, fecha, propietario, teléfono,
  dirección, mascota, NHC, monto_total, monto_letra, fecha_vencimiento,
  lugar_pago, cuenta_bancaria, notas, estado).
- `convenios_pagos` — un pago por fila (convenio_id, numero, fecha,
  importe, efectuado, fecha_pago, albaran, factura_numero,
  factura_uuid, tipo_pago, pagado_con_tarjeta).
- `convenios_alertas_vistas` — marca de "visto hoy" por convenio.

### Estados

`borrador` → `impreso` → `firmado` → `pagado` → `cancelado`.

### Reglas

1. Los convenios **no llevan IVA** (servicios médicos veterinarios
   exentos).
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
9. Doble clic en fila del listado abre editar. Botones de la fila
   tienen `event.stopPropagation()`.
10. La celda de vencimiento se pinta rojo (`celda-vencida`) o amarillo
    (`celda-por-vencer`) según el estado, con los días debajo.
11. El módulo `"convenios"` debe estar en `ip_permisos.json`.
12. El conversor `numero_a_letras` trabaja con centavos enteros para
    evitar errores de punto flotante.
13. Filtros híbridos: `estado`/`desde`/`hasta` server-side, `q`
    client-side con debounce 150ms. El `q` viaja en la URL como hidden.
14. El Excel de convenios respeta los mismos filtros que el listado.

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
  Respeta los filtros híbridos del listado.
- Clic en **año** o **mes**: solo expande/colapsa (no navega).
- El endpoint manda `Cache-Control: no-store`.
- Los estilos se reutilizan de Egresos / Servicios Externos
  (`.arbol-reportes`, `.nodo-sucursal-btn`, `.nodo-hoja`).
- `window.abrirModalReportes = abrirModalReportes` al final del
  `<script>`.

### Generación

- Un **job diario** (thread daemon en `shared/jobs_convenios.py`) corre
  a la hora configurada en `json/convenios_config.json` →
  `recordatorios.hora` (default `08:00`).
- Si la app estaba apagada a esa hora, el job corre al arrancar (si ya
  pasó la hora y no se generó hoy).
- El job recorre los convenios con `estado NOT IN ('pagado', 'cancelado')`
  y `fecha_vencimiento != ''`.
- Calcula el saldo pendiente (`monto_total - suma de pagos efectuados`).
  Si `pendiente <= 0.01`, lo salta.
- Calcula `dias = fecha_vencimiento - hoy`:
  - `dias < 0` → tipo `vencido`.
  - `0 <= dias <= dias_por_vencer` → tipo `por_vencer`.
  - `dias > dias_por_vencer` → no genera.
- Genera el mensaje y lo inserta en `uploads/recordatorios/convenios_importada.json`
  con un `id` único `conv-<cid>-<YYYY-MM-DD>` (evita duplicados del mismo día).
- **No envía nada solo.** Solo prepara los mensajes. El envío es manual
  desde la pestaña Convenios.

### Mensajes

**Vencido:**
Hola {propietario}, le saludamos de Clínica Veterinaria Baalak.
Le recordamos que tiene un convenio de pago pendiente por {mascota}
con saldo de ${pendiente}, que venció el {fecha_vencimiento}.
Le agradecemos pasar a recepción o comunicarse para regularizar.

**Por vencer:**
Hola {propietario}, le saludamos de Clínica Veterinaria Baalak.
Le recordamos que tiene un convenio de pago pendiente por {mascota}
con saldo de ${pendiente}, que vence el {fecha_vencimiento}.
Le agradecemos pasar a recepción o comunicarse para regularizar.


### Estructura del JSON (`convenios_importada.json`)

    {
      "generado_en": "2026-11-16T08:00:00",
      "items": [
        {
          "id": "conv-2-2026-11-16",
          "convenio_id": 2,
          "folio": "CONV-2026-0001",
          "tipo": "vencido",
          "propietario": "...",
          "mascota": "...",
          "telefono": "...",
          "monto_total": 3000.0,
          "pagado": 0.0,
          "pendiente": 3000.0,
          "fecha_vencimiento": "2026-11-10",
          "dias": 6,
          "mensaje": "...",
          "enviado": false,
          "descartado": false,
          "hash": "...",
          "generado_en": "..."
        }
      ]
    }

### Endpoints nuevos en `/recordatorios`

| Método | Ruta | Función |
|---|---|---|
| GET | `/recordatorios/convenios/whatsapp/{idx}` | URL + mensaje |
| POST | `/recordatorios/convenios/marcar/{idx}` | Marca enviado |
| POST | `/recordatorios/convenios/desmarcar/{idx}` | Desmarca |
| POST | `/recordatorios/convenios/descartar/{idx}` | Descarta (no se regenera hoy) |
| POST | `/recordatorios/convenios/regenerar` | Fuerza la generación manual |

### Configuración

En `json/convenios_config.json`:

    {
      "recordatorios": {
        "activo": true,
        "hora": "08:00",
        "dias_por_vencer": 3
      }
    }

- `activo`: si es `false`, el job no corre.
- `hora`: hora local a la que corre el job (formato 24h).
- `dias_por_vencer`: cuántos días antes del vencimiento se genera el
  recordatorio (mismo parámetro que usan las alertas visuales).

### Reglas de la integración

1. **El job corre en un thread daemon**, separado del gestor
   `shared/jobs.py` (que es para jobs manuales con progreso como SAT y
   Gmail). No comparten estado.
2. **Un mensaje por convenio por día.** El `id` con fecha lo garantiza.
   Al día siguiente, si sigue vencido, se genera uno nuevo.
3. **El `reset` de Recordatorios borra también `convenios_importada.json`**.
4. **Los mensajes descartados no se regeneran hoy.** El `descartado: true`
   se respeta hasta el día siguiente.
5. **El historial de envíos** usa el mismo `historial_recordatorios.json`
   con `tipo="convenios"`. `ya_fue_enviado` y `marcar_enviado` son
   genéricos y funcionan sin cambios.
6. **El botón único Enviar/Desmarcar** de la barra superior funciona
   igual para las tres pestañas (Citas, Vacunas, Convenios), porque el
   JS es genérico sobre `data-tipo` y `data-idx`.
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
2. Luego, por cada clave en `obs_celdas_json`, se formatea el texto con
   `_formatear_obs_celda(campo, sub, valor, texto)`:
   - Egreso → `Gasto de $X: <texto>`
   - Colaboradores → `Deuda de $X: <texto>`
3. Se unen con `\n`.

Si el usuario **borra** el textarea y guarda, la clave se elimina del JSON
y la línea desaparece de `observaciones`.

Si el usuario **cambia el monto** de la celda, la cantidad en el texto se
**recalcula automáticamente** (porque se relee el valor fresco), pero el
texto que escribió se conserva.

### Frontend

- `<dialog id="modal-celda">` tiene un bloque `#modal-celda-obs-wrap`
  (oculto por default) con `<textarea id="modal-celda-obs">`.
- `abrirModal(td)` decide si mostrarlo según `campo`/`subcampo`.
- `aplicarModal()` manda `obs` en el payload de `/actualizar`.
- `guardarRaw(payload)` manda el payload completo (ya no filtra campos).
- El tab Observaciones usa `<textarea class="corte-obs">` (no `<input>`)
  para que los `\n` se rendericen como saltos de línea reales.
- Auto-resize en el textarea (crece según contenido).

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
  filtre por fecha en el servidor. `after:`/`before:` son exclusivos,
  así que se manda `after:<desde - 1 día>` y `before:<hasta + 1 día>`
  para que el rango sea inclusivo.
- **No se usa** `SINCE`/`BEFORE` de IMAP estándar. Gmail los ignora
  o los aplica sobre `INTERNALDATE` (fecha de entrega), no sobre el
  header `Date:`.
- El `search` de IMAP combina `UNSEEN` (si aplica), `FROM` (si aplica)
  y `X-GM-RAW` (si hay rango de fechas).
- **Filtro de precisión en Python** (v0.9): se conserva el filtro por
  header `Date:` con `parsedate_to_datetime`. Razón: `X-GM-RAW` usa
  la fecha interna de Gmail, que puede diferir del header en correos
  reenviados o migrados.
- El filtro Python se aplica **antes** del chequeo de caché y del
  filtro de remitente, para descartar correos fuera de rango temprano.
- `info["omitidos_fecha"]` cuenta los correos descartados por fecha.
  Con el pre-filtro `X-GM-RAW` activo, este contador debería ser ~0
  en condiciones normales (solo sube si hay desfase fecha interna vs
  header `Date:`).
- El log del job muestra `Fuera de rango (fecha < >). Se omite. Asunto: ...`.
- **Fallback**: si `X-GM-RAW` no está disponible (proveedor no Gmail),
  el `search` reintenta sin ese criterio y cae al comportamiento
  anterior (traer todo y filtrar en Python).

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
- Resumen: `Reclasificadas: N | Sin XML: M | Errores: K`.

### Regex de serie tolerante

El regex en `correo_facturas.py` para extraer la serie del asunto es:

    r"\b(S1|PRADOS?)\b[\/\s\-]*(\d+)"

Captura:
- `S1/08511-8363` → `S1` + `8511`
- `Prados/00265-264` → `PRADOS` + `265`
- `prados268-267` → `PRADOS` + `268`
- `PRADOS 270-269` → `PRADOS` + `270`
- `S1/8527` → `S1` + `8527`

Normaliza `PRADO` → `PRADOS`. Quita ceros a la izquierda. Si no encuentra
serie conocida, cae a un regex genérico `([A-Za-z0-9]+)\s*-\s*(\d+)`.

---

## 12. UI: iconos, sidebar, tabla full-height (v0.9)

### Tabler Icons

Se reemplazaron los emojis del sidebar y botones por iconos de Tabler:

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
| Permisos IP (sidebar) | shield-lock | `ti-shield-lock` |
| Brand (VetSuite) | paw | `ti-paw` |
| Descargar de Gmail | mail o download | `ti-mail` / `ti-download` |
| Ver registros | eye o list | `ti-eye` / `ti-list` |
| Exportar Excel | file-excel | `ti-file-excel` |
| Enviar WhatsApp | brand-whatsapp-filled | `ti-brand-whatsapp-filled` |
| Desmarcar (WhatsApp) | x | `ti-x` |
| Reset | trash o refresh | `ti-trash` / `ti-refresh` |

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

- La URL real es `/admin/ips` (con slash), pero el nombre interno del
  módulo es `"admin_ips"` (con guion bajo).
- El `startswith` en `base.html` debe comparar contra la **URL**, no contra
  el nombre interno:

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

- En `ingresos.html`, el card de la tabla lleva la clase `tabla-full`.
- Solo aplica a Ingresos. Otras páginas conservan su `tabla-scroll` original.

### Doble clic en fila de Ingresos

- El `<tr>` lleva `data-id="{{ r.id }}"` y `style="cursor: pointer;"`.
- `dblclick` normal → abre `/ingresos/ver-pdf/{id}` en pestaña nueva.
- `Ctrl/Cmd + dblclick` → abre `/ingresos/ver-xml/{id}`.

---

## 13. Cómo trabajar

- Arrancar: uvicorn main:app --reload --host 127.0.0.1 --port 8000
- Probar: http://127.0.0.1:8000/ingresos, /egresos, /recordatorios,
  /corte_semanal, /servicios_externos, /ingresos/catalogo
- Probar parser de Recordatorios: python probar_parser.py archivo.xlsx
- La BD está en vetsuite.db (no va a git).
- Los archivos de uploads/ no van a git.
- Configs que NO van a git: gmail_config.json, egresos_config.json,
  recordatorios_config.json, catalogo_qvet.json, categorias_manuales.json,
  proveedores_sucursal.json, solicitud_sat_activa.json, jobs_state.json,
  servicios_externos_config.json.
- Si se corrompen los archivos de Ingresos: python scripts/reparar_archivos.py
- Si hay basura en uploads/facturas/: python scripts/limpiar_facturas.py
- Si uvicorn no recarga un cambio de CSS/JS, forzar recarga en el navegador
  con Ctrl+Shift+R (Cmd+Shift+R en Mac). Un `304 Not Modified` en la
  consola es normal (el archivo no cambió para el navegador).
- Los JSON de configuración viven en `json/`, no en la raíz.
- La carpeta `scripts/` tiene los utilitarios (`reparar_archivos.py`, `limpiar_facturas.py`). Se corren desde la raíz: `python scripts/reparar_archivos.py`.

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
15. Recordatorios persiste en JSON + localStorage (tab y scroll).
16. Los archivos listados en "Cómo trabajar" NO van a git.
17. El catálogo QVET vive en JSON, no en SQLite.
18. El catálogo se filtra client-side.
19. Los árboles de reportes se calculan en el backend (solo agregados).
v0.9.x: el árbol de reportes de Servicios Externos calcula la semana en Python con core.corte_semanal.semanas.semana_de_fecha() (ISO 8601), NO con strftime('%W') de SQLite. La directiva %W de SQLite no es ISO y desfasa una semana respecto al resto del módulo (selector type="week", asegurar_semana, rangoSemana). Todos los árboles de reportes que agrupen por semana deben usar semana_de_fecha().
20. metodo_pago se normaliza a PUE o PPD al insertar.
21. El Corte Semanal usa plantilla, no generación a mano.
22. Los montos del Corte se guardan como TEXT (expresiones 2345+679).
23. El Corte genera el Excel solo al cerrar (o al descargar borrador).
24. Una semana cerrada es inmutable en Corte (409).
25. core/permisos_ip.py reconoce /corte_semanal como módulo "corte".
26. Servicios Externos usa una sola tabla servicios_externos (sin cierre a
    nivel tabla; el cierre es por semana ISO en servicios_semanas).
27. Estado "pendiente" = fecha_pago = ''. Sin columna booleana.
28. tipo_pago se limpia si no hay fecha_pago.
29. tipos_pago vive en servicios_externos_config.json con los valores fijos
    Efectivo, Transferencia, TC, TD.
30. recuperacion es listbox cerrado: Si | No | N/A.
31. Servicios Externos no genera Excel. Es solo control en pantalla.
32. Ruta pública con guion bajo: /servicios_externos. Módulo interno:
    "servicios_externos" en ip_permisos.json.
33. Servicios Externos se cierra por semana ISO (lunes a domingo).
    Semana cerrada es inmutable (409).
34. Al cerrar se guarda snapshot de totales en servicios_semanas.
35. El filtro de semana reemplaza a "Desde/Hasta" en Servicios Externos.
36. La tabla siempre muestra exactamente una semana.
37. El botón eliminar de Servicios Externos vive dentro del modal de
    edición (no en la fila).
38. window.abrirModalReportes se define dentro del IIFE (necesario para
    el onclick del HTML).
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
44. v0.8: el tab Observaciones usa `<textarea>` (no `<input>`) para que
    los `\n` se rendericen como saltos de línea reales.
45. v0.9: el filtro de fechas de Gmail se hace en Python sobre el header
    `Date:` con `parsedate_to_datetime`. NO se usa `SINCE`/`BEFORE` de
    IMAP (Gmail los ignora o los aplica sobre `INTERNALDATE`).
46. v0.9: el `search` de IMAP solo lleva `UNSEEN`, `FROM` y `ALL`.
    Los criterios se pasan como argumentos sueltos (`*criterios`), no
    como un string con paréntesis.
47. v0.9: el filtro de fecha se aplica ANTES del caché y del filtro de
    remitente.
48. v0.9: el regex de serie del asunto es tolerante:
    `\b(S1|PRADOS?)\b[\/\s\-]*(\d+)`. Acepta con/sin `/`, espacio o guion.
49. v0.9: `serie_a_sucursal()` normaliza `PRADO` → `PRADOS` y case.
50. v0.9: el endpoint `/reclasificar-sucursales` solo mueve a Baalak/Prado
    cuando el XML dice `S1` o `Prado(s)`. Otras series no se tocan.
51. v0.9: el visor de archivos (`/ver-pdf/{id}`, `/ver-xml/{id}`) sirve
    `inline` con `Cache-Control: no-store`. Fallback por UUID y por
    cualquier sucursal.
52. v0.9: doble clic en fila de Ingresos abre PDF; Ctrl/Cmd + doble clic
    abre XML.
53. v0.9: el item activo del sidebar compara `request.url.path` (URL),
    NO el nombre interno del módulo. Ej: `/admin` (URL), no `admin_ips`.
54. v0.9: los iconos del sidebar y botones usan Tabler Icons
    (`<i class="ti ti-<nombre>"></i>`), no emojis.
55. v0.9: la tabla de Ingresos usa `.card.tabla-full` + `.tabla-scroll`
    para ocupar el alto restante. Otras páginas conservan su
    `.tabla-scroll` original.
56. v0.9: si uvicorn no recarga CSS/JS, forzar recarga en el navegador.
    Un `304 Not Modified` es normal.
57. v0.9.x: las rutas de archivos se centralizan en `shared/rutas.py`.
    Todo el código importa de ahí en vez de hardcodear
    `Path(__file__).parent / "..."`.
58. v0.9.x: `shared/rutas.py` expone `ROOT`, `JSON_DIR`, `UPLOADS_DIR`,
    `DB_FILE` y una constante por cada JSON de configuración.
59. v0.9.x: los JSON de configuración viven en `json/`. La app los
    lee y escribe ahí.
60. v0.9.x: los módulos transversales (db, jobs, templates_shared,
    uploads_manager, campos) viven en `shared/`.
61. v0.9.x: el pipeline de Ingresos (correo_facturas, correo_utils,
    lector_facturas, excel_web, zip_generador) vive en `ingresos/`.
62. v0.9.x: los scripts de mantenimiento (reparar_archivos,
    limpiar_facturas) viven en `scripts/`.
63.  v0.9.x: la navegación con Enter/Shift+Enter en celdas numéricas del Corte Semanal es tipo Excel: dentro de la misma columna (día)   baja/sube fila por fila, y al llegar al final de la columna salta a la primera (o última, en Shift+Enter) fila editable de la columna siguiente/anterior del mismo bloque. Al terminar la última columna (domingo) pasa al bloque siguiente (Ingresos → Egresos → Por cobrar → Observaciones → ciclo a Ingresos), reset a Lunes fila 1 (o Domingo última fila si es Shift+Enter). Observaciones usa Enter = salto de línea; la navegación entre textareas es con Tab/flechas. No cruza entre sucursales.
64. v0.9.x: el pre-filtro de fecha de Gmail va en `X-GM-RAW` con
    `after:`/`before:`, NO en `SINCE`/`BEFORE` de IMAP estándar
    (Gmail los ignora o los aplica sobre `INTERNALDATE`).
65. v0.9.x: `after:` y `before:` son exclusivos. Para un rango
    inclusivo `[desde, hasta]`, mandar `after:<desde - 1 día>` y
    `before:<hasta + 1 día>`.
66. v0.9.x: el filtro Python por header `Date:` se conserva como
    verificación de precisión (X-GM-RAW usa la fecha interna de Gmail,
    que puede diferir del header en correos reenviados o migrados).
67. v0.9.x: si `X-GM-RAW` no está disponible (proveedor no Gmail),
    reintentar sin ese criterio y caer al comportamiento anterior
    (traer todo y filtrar en Python).
68. v0.9.x: los Convenios de Pago NO llevan IVA (servicios médicos
    veterinarios exentos, art. 41 Reglamento LIVA).
69. v0.9.x: los pagos de convenio se guardan con upsert por `id`. Los
    pagos efectuados nunca se modifican ni se eliminan desde el
    formulario.
70. v0.9.x: si un convenio tiene pagos efectuados, los cambios
    estructurales (monto, fecha, propietario, mascota) se rechazan con
    409 y requieren contraseña para desbloquear.
71. v0.9.x: la impresión de convenios usa iframe oculto con `print()`.
    Fallback a pestaña nueva si el navegador lo bloquea.
72. v0.9.x: la celda de vencimiento del listado de convenios se pinta
    rojo (vencido) o amarillo (por vencer), con los días de atraso o
    restantes debajo de la fecha.
73. v0.9.x: el job de recordatorios de convenios corre en un thread
    daemon en `shared/jobs_convenios.py`, separado de `shared/jobs.py`
    (que es para jobs manuales con progreso).
74. v0.9.x: un mensaje de recordatorio por convenio por día. El `id`
    `conv-<cid>-<YYYY-MM-DD>` lo garantiza. Al día siguiente se genera
    uno nuevo si sigue vencido.
75. v0.9.x: el job no envía nada solo. Solo prepara los mensajes. El
    envío es manual desde la pestaña Convenios de Recordatorios.
76. v0.9.x: el `reset` de Recordatorios borra también
    `convenios_importada.json`.
77. v0.9.x: los mensajes descartados (`descartado: true`) no se
    regeneran el mismo día. Al día siguiente sí.
78. v0.9.x: el historial de envíos de convenios usa
    `historial_recordatorios.json` con `tipo="convenios"`. Es genérico,
    no requiere cambios en `historial.py`.
79. v0.9.x: si la app estaba apagada a la hora configurada, el job de
    convenios corre al arrancar (si ya pasó la hora y no se generó hoy).
80. v0.9.x: el listado de convenios tiene filtros híbridos: estado/fechas
    server-side (query params), búsqueda por texto client-side (debounce
    150ms). El `q` viaja en la URL como hidden.
81. v0.9.x: el Excel de convenios (`/convenios/excel`) respeta los mismos
    filtros que el listado. Dos hojas: Convenios y Pagos.
82. v0.9.x: el UUID de factura se llena desde `ingresos.folio_fiscal` al
    buscar la factura del cliente. Se guarda en
    `convenios_pagos.factura_uuid` y se exporta en el Excel.
83. v0.9.x: el botón eliminar de convenios vive dentro del formulario,
    no en el listado. Solo aparece si está en borrador y sin pagos
    efectuados.
84. v0.9.x: la pestaña Convenios de Recordatorios tiene botones
    "Regenerar" (fuerza la generación) y "Descartar" (marca como
    descartado el seleccionado, no se regenera hoy). Solo visibles en
    esa pestaña.
85. v0.9.x: los `print()` de `sat/descarga.py` son avisos de progreso y
    errores, no debug. No se borran.
86. v0.9.x: múltiples `addEventListener('DOMContentLoaded', ...)` en el
    mismo `<script>` son válidos y se acumulan. No se reemplazan entre
    sí. Solo `element.onclick = fn` sobrescribe.

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
- [ ] Reportes con árbol en Convenios (Año → Mes → Estado) — opcional.
- [ ] Exportar a Excel desde Servicios Externos (opcional).
- [ ] Historial de semanas cerradas en Servicios Externos.
- [ ] Endpoint `/egresos/zip` con filtro por rango de fechas.
- [ ] Rotación de snapshots del SAT (borrar los de más de 6 meses).
- [ ] Manejo de XMLs tipo E (notas de crédito) y P (complementos de
      pago) en Egresos.
- [ ] Validación más estricta al cerrar la semana del Corte.
- [ ] Historial de cierres del Corte (lista de semanas cerradas).

---

## 17. Convenios de Pago (/convenios)

Módulo para generar convenios de pago (reconocimiento de deuda) con el
cliente, imprimirlos en formato Carta y dar seguimiento a los pagos
acordados. Reemplaza el llenado manual del formato en Word/PDF.

### Modelo de datos

**Tabla `convenios`:**

    id INTEGER PRIMARY KEY AUTOINCREMENT,
    folio TEXT UNIQUE,                  -- CONV-<año>-<consecutivo 4 dígitos>
    fecha TEXT NOT NULL,                -- fecha de firma
    propietario TEXT NOT NULL,
    telefono TEXT DEFAULT '',
    direccion TEXT DEFAULT '',
    mascota TEXT DEFAULT '',
    nhc TEXT DEFAULT '',                -- Número de Historia Clínica
    monto_total REAL NOT NULL DEFAULT 0,
    monto_letra TEXT DEFAULT '',        -- generado con numero_a_letras()
    fecha_vencimiento TEXT DEFAULT '',
    lugar_pago TEXT DEFAULT 'recepcion',-- recepcion | transferencia | ambos
    cuenta_bancaria TEXT DEFAULT '',    -- opcional, sobreescribe config
    estado TEXT NOT NULL DEFAULT 'borrador', -- borrador | impreso | firmado | pagado | cancelado
    notas TEXT DEFAULT '',
    creado_en TEXT DEFAULT CURRENT_TIMESTAMP,
    actualizado_en TEXT DEFAULT CURRENT_TIMESTAMP

**Tabla `convenios_pagos`:**

    id INTEGER PRIMARY KEY AUTOINCREMENT,
    convenio_id INTEGER NOT NULL,
    numero INTEGER NOT NULL,            -- 1, 2, 3...
    fecha TEXT NOT NULL,
    importe REAL NOT NULL DEFAULT 0,
    efectuado INTEGER NOT NULL DEFAULT 0,
    fecha_pago TEXT DEFAULT '',
    albaran TEXT DEFAULT '',
    factura_numero TEXT DEFAULT '',
    factura_uuid TEXT DEFAULT '',
    tipo_pago TEXT DEFAULT '',          -- Efectivo | Transferencia | Tarjeta de crédito | Tarjeta de débito | Otro
    pagado_con_tarjeta INTEGER DEFAULT 0,
    FOREIGN KEY (convenio_id) REFERENCES convenios(id) ON DELETE CASCADE

**Tabla `convenios_alertas_vistas`:**

    convenio_id INTEGER NOT NULL,
    fecha_vista TEXT NOT NULL,          -- YYYY-MM-DD
    PRIMARY KEY (convenio_id, fecha_vista)

### Configuración (`json/convenios_config.json`)

    {
      "clinica": {
        "nombre": "Clínica Veterinaria Baalak",
        "mvz": "MVZ. Francisco Julián Gómez Cancino",
        "domicilio": "Av. Central #33 Entre Colosio y Costa Rica",
        "ciudad": "San Francisco de Campeche, Campeche",
        "cuenta_bancaria": ""
      },
      "alertas": { "dias_por_vencer": 3 },
      "seguridad": { "password_hash": "" }
    }

- `password_hash` vacío → modo abierto (no pide contraseña al desbloquear).
- Para activarlo: `python -c "import hashlib; print(hashlib.sha256('TU_CONTRASEÑA'.encode()).hexdigest())"` y pegar el resultado.

### IVA

**Los convenios NO llevan IVA.** Las cirugías veterinarias son servicios
médicos exentos de IVA en México (art. 41 del Reglamento de la Ley del
IVA, aplicable a médicos veterinarios con título y cédula). El monto
total del convenio es el precio del servicio, sin IVA trasladado.
Si el convenio incluyera productos del mostrador, esos sí llevarían
IVA, pero el módulo no hace ese desglose (no es el caso de uso).

### Endpoints

| Método | Ruta | Función |
|---|---|---|
| GET | `/convenios` | Listado + bandeja de alertas |
| GET | `/convenios/nuevo` | Formulario de alta |
| GET | `/convenios/{id}/editar` | Formulario de edición |
| GET | `/convenios/{id}/imprimir` | Vista Carta para imprimir (iframe oculto) |
| GET | `/convenios/numero-a-letras?monto=N` | Convierte monto a letra |
| GET | `/convenios/buscar-cliente?q=&rfc=` | Busca factura del cliente en `ingresos` |
| POST | `/convenios/guardar` | Crear/actualizar (JSON) |
| POST | `/convenios/{id}/estado` | Cambiar estado |
| POST | `/convenios/{id}/pago/{pid}/marcar` | Marcar pago efectuado |
| POST | `/convenios/{id}/eliminar` | Eliminar (solo borrador sin pagos) |
| POST | `/convenios/{id}/alerta-vista` | Marcar alerta como vista |
| POST | `/convenios/verificar-password` | Validar contraseña de desbloqueo |
| GET | `/convenios/excel` | Exportar a Excel (respeta filtros) |

### Flujo

1. `/convenios` → listado con bandeja de alertas de cobranza.
2. Botón **+ Nuevo convenio** → formulario con:
   - Datos del propietario (nombre, RFC, teléfono, dirección).
   - Datos de la mascota (nombre, NHC).
   - Monto total + monto en letra (auto).
   - Fechas del convenio y de vencimiento.
   - Lugar de pago + cuenta bancaria (opcional).
   - **Plan de pagos dinámico**: N pagos, cada uno con fecha, importe,
     efectuado, albarán, factura (con botón de búsqueda) y tipo de pago.
3. Guardar → folio automático `CONV-2026-0001`.
4. Botón 🖨 → carga el template en un iframe oculto y dispara
   `window.print()`. El usuario no ve pestaña nueva.
5. Doble clic en fila del listado → abre editar.
6. Botón **Desbloquear** (solo si hay pagos efectuados) → pide contraseña,
   desbloquea la edición de campos no bloqueados.

### Reglas del módulo

1. **El folio se genera automático**: `CONV-<año>-<consecutivo 4 dígitos>`.
2. **Los pagos se guardan con upsert por `id`**:
   - Si el pago viene con `id` y existe en BD, se actualiza (salvo que
     esté efectuado).
   - Si no viene `id`, se inserta.
   - Si existía en BD y no vino en el payload, se elimina (solo si no
     está efectuado).
   - Los pagos efectuados **nunca se modifican ni se eliminan** desde
     el formulario.
3. **El botón 🗑 del listado** solo aparece si `estado == 'borrador'`
   **y** no hay pagos efectuados.
4. **Cambios estructurales bloqueados** cuando hay pagos efectuados:
   monto total, fecha, propietario y mascota no se pueden modificar
   (409). Requiere contraseña para desbloquear.
5. **Contraseña opcional**: si `password_hash` está vacío, el desbloqueo
   no pide contraseña. En producción debe estar configurada.
6. **La búsqueda de factura** solo vincula facturas a nombre del cliente
   (no público en general). Se busca por RFC primero, luego por nombre.
7. **La detección de pago con tarjeta** se deriva del tipo de pago
   (`Tarjeta de crédito` o `Tarjeta de débito` → `pagado_con_tarjeta=1`).
8. **El IVA no se calcula** (servicios médicos veterinarios exentos).
9. **La impresión** usa un iframe oculto con `print()`. Fallback a
   pestaña nueva si el navegador lo bloquea.
10. **El doble clic en fila** del listado abre editar. Los botones de
    la fila tienen `event.stopPropagation()`.
11. **La celda de vencimiento** se pinta: rojo (`celda-vencida`) si
    vencido, amarillo (`celda-por-vencer`) si por vencer. Debajo de la
    fecha se muestran los días de atraso o los días restantes.
12. **La bandeja de alertas** de la parte superior muestra los convenios
    vencidos y por vencer (según `dias_por_vencer` en config). Se puede
    marcar como vista por día.
13. **El módulo "convenios"** debe estar en `ip_permisos.json` (global y
    por IP que lo necesite).
14. **Filtros híbridos en el listado** (v0.9.x):
    - Server-side: `estado`, `desde`, `hasta` (query params en la URL).
    - Client-side: `q` (búsqueda por texto con debounce 150ms sobre las filas ya cargadas).
    - El `q` viaja en la URL como hidden para preservarse al cambiar los filtros server-side.
    - La URL es compartible: `/convenios?estado=borrador&desde=2026-11-01&hasta=2026-11-30&q=Francisco`.
15. **Exportar a Excel** (v0.9.x):
    - Endpoint: `GET /convenios/excel?estado=&desde=&hasta=&q=`.
    - Respeta los mismos filtros que el listado (server-side + `q` en Python).
    - Dos hojas: "Convenios" (una fila por convenio) y "Pagos" (una fila por pago).
    - Formato de moneda en columnas de importe, encabezados azules, primera fila congelada.
    - Nombre: `Convenios_YYYY-MM-DD_HHMM.xlsx`.
16. **UUID de factura** (v0.9.x):
    - Se llena automáticamente al hacer clic en 🔍 de una fila de pago.
    - `buscar_ingreso_por_cliente()` devuelve `folio_fiscal` del ingreso.
    - Se guarda en `convenios_pagos.factura_uuid`.
    - Se muestra como texto pequeño debajo del número de factura.
    - Se exporta en la hoja "Pagos" del Excel (columna "UUID factura").
17. **Eliminar convenio** (v0.9.x):
    - El botón 🗑 vive dentro del formulario (`convenios_form.html`), no en el listado.
    - Solo aparece si `conv.estado == 'borrador'` y `not tiene_efectuados`.
    - Pide confirmación con `confirm()`.
    - Redirige al listado tras eliminar.
    - El endpoint `POST /convenios/{cid}/eliminar` ya valida las reglas en backend.

## 17. Deuda técnica resuelta (2026-11-17)

### 17.1 Rutas centralizadas

Todos los `Path(__file__)` del proyecto (fuera de `shared/rutas.py` y de
los `scripts/`) fueron reemplazados por constantes de `shared.rutas`:

- `ROOT` — raíz del proyecto (usado en `main.py`, `routers/egresos.py`,
  `routers/rechazados.py`, `core/rutas_recordatorios.py`,
  `core/corte_semanal/excel_corte.py`, `egresos/manager.py`,
  `sat/procesar_xml.py`).
- `CORTE_SEMANAL_DIR` — `uploads/corte_semanal/` (`routers/corte_semanal.py`).
- `SAT_HISTORIAL_DIR` — `uploads/egresos/_sat_historial/` (`core/sat_historial.py`).
- `EGRESOS_DIR` / `EGRESOS_CONTABILIDAD_DIR` — carpetas de Egresos
  (`core/rutas_egresos.py`).
- `CONFIG_EGRESOS` — alias de `EGRESOS_CONFIG` (ver 17.2).

**Excepción:** los `scripts/*.py` conservan su `Path(__file__)` porque es
bootstrap de `sys.path`, no una ruta de datos.

### 17.2 Config de Egresos consolidada

Antes había dos módulos que leían **archivos distintos**:

- `egresos/config_egresos.py` → `json/config_egresos.json` (fantasma).
- `egresos/sat_wrapper.py` → `json/egresos_config.json` (real).

Ahora:

- **Un solo archivo:** `json/egresos_config.json`.
- **Un solo módulo de config:** `egresos/config_egresos.py`.
- `sat_wrapper.py` importa de `config_egresos` y ya no duplica
  `cargar_config`, `cargar_solicitud_activa`, `cargar_proveedores_sucursal`,
  etc.
- `CONFIG_EGRESOS` en `shared.rutas` quedó como alias de
  `EGRESOS_CONFIG` para no romper imports viejos.
- Nuevo helper `get_fiel()` en `config_egresos.py` que devuelve
  `{rfc, cer, key, pwd}` listo para `sat.descarga`.
- `core/sat_historial.py` ahora usa `historial_sat_activo()` de
  `config_egresos.py`, que respeta `VET_SUITE_HISTORIAL=1` además del
  JSON.

### Reglas nuevas

1. Todo `Path(__file__)` de datos vive en `shared/rutas.py`. El resto del
   código importa constantes.
2. `json/egresos_config.json` es el único archivo de config de Egresos.
   `CONFIG_EGRESOS` es alias de `EGRESOS_CONFIG`.
3. `sat_wrapper.py` no lee JSON; solo importa de `config_egresos.py`.
4. `sat_wrapper.py` reexporta `cargar_config`, `guardar_config`,
   `cargar_solicitud_activa`, etc. con alias para compatibilidad.
5. Los `scripts/*.py` conservan su `Path(__file__)` de bootstrap.
6. `core/sat_historial.py` usa `historial_sat_activo()` de
   `config_egresos.py`.