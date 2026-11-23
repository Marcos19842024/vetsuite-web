# core/recordatorios/plantillas.py
"""
CRUD de plantillas libres de Recordatorios.
Persistencia: tabla plantillas_libres en vetsuite.db.
Soft-delete: al borrar se pone activa=0.
"""

from datetime import datetime
from shared.db import get_conn


def listar_activas() -> list[dict]:
    con = get_conn()
    try:
        cur = con.cursor()
        cur.execute("""
            SELECT id, nombre, cuerpo FROM plantillas_libres
            WHERE activa = 1 ORDER BY nombre COLLATE NOCASE
        """)
        return [{"id": r["id"], "nombre": r["nombre"], "cuerpo": r["cuerpo"]}
                for r in cur.fetchall()]
    finally:
        con.close()


def obtener(pid: int) -> dict | None:
    con = get_conn()
    try:
        cur = con.cursor()
        cur.execute(
            "SELECT id, nombre, cuerpo, activa FROM plantillas_libres WHERE id = ?",
            (pid,),
        )
        r = cur.fetchone()
        if not r:
            return None
        return {"id": r["id"], "nombre": r["nombre"],
                "cuerpo": r["cuerpo"], "activa": bool(r["activa"])}
    finally:
        con.close()


def crear(nombre: str, cuerpo: str) -> int:
    con = get_conn()
    try:
        cur = con.cursor()
        cur.execute(
            "INSERT INTO plantillas_libres (nombre, cuerpo, activa) VALUES (?, ?, 1)",
            (nombre.strip(), cuerpo.strip()),
        )
        con.commit()
        return cur.lastrowid # type: ignore
    finally:
        con.close()


def actualizar(pid: int, nombre: str, cuerpo: str) -> bool:
    con = get_conn()
    try:
        cur = con.cursor()
        cur.execute(
            """UPDATE plantillas_libres
               SET nombre = ?, cuerpo = ?, actualizada_en = ?
               WHERE id = ? AND activa = 1""",
            (nombre.strip(), cuerpo.strip(),
             datetime.utcnow().isoformat(), pid),
        )
        con.commit()
        return cur.rowcount > 0
    finally:
        con.close()


def borrar(pid: int) -> bool:
    con = get_conn()
    try:
        cur = con.cursor()
        cur.execute(
            """UPDATE plantillas_libres
               SET activa = 0, actualizada_en = ?
               WHERE id = ? AND activa = 1""",
            (datetime.utcnow().isoformat(), pid),
        )
        con.commit()
        return cur.rowcount > 0
    finally:
        con.close()


def renderizar(cuerpo: str, cliente: dict, sucursal: str = "") -> str:
    """Reemplaza {variables} en el cuerpo con datos del cliente."""
    import re
    from datetime import date

    mascotas = cliente.get("mascotas", [])
    nombres_m = []
    for m in mascotas:
        if isinstance(m, str):
            nombres_m.append(m)
        elif isinstance(m, dict):
            nombres_m.append(m.get("nombre", ""))
    mascotas_txt = ", ".join(n for n in nombres_m if n)

    reemplazos = {
        "nombre":   cliente.get("nombre", ""),
        "mascota":  mascotas_txt,
        "telefono": cliente.get("telefono_display", cliente.get("telefono", "")),
        "sucursal": sucursal,
        "fecha":    date.today().strftime("%d/%m/%Y"),
    }

    def _sub(m):
        return str(reemplazos.get(m.group(1).strip(), ""))

    return re.sub(r"\{(\w+)\}", _sub, cuerpo)