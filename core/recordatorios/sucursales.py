# core/recordatorios/sucursales.py
from core.rutas_recordatorios import CONFIG_FILE, cargar_json, guardar_json

_DEFAULT = {
    "sucursal_activa": "BAALAK_CENTRAL",
    "sucursales": {
        "BAALAK_CENTRAL": {"nombre": "Baalak (Central)", "id": "BAALAK_CENTRAL"},
        "ANIMALIA":       {"nombre": "Animalia",         "id": "ANIMALIA"},
    },
}


def cargar_sucursales() -> dict:
    return cargar_json(CONFIG_FILE, _DEFAULT.copy())


def sucursal_activa() -> dict:
    cfg = cargar_sucursales()
    sid = cfg.get("sucursal_activa", "BAALAK_CENTRAL")
    return cfg["sucursales"].get(sid, {"nombre": sid, "id": sid})


def nombre_clinica_activa() -> str:
    return sucursal_activa().get("nombre", "VetSuite")


def guardar_sucursal_activa(sid: str) -> None:
    cfg = cargar_sucursales()
    if sid in cfg.get("sucursales", {}):
        cfg["sucursal_activa"] = sid
        guardar_json(CONFIG_FILE, cfg)