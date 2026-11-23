# core/cuentas_por_cobrar/config.py
from __future__ import annotations
import json
from threading import Lock

from shared.rutas import CPC_CONFIG

_LOCK = Lock()
_DEFAULT = {
    "institucionales": [],
    "semaforo": {"verde_max": 30, "amarillo_max": 60, "naranja_max": 90},
    "dias_por_vencer": 7,
    "plantillas_whatsapp": {},
    "plantilla_activa": "recordatorio_amable",
    "adjuntos": {"max_mb": 5, "retencion_dias": 365,
                 "tipos_permitidos": ["image/jpeg", "image/png", "application/pdf"]},
    "reporte_pdf": {"cliente": "Baalak Veterinaria",
                    "logo": "static/logo.png",
                    "firmas": ["Recepción", "Administración"]},
    "roles": {"recepcion": ["ver", "bitacora", "estado_basico",
                            "verificar_qvet", "whatsapp"],
              "admin": ["*"]},
}


def cargar_config() -> dict:
    with _LOCK:
        if not CPC_CONFIG.exists():
            return json.loads(json.dumps(_DEFAULT))
        try:
            data = json.loads(CPC_CONFIG.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return json.loads(json.dumps(_DEFAULT))
    # Merge superficial con defaults para tolerar configs viejas
    out = json.loads(json.dumps(_DEFAULT))
    if isinstance(data, dict):
        for k, v in data.items():
            out[k] = v
    return out


def guardar_config(data: dict) -> None:
    with _LOCK:
        CPC_CONFIG.parent.mkdir(parents=True, exist_ok=True)
        CPC_CONFIG.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )