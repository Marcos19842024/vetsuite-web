import json
from pathlib import Path

from shared.rutas import IP_PERMISOS as RUTA

_DEFAULT = {
    "modulos": ["ingresos", "egresos", "corte semanal", "servicios externos", "recordatorios", "convenios"],
    "ips": {
        "127.0.0.1": {
            "nombre": "Servidor / Administrador",
            "modulos": ["ingresos", "egresos", "corte semanal", "servicios externos", "recordatorios", "convenios"],
        }
    },
    "admin ips": ["127.0.0.1"],
    "default_deny": True,
}


def _normalizar_ip_entry(valor):
    """Acepta lista (formato viejo) o dict (formato nuevo) y devuelve dict."""
    if isinstance(valor, list):
        return {"nombre": "", "modulos": list(valor)}
    if isinstance(valor, dict):
        return {
            "nombre": valor.get("nombre", "") or "",
            "modulos": list(valor.get("modulos", []) or []),
        }
    return {"nombre": "", "modulos": []}


def cargar() -> dict:
    if not RUTA.exists():
        guardar(_DEFAULT)
        return json.loads(json.dumps(_DEFAULT))  # copia profunda
    try:
        data = json.loads(RUTA.read_text(encoding="utf-8"))
    except Exception:
        return json.loads(json.dumps(_DEFAULT))

    data.setdefault("modulos", list(_DEFAULT["modulos"]))
    data.setdefault("admin ips", ["127.0.0.1"])
    data.setdefault("default_deny", True)

    # Normaliza el diccionario de IPs al formato {ip: {nombre, modulos}}
    ips_norm = {}
    for ip, valor in (data.get("ips") or {}).items():
        ips_norm[ip] = _normalizar_ip_entry(valor)
    data["ips"] = ips_norm

    return data


def guardar(cfg: dict) -> None:
    RUTA.write_text(
        json.dumps(cfg, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def modulos_permitidos(ip: str) -> list:
    cfg = cargar()
    entrada = cfg["ips"].get(ip)
    if entrada is not None:
        return list(entrada.get("modulos", []))
    if not cfg.get("default_deny", True):
        return list(cfg["modulos"])
    return []


def es_admin(ip: str) -> bool:
    return ip in cargar().get("admin ips", [])


def modulo_de_path(path: str):
    for m in ("ingresos", "egresos", "corte semanal", "servicios externos", "recordatorios", "convenios"):
        if path == f"/{m}" or path.startswith(f"/{m}/"):
            return m
    return None