# VetSuite Web — Contexto del proyecto

Versión: v0.7
Última actualización: 2026-11-04

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
10. Cómo trabajar
11. Reglas de la versión web
12. Reglas de git
13. Pendientes

---

## 1. Stack

- Python 3.14 + FastAPI + Uvicorn
- SQLite (vetsuite.db)
- Jinja2 para templates
- Tabler UI (CDN) para el diseño visual (basado en Bootstrap 5)
- openpyxl para Excel (Ingresos, Egresos, Recordatorios, Corte)
- pdfplumber para PDFs de Ingresos
- cfdiclient para el SAT (Egresos)
- IMAP (imaplib) para Gmail (Ingresos)
- HTML + CSS + JS vanilla
- Threads daemon para jobs de larga duración (SAT, Gmail)
- localStorage para persistencia de UI (Recordatorios: tab activo y scroll)

---

## 2. Módulos (estado)

- Ingresos: completo (Gmail → XML+PDF → BD → Excel → ZIP → catálogo → reportes).
- Egresos: completo (SAT → XML → BD → Excel → ZIP → reportes).
- Recordatorios: completo (Excel → mensajes → WhatsApp wa.me → historial).
- Corte Semanal: completo (captura diaria → totales → Excel → cierre de semana → reportes).
- Servicios Externos: completo (captura → filtros → cierre de semana → reportes).
- Catálogo QVET: consulta + edición + agregar (desde /ingresos/catalogo).
- Reportes (árbol): modal en Ingresos, Egresos, Corte Semanal y Servicios Externos.
- Estética y Transportes: no se incluye en la web.

---

## 3. Estructura del proyecto

Archivos en la raíz:

- main.py — FastAPI app + routers
- db.py — SQLite + init_db() + migraciones
- jobs.py — gestor de jobs con persistencia
- jobs_state.json — estado persistente de los jobs (NO va a git)
- uploads_manager.py — rutas de Ingresos
- correo_facturas.py — descarga IMAP de Gmail
- correo_utils.py — agrupar XML+PDF por correo
- lector_facturas.py — parser XML+PDF de Ingresos
- excel_web.py — generador de Excel de Ingresos
- zip_generador.py — ZIP mensual de Ingresos
- reparar_archivos.py — reparación de archivos huérfanos
- limpiar_facturas.py — limpieza de uploads/facturas/
- probar_parser.py — script de prueba del parser de Recordatorios
- regenerar_plantilla.py — regenera la plantilla del Corte desde cero
- requirements.txt

Configuración (NO va a git):

- gmail_config.json
- egresos_config.json
- recordatorios_config.json
- catalogo_qvet.json
- categorias_manuales.json
- proveedores_sucursal.json
- solicitud_sat_activa.json
- servicios_externos_config.json
- vetsuite.db

Paquete egresos/:

- __init__.py
- manager.py — rutas y movimiento de XMLs
- sat_wrapper.py — wrapper de sat/ + config + proveedores
- excel_egresos.py — generador de Excel PUE + PPD

Paquete core/:

- rutas_egresos.py
- sat_historial.py
- rutas_recordatorios.py
- recordatorios/
  - __init__.py
  - sucursales.py
  - historial.py
  - envio.py
  - procesar_excel.py
- corte/
  - __init__.py
  - expr.py — parser seguro de expresiones tipo 2345+679
  - semanas.py — helpers ISO week (lunes a domingo)
  - excel_corte.py — generador del Excel del Corte usando plantilla
- servicios_externos/
  - __init__.py
  - config.py — cargar/guardar listas (conceptos, tipos de pago)
  - parser.py — parseo de "Efectivo 24/10/26" para migración
  - semanas.py — wrapper de core/corte/semanas.py

Paquete routers/:

- ingresos.py — incluye /arbol y /catalogo
- rechazados.py
- egresos.py — incluye /arbol
- recordatorios.py
- config_gmail.py
- uploads.py
- corte.py — Corte Semanal (captura + Excel + cierre + /arbol)
- servicios_externos.py — Servicios Externos (captura + cierre + /arbol)
- admin_ips.py — administración de IPs y permisos

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

Paquete static/:

- style.css

Paquete sat/:

- conversion.py, descarga.py, procesar_xml.py, procesar_completo.py,
  guardar_egresos.py, mover_egresos.py

Paquete config/:

- campos.py — MESES_ES
- config_egresos.py

Carpeta uploads/:

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
- cortes/plantilla_semanal.xlsx — plantilla base (NO va a git)
- cortes/<año>-W<semana> - Semanal Baalak-Prado <Mes>.xlsx — Excel cerrados
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
uploads/recordatorios/ (agenda_importada.json, vacunas_importada.json,
historial_recordatorios.json). La tabla queda como placeholder de la app
de escritorio.

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
2. Descarga de Gmail (no leídos / rango / últimos N días).
3. Procesamiento de cada par XML+PDF: cabecera del XML, productos del PDF, datos_json.
4. Renombrado a <folio>.xml / <folio>.pdf.
5. Organización en uploads/ingresos/<año>/<mes>/<sucursal>/.
6. Sucursal por serie del asunto (S1 → Baalak, Prados → Prado).
7. Reclasificación de productos no catalogados.
8. Excel (/ingresos/excel) con filtros.
9. ZIP mensual con la estructura de escritorio.
10. Reset total del módulo.
11. Reportes: modal con árbol Año → Mes → Sucursal.
12. Catálogo: consulta, edición y agregar productos desde /ingresos/catalogo.

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
8. Botón único de envío/marcar/desmarcar.
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
5. Excel con fórmulas vivas usando plantilla (uploads/cortes/plantilla_semanal.xlsx).
6. Cierre de semana (bloquea la edición, guarda Excel).
7. Reapertura de semana (borra el Excel guardado).
8. Reportes: modal con árbol Año → Semana → Sucursal (ingresos, egresos, utilidad).

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
  con core/corte/expr.py (sin eval).
- Excel desde plantilla (uploads/cortes/plantilla_semanal.xlsx).
- Nombre de hoja: "Sem del <día1> al <día7>".
- Nombre de archivo: "Semanal Baalak-Prado <Mes>.xlsx" (mes del lunes).
- Archivo cerrado: "<año>-W<semana> - Semanal Baalak-Prado <Mes>.xlsx".
- Semana cerrada: POST /corte_semanal/actualizar responde 409.
- Reabrir borra el Excel guardado.
- Excel generado al cerrar, no antes.

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

## 10. Cómo trabajar

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
- Si se corrompen los archivos de Ingresos: python reparar_archivos.py
- Si hay basura en uploads/facturas/: python limpiar_facturas.py

---

## 11. Reglas de la versión web

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

---

## 12. Reglas de git

NO van a git:

- vetsuite.db
- uploads/ (todo)
- gmail_config.json
- egresos_config.json
- recordatorios_config.json
- catalogo_qvet.json
- categorias_manuales.json
- proveedores_sucursal.json
- solicitud_sat_activa.json
- jobs_state.json
- servicios_externos_config.json
- migrar_servicios_externos.py
- migrar_tipos_pago.py
- migrar_recuperacion.py
- Inicineraciones.xlsx (si está en la raíz)

---

## 13. Pendientes

- [ ] Tests automáticos del parser de Recordatorios.
- [ ] Tests automáticos del pipeline de Ingresos y Egresos.
- [ ] Tests automáticos del parser de expresiones del Corte (expr.py).
- [ ] Tests automáticos del generador de Excel del Corte (excel_corte.py).
- [ ] Tests automáticos del módulo Servicios Externos.
- [ ] Tests automáticos del árbol de reportes de Corte Semanal.
- [ ] Documentación de instalación en Windows 11.
- [ ] Arranque automático con el sistema (tarea programada).
- [ ] Endpoint /egresos/zip con filtro por rango de fechas (hoy solo por mes).
- [ ] Rotación de snapshots del SAT (borrar los de más de 6 meses).
- [ ] Manejo de XMLs tipo E (notas de crédito) y P (complementos de pago).
- [ ] Limpiar print() de debug en sat/descarga.py (líneas 142-146).
- [ ] Revisar iicio.txt (archivo huérfano) y borrarlo.
- [ ] Pruebas del usuario final en Ingresos, Egresos y Recordatorios.
- [ ] Filtros en vivo (server-side con debounce) en Ingresos y Egresos
      (evaluado y descartado por ahora; el modal de reportes cubre la
      necesidad).
- [ ] Validación más estricta al cerrar la semana del Corte (que las 7
      fechas tengan datos o que los totales cuadren).
- [ ] Exportar el Excel del Corte también como PDF.
- [ ] Historial de cierres del Corte (lista de semanas cerradas).
- [ ] Exportar a Excel desde Servicios Externos (opcional).
- [ ] Historial de semanas cerradas en Servicios Externos.