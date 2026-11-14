import json
import sqlite3
from pathlib import Path

from shared.rutas import DB_FILE as DB_PATH

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    cur = conn.cursor()

    # --- INGRESOS ---
    cur.execute("""
    CREATE TABLE IF NOT EXISTS ingresos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha TEXT NOT NULL,
        folio TEXT,
        folio_fiscal TEXT,
        cliente TEXT,
        rfc TEXT,
        total REAL NOT NULL DEFAULT 0,
        sucursal TEXT,
        notas TEXT,
        datos_json TEXT
    )
    """)
    
    # Migración ingresos
    try:
        cols = [r[1] for r in cur.execute("PRAGMA table_info(ingresos)").fetchall()]
        if "datos_json" not in cols:
            cur.execute("ALTER TABLE ingresos ADD COLUMN datos_json TEXT")
    except Exception:
        pass

    # --- EGRESOS ---
    cur.execute("""
    CREATE TABLE IF NOT EXISTS egresos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha TEXT NOT NULL,
        folio TEXT,
        uuid TEXT,
        proveedor TEXT,
        rfc TEXT,
        total REAL NOT NULL DEFAULT 0,
        sucursal TEXT,
        metodo_pago TEXT,
        forma_pago TEXT,
        notas TEXT,
        serie TEXT
    )
    """)
    
    # Migración egresos
    try:
        cols = [r[1] for r in cur.execute("PRAGMA table_info(egresos)").fetchall()]
        if "serie" not in cols:
            cur.execute("ALTER TABLE egresos ADD COLUMN serie TEXT")
    except Exception:
        pass

    # --- RECORDATORIOS ---
    cur.execute("""
    CREATE TABLE IF NOT EXISTS recordatorios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha TEXT NOT NULL,
        hora TEXT,
        cliente TEXT,
        mascota TEXT,
        telefono TEXT,
        tipo TEXT,
        mensaje TEXT,
        enviado INTEGER NOT NULL DEFAULT 0
    )
    """)

    # --- Corte Semanal ---
    conn.execute("""
    CREATE TABLE IF NOT EXISTS cortes_diarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha TEXT NOT NULL,
        sucursal TEXT NOT NULL,
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
        obs_celdas_json     TEXT DEFAULT '{}',
        observaciones       TEXT DEFAULT '',
        creado_en           TEXT DEFAULT CURRENT_TIMESTAMP,
        actualizado_en      TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(fecha, sucursal)
    )
    """)

    # ---- NUEVO: migración de obs_celdas_json ----
    cols = {r[1] for r in conn.execute("PRAGMA table_info(cortes_diarios)").fetchall()}
    if "obs_celdas_json" not in cols:
        conn.execute("ALTER TABLE cortes_diarios ADD COLUMN obs_celdas_json TEXT DEFAULT '{}'")
        print("[db] migración: cortes_diarios.obs_celdas_json agregada")

    # ---- NUEVO: sembrar __manual__ en filas viejas ----
    rows_mig = conn.execute("""
        SELECT id, observaciones, obs_celdas_json FROM cortes_diarios
        WHERE observaciones != ''
        AND (obs_celdas_json IS NULL OR obs_celdas_json = '{}')
    """).fetchall()
    for r in rows_mig:
        try:
            data = json.loads(r["obs_celdas_json"] or "{}")
        except Exception:
            data = {}
        data["__manual__"] = r["observaciones"]
        conn.execute(
            "UPDATE cortes_diarios SET obs_celdas_json = ? WHERE id = ?",
            (json.dumps(data, ensure_ascii=False), r["id"]),
        )
    if rows_mig:
        print(f"[db] migración: __manual__ sembrado en {len(rows_mig)} filas")

    conn.execute("""
    CREATE TABLE IF NOT EXISTS cortes_semanas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        anio INTEGER NOT NULL,
        semana INTEGER NOT NULL,
        desde TEXT NOT NULL,
        hasta TEXT NOT NULL,
        estado TEXT NOT NULL DEFAULT 'abierta',
        excel_path TEXT,
        cerrado_en TEXT,
        UNIQUE(anio, semana)
    )
    """)

    # Migración cortes_diarios
    cols = {r[1] for r in conn.execute("PRAGMA table_info(cortes_diarios)").fetchall()}
    if "obs_celdas_json" not in cols:
        conn.execute("ALTER TABLE cortes_diarios ADD COLUMN obs_celdas_json TEXT DEFAULT '{}'")
        print("[db] migración: cortes_diarios.obs_celdas_json agregada")

    # --- Servicios Externos ---
    conn.execute("""
    CREATE TABLE IF NOT EXISTS servicios_semanas (
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
    )
    """)

    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_serv_sem_estado "
        "ON servicios_semanas(estado)"
    )

    conn.execute("""
    CREATE TABLE IF NOT EXISTS servicios_externos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        concepto TEXT NOT NULL DEFAULT '',
        fecha TEXT NOT NULL,
        cliente TEXT NOT NULL,
        mascota TEXT DEFAULT '',
        recuperacion TEXT DEFAULT '',
        fecha_entrega TEXT DEFAULT '',
        total REAL NOT NULL DEFAULT 0,
        fecha_pago TEXT DEFAULT '',
        tipo_pago TEXT DEFAULT '',
        notas TEXT DEFAULT '',
        creado_en TEXT DEFAULT CURRENT_TIMESTAMP,
        actualizado_en TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.execute("CREATE INDEX IF NOT EXISTS idx_serv_ext_fecha ON servicios_externos(fecha)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_serv_ext_pago ON servicios_externos(fecha_pago)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_serv_ext_concepto ON servicios_externos(concepto)")

    # --- Convenios ---
    conn.execute("""
        CREATE TABLE IF NOT EXISTS convenios (
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
            estado TEXT NOT NULL DEFAULT 'borrador',
            notas TEXT DEFAULT '',
            creado_en TEXT DEFAULT CURRENT_TIMESTAMP,
            actualizado_en TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS convenios_pagos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            convenio_id INTEGER NOT NULL,
            numero INTEGER NOT NULL,
            fecha TEXT NOT NULL,
            importe REAL NOT NULL DEFAULT 0,
            efectuado INTEGER NOT NULL DEFAULT 0,
            fecha_pago TEXT DEFAULT '',
            FOREIGN KEY (convenio_id) REFERENCES convenios(id) ON DELETE CASCADE
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS convenios_alertas_vistas (
            convenio_id INTEGER NOT NULL,
            fecha_vista TEXT NOT NULL,
            PRIMARY KEY (convenio_id, fecha_vista)
        )
    """)

    # --- Convenios: migración v1.1 (albarán/factura/tipo_pago por pago) ---
    cols_pagos = {r[1] for r in conn.execute("PRAGMA table_info(convenios_pagos)")}
    if "albaran" not in cols_pagos:
        conn.execute("ALTER TABLE convenios_pagos ADD COLUMN albaran TEXT DEFAULT ''")
    if "factura_numero" not in cols_pagos:
        conn.execute("ALTER TABLE convenios_pagos ADD COLUMN factura_numero TEXT DEFAULT ''")
    if "factura_uuid" not in cols_pagos:
        conn.execute("ALTER TABLE convenios_pagos ADD COLUMN factura_uuid TEXT DEFAULT ''")
    if "tipo_pago" not in cols_pagos:
        conn.execute("ALTER TABLE convenios_pagos ADD COLUMN tipo_pago TEXT DEFAULT ''")
    if "pagado_con_tarjeta" not in cols_pagos:
        conn.execute("ALTER TABLE convenios_pagos ADD COLUMN pagado_con_tarjeta INTEGER DEFAULT 0")

    conn.commit()
    conn.close()

def borrar_todos_ingresos():
    conn = get_conn()
    count = conn.execute("SELECT COUNT(*) FROM ingresos").fetchone()[0]
    conn.execute("DELETE FROM ingresos")
    conn.commit()
    conn.close()
    return count