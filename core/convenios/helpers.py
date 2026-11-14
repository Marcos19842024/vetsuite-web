"""Helpers de Convenios: folio, búsqueda de ingreso, estado de pagos."""
import datetime
import json

from shared.db import get_conn
from shared.rutas import CONVENIOS_ALERTAS_VISTAS

MESES_ES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


def fecha_legible(iso: str) -> str:
    """'2026-09-30' -> '30 de septiembre de 2026'."""
    if not iso:
        return ""
    try:
        d = datetime.date.fromisoformat(iso)
        return f"{d.day} de {MESES_ES[d.month - 1]} de {d.year}"
    except Exception:
        return iso


def generar_folio(conn) -> str:
    """CONV-<año>-<consecutivo 4 dígitos>."""
    anio = datetime.date.today().year
    row = conn.execute(
        "SELECT COUNT(*) FROM convenios WHERE folio LIKE ?",
        (f"CONV-{anio}-%",),
    ).fetchone()
    consec = (row[0] if row else 0) + 1
    # Asegurar que no exista (por si se borró alguno)
    while True:
        folio = f"CONV-{anio}-{consec:04d}"
        existe = conn.execute(
            "SELECT 1 FROM convenios WHERE folio=?", (folio,)
        ).fetchone()
        if not existe:
            return folio
        consec += 1


def buscar_ingreso_por_cliente(conn, nombre: str, rfc: str = ""):
    """Busca una factura de Ingresos a nombre del cliente.

    Reglas:
    - Coincide por RFC si se proporciona (más confiable).
    - Si no, por nombre exacto (case-insensitive).
    - NO vincula facturas a 'Público en general'.
    Devuelve dict con id, fecha, folio, rfc, total, forma_pago o None.
    """
    if rfc:
        row = conn.execute(
            "SELECT id, fecha, folio, rfc, total, datos_json "
            "FROM ingresos WHERE UPPER(TRIM(rfc)) = UPPER(TRIM(?)) "
            "ORDER BY fecha DESC LIMIT 1",
            (rfc,),
        ).fetchone()
        if row:
            return _row_a_ingreso(row)
    if nombre:
        row = conn.execute(
            "SELECT id, fecha, folio, rfc, total, datos_json "
            "FROM ingresos WHERE UPPER(TRIM(cliente)) = UPPER(TRIM(?)) "
            "ORDER BY fecha DESC LIMIT 1",
            (nombre,),
        ).fetchone()
        if row:
            ing = _row_a_ingreso(row)
            # Descartar público en general
            if ing and ing.get("rfc", "").upper() in ("XAXX010101000", "PÚBLICO EN GENERAL", "PUBLICO EN GENERAL"):
                return None
            return ing
    return None


def _row_a_ingreso(row):
    if not row:
        return None
    try:
        datos = json.loads(row["datos_json"] or "{}")
    except Exception:
        datos = {}
    forma = (datos.get("Forma de pago") or datos.get("forma_pago") or "").upper()
    tarjeta = any(k in forma for k in ("TARJETA", "CRÉDITO", "CREDITO", "DÉBITO", "DEBITO", "TC", "TD"))
    return {
        "id": row["id"],
        "fecha": row["fecha"],
        "folio": row["folio"],
        "rfc": row["rfc"] or "",
        "total": row["total"] or 0,
        "forma_pago": forma,
        "pagado_con_tarjeta": 1 if tarjeta else 0,
    }


def cargar_alertas_vistas() -> set:
    """Devuelve un set de convenio_id vistos hoy."""
    hoy = datetime.date.today().isoformat()
    if not CONVENIOS_ALERTAS_VISTAS.exists():
        return set()
    try:
        with open(CONVENIOS_ALERTAS_VISTAS, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return set()
    return {int(k) for k, v in data.items() if v == hoy}


def marcar_alerta_vista(convenio_id: int) -> None:
    hoy = datetime.date.today().isoformat()
    data = {}
    if CONVENIOS_ALERTAS_VISTAS.exists():
        try:
            with open(CONVENIOS_ALERTAS_VISTAS, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
    data[str(convenio_id)] = hoy
    CONVENIOS_ALERTAS_VISTAS.parent.mkdir(parents=True, exist_ok=True)
    with open(CONVENIOS_ALERTAS_VISTAS, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def calcular_estado_pago(conn, convenio_id: int) -> dict:
    """Devuelve {total, pagado, pendiente, n_pagos, n_pagados}."""
    conv = conn.execute(
        "SELECT monto_total FROM convenios WHERE id=?", (convenio_id,)
    ).fetchone()
    total = conv["monto_total"] if conv else 0
    rows = conn.execute(
        "SELECT importe, efectuado FROM convenios_pagos WHERE convenio_id=?",
        (convenio_id,),
    ).fetchall()
    pagado = sum((r["importe"] or 0) for r in rows if r["efectuado"])
    return {
        "total": total,
        "pagado": pagado,
        "pendiente": total - pagado,
        "n_pagos": len(rows),
        "n_pagados": sum(1 for r in rows if r["efectuado"]),
    }