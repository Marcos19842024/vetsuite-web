# core/recordatorios/historial.py
"""
Historial de envíos. Igual que escritorio: clave (telefono, tipo, hash_mensaje).
"""
import hashlib
from core.rutas_recordatorios import HISTORIAL_FILE, cargar_json, guardar_json


def _hash(mensaje: str) -> str:
    return hashlib.sha256((mensaje or "").encode("utf-8")).hexdigest()[:16]


def _cargar() -> dict:
    data = cargar_json(HISTORIAL_FILE, {"envios": []})
    if not isinstance(data, dict) or "envios" not in data:
        data = {"envios": []}
    return data


def _guardar(data: dict) -> None:
    guardar_json(HISTORIAL_FILE, data)


def ya_fue_enviado(telefono: str, tipo: str, mensaje: str) -> bool:
    h = _hash(mensaje)
    for e in _cargar()["envios"]:
        if e.get("telefono") == telefono and e.get("tipo") == tipo and e.get("hash") == h:
            return True
    return False


def marcar_enviado(telefono: str, tipo: str, mensaje: str, nombre: str = "") -> None:
    data = _cargar()
    h = _hash(mensaje)
    # Evitar duplicados
    for e in data["envios"]:
        if e.get("telefono") == telefono and e.get("tipo") == tipo and e.get("hash") == h:
            return
    from datetime import datetime
    data["envios"].append({
        "telefono": telefono,
        "tipo": tipo,
        "hash": h,
        "nombre": nombre,
        "enviado_en": datetime.now().isoformat(timespec="seconds"),
    })
    _guardar(data)


def desmarcar_enviado(telefono: str, tipo: str) -> None:
    data = _cargar()
    data["envios"] = [
        e for e in data["envios"]
        if not (e.get("telefono") == telefono and e.get("tipo") == tipo)
    ]
    _guardar(data)


def listar_envios() -> list:
    return _cargar()["envios"]