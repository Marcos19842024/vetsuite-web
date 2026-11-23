# core/cuentas_por_cobrar/bitacora.py
from __future__ import annotations
import sqlite3
from datetime import datetime

RESULTADOS_VALIDOS = {
    "sin_respuesta", "contestado", "buzon", "numero_equivocado",
    "promesa_pago", "pago_realizado", "no_le_interesa", "disputa",
    "verificado_en_qvet", "es_convenio", "institucional",
}

TIPOS_VALIDOS = {"llamada", "whatsapp", "email", "visita", "sms", "otro"}

# Estados que requieren verificación previa en QVET
ESTADOS_BLOQUEADOS = {"contactado", "promesa_pago", "pagado"}


def verificado_en_qvet(conn: sqlite3.Connection, cpc_cliente_id: int) -> bool:
    row = conn.execute(
        "SELECT 1 FROM cpc_bitacora "
        "WHERE cpc_cliente_id = ? AND resultado = 'verificado_en_qvet' "
        "LIMIT 1",
        (cpc_cliente_id,),
    ).fetchone()
    return row is not None


def agregar_entrada(
    conn: sqlite3.Connection,
    cpc_cliente_id: int,
    *,
    fecha: str,
    hora: str = "",
    tipo_contacto: str = "llamada",
    resultado: str = "",
    promesa_fecha: str = "",
    promesa_monto: float = 0,
    observaciones: str = "",
    usuario: str = "",
) -> int:
    if tipo_contacto not in TIPOS_VALIDOS:
        raise ValueError(f"Tipo de contacto inválido: {tipo_contacto}")
    if resultado and resultado not in RESULTADOS_VALIDOS:
        raise ValueError(f"Resultado inválido: {resultado}")

    cur = conn.execute(
        """INSERT INTO cpc_bitacora
           (cpc_cliente_id, fecha, hora, tipo_contacto, resultado,
            promesa_fecha, promesa_monto, observaciones, usuario)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (cpc_cliente_id, fecha, hora, tipo_contacto, resultado,
         promesa_fecha, promesa_monto, observaciones, usuario),
    )
    conn.commit()
    return cur.lastrowid


def listar_entradas(conn: sqlite3.Connection, cpc_cliente_id: int) -> list[dict]:
    rows = conn.execute(
        """SELECT * FROM cpc_bitacora
           WHERE cpc_cliente_id = ?
           ORDER BY fecha DESC, hora DESC, id DESC""",
        (cpc_cliente_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def puede_cambiar_a(conn: sqlite3.Connection, cpc_cliente_id: int, nuevo_estado: str) -> tuple[bool, str]:
    if nuevo_estado not in ESTADOS_BLOQUEADOS:
        return True, ""
    if verificado_en_qvet(conn, cpc_cliente_id):
        return True, ""
    return False, "Debes registrar 'verificado_en_qvet' en la bitácora antes de marcar este estado."


def actualizar_contacto_cliente(conn: sqlite3.Connection, cpc_cliente_id: int) -> None:
    """Recalcula último contacto y próximo contacto desde la bitácora."""
    ultimo = conn.execute(
        "SELECT MAX(fecha) FROM cpc_bitacora WHERE cpc_cliente_id = ?",
        (cpc_cliente_id,),
    ).fetchone()[0] or ""

    proximo = conn.execute(
        """SELECT promesa_fecha FROM cpc_bitacora
           WHERE cpc_cliente_id = ? AND promesa_fecha != ''
           ORDER BY promesa_fecha DESC LIMIT 1""",
        (cpc_cliente_id,),
    ).fetchone()
    proximo = proximo[0] if proximo else ""

    conn.execute(
        "UPDATE cpc_clientes SET ultimo_contacto = ?, proximo_contacto = ?, actualizado_en = ? WHERE id = ?",
        (ultimo, proximo, datetime.utcnow().isoformat(timespec="seconds"), cpc_cliente_id),
    )
    conn.commit()