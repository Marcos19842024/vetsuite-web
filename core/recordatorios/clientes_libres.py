# core/recordatorios/clientes_libres.py
"""
Cache de clientes para la pestaña Libres.
Persistencia: uploads/recordatorios/libres_clientes.json
Se borra con Reset.
"""

from core.rutas_recordatorios import (
    LIBRES_CLIENTES_CACHE, cargar_json, guardar_json,
)


def cargar() -> list[dict]:
    data = cargar_json(LIBRES_CLIENTES_CACHE, None)
    if not data:
        return []
    if isinstance(data, dict):
        return data.get("clientes", []) or []
    if isinstance(data, list):
        return data
    return []


def guardar(clientes: list[dict]) -> None:
    guardar_json(LIBRES_CLIENTES_CACHE, {"clientes": clientes})


def agregar(clientes_nuevos: list[dict]) -> tuple[int, int]:
    """Agrega por teléfono. Devuelve (nuevos, total)."""
    actuales = cargar()
    claves = {(c.get("telefono") or "").strip() for c in actuales}
    nuevos = 0
    for c in clientes_nuevos:
        tel = (c.get("telefono") or "").strip()
        if tel and tel not in claves:
            actuales.append(c)
            claves.add(tel)
            nuevos += 1
    guardar(actuales)
    return nuevos, len(actuales)


def borrar_todos() -> int:
    n = len(cargar())
    guardar([])
    return n