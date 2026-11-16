# core/recordatorios/convenios_cache.py
"""Carga y guardado de los mensajes de convenios generados por el job."""
from core.rutas_recordatorios import CONVENIOS_CACHE, cargar_json, guardar_json


DEFAULT = {"generado_en": "", "items": []}


def cargar() -> dict:
    data = cargar_json(CONVENIOS_CACHE, None)
    if not isinstance(data, dict) or "items" not in data:
        return {"generado_en": "", "items": []}
    return data


def guardar(data: dict) -> None:
    guardar_json(CONVENIOS_CACHE, data)


def existe_id(data: dict, item_id: str) -> bool:
    return any(it.get("id") == item_id for it in data.get("items", []))


def agregar(data: dict, item: dict) -> None:
    data.setdefault("items", []).append(item)


def borrar_todo() -> None:
    if CONVENIOS_CACHE.exists():
        CONVENIOS_CACHE.unlink()


def marcar_descartado(idx: int) -> bool:
    data = cargar()
    items = data.get("items", [])
    if not (0 <= idx < len(items)):
        return False
    items[idx]["descartado"] = True
    guardar(data)
    return True