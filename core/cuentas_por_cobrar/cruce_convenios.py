# core/cuentas_por_cobrar/cruce_convenios.py
"""
Cruce entre Cuentas por Cobrar y Convenios de Pago.

- Un cliente de CPC "tiene convenio" si existe un convenio en estado
  'firmado' o 'impreso' cuyo propietario, normalizado, coincide con
  el nombre del cliente de CPC.
- La comparación es por nombre normalizado (mayúsculas, sin acentos,
  sin puntos, colapsando espacios).
"""

from __future__ import annotations
import sqlite3

from core.cuentas_por_cobrar.calculos import normalizar_nombre


ESTADOS_ACTIVOS = ("firmado", "impreso")


def _normalizar(s: str) -> str:
    """Reutiliza el normalizador de calculos (mismo criterio en todo el módulo)."""
    return normalizar_nombre(s)


def buscar_convenio_activo(conn: sqlite3.Connection, nombre_cliente: str) -> dict | None:
    """
    Devuelve el primer convenio activo cuyo propietario coincide con
    `nombre_cliente` (normalizado), o None si no hay.
    """
    objetivo = _normalizar(nombre_cliente)
    if not objetivo:
        return None

    rows = conn.execute(
        """SELECT id, folio, propietario, estado
           FROM convenios
           WHERE estado IN (?, ?)""",
        ESTADOS_ACTIVOS,
    ).fetchall()

    for r in rows:
        if _normalizar(r["propietario"] or "") == objetivo:
            return dict(r)
    return None


def cruzar_cliente(conn: sqlite3.Connection, cpc_cliente_id: int) -> dict | None:
    """
    Cruza un cliente puntual y actualiza su fila en cpc_clientes.
    Devuelve el convenio encontrado (dict) o None.
    No hace commit: lo deja al caller.
    """
    row = conn.execute(
        "SELECT id, nombre, es_institucional FROM cpc_clientes WHERE id = ?",
        (cpc_cliente_id,),
    ).fetchone()
    if not row:
        return None

    # Los institucionales no se cruzan (no aplica cobranza por esta vía)
    if row["es_institucional"]:
        return None

    conv = buscar_convenio_activo(conn, row["nombre"])

    if conv:
        conn.execute(
            """UPDATE cpc_clientes
               SET es_convenio = 1,
                   convenio_folio = ?,
                   estado = CASE
                       WHEN estado IN ('pagado', 'cancelado', 'disputa') THEN estado
                       ELSE 'convenio'
                   END
               WHERE id = ?""",
            (conv["folio"], cpc_cliente_id),
        )
        return conv

    # Si no hay convenio activo, limpiar la marca (pudo haberse cancelado)
    conn.execute(
        """UPDATE cpc_clientes
           SET es_convenio = 0,
               convenio_folio = '',
               estado = CASE
                   WHEN estado = 'convenio' THEN 'pendiente'
                   ELSE estado
               END
           WHERE id = ?""",
        (cpc_cliente_id,),
    )
    return None


def cruzar_todos(conn: sqlite3.Connection) -> dict:
    """
    Cruza todos los clientes de CPC que no sean institucionales.
    Devuelve un resumen: {marcados, desmarcados}.
    Hace commit al final.
    """
    rows = conn.execute(
        "SELECT id FROM cpc_clientes WHERE es_institucional = 0"
    ).fetchall()

    marcados = 0
    desmarcados = 0

    for r in rows:
        antes = conn.execute(
            "SELECT es_convenio FROM cpc_clientes WHERE id = ?", (r["id"],)
        ).fetchone()["es_convenio"]

        conv = cruzar_cliente(conn, r["id"])

        if conv and not antes:
            marcados += 1
        elif not conv and antes:
            desmarcados += 1

    conn.commit()
    return {"marcados": marcados, "desmarcados": desmarcados, "total": len(rows)}