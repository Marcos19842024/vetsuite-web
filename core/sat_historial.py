# -*- coding: utf-8 -*-
"""
core/sat_historial.py

Historial de todo lo que viene del SAT (respuestas crudas, ZIPs, XMLs,
metadatos). Permite reprocesar descargas sin volver a pedirle nada al SAT.

Reglas de diseño:
  - Un "snapshot" por solicitud. Nunca se sobreescribe.
  - Nunca borra automáticamente (salvo rotación explícita).
  - Nunca falla por el historial: si algo sale mal, loguea y sigue.
  - Los snapshots NO van a git (contienen RFCs y montos reales).

Estructura en disco:
  egresos/_sat_historial/
    ├── 2026-10-11_1032_ABC123/
    │   ├── meta.json
    │   ├── 01_solicita.json
    │   ├── 02_verifica_1.json
    │   ├── 03_descarga_1.json
    │   ├── 03_descarga_1.zip
    │   └── xmls/
    │       └── *.xml
    └── _errores/
        └── 2026-10-11_1102_500.json
"""

from __future__ import annotations

import json
import os
import zipfile
from datetime import datetime
from pathlib import Path

from core.rutas_egresos import CARPETA_DATOS  # ajusta si el nombre difiere


# ─────────────────────────────────────────────────────────────
# Rutas
# ─────────────────────────────────────────────────────────────

HISTORIAL_DIR = Path(__file__).parent.parent / "uploads" / "egresos" / "_sat_historial"
ERRORES_DIR = HISTORIAL_DIR / "_errores"


def _ahora() -> datetime:
    return datetime.now()


def _timestamp() -> str:
    return _ahora().strftime("%Y-%m-%d_%H%M%S")


# ─────────────────────────────────────────────────────────────
# Config (lee de config_egresos.json)
# ─────────────────────────────────────────────────────────────

def _historial_activo() -> bool:
    try:
        from egresos.sat_wrapper import cargar_config
        cfg = cargar_config()
        return bool(cfg.get("guardar_historial_sat", False))
    except Exception:
        return False


# ─────────────────────────────────────────────────────────────
# Snapshot: creación y manejo
# ─────────────────────────────────────────────────────────────

def _crear_snapshot(id_solicitud: str, meta_inicial: dict) -> Path:
    """Crea la carpeta del snapshot y escribe meta.json inicial."""
    HISTORIAL_DIR.mkdir(parents=True, exist_ok=True)
    nombre = f"{_timestamp()}_{id_solicitud or 'sin_id'}"
    carpeta = HISTORIAL_DIR / nombre
    carpeta.mkdir(parents=True, exist_ok=True)

    meta = {
        "id_solicitud": id_solicitud,
        "fecha_inicio": _ahora().isoformat(timespec="seconds"),
        "fecha_fin": None,
        "estado_final": None,
        "num_xmls": 0,
        "verificaciones": [],
        "errores": [],
        "archivos": [],
        **meta_inicial,
    }
    _escribir_json(carpeta / "meta.json", meta)
    return carpeta


def _escribir_json(ruta: Path, data: dict) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)


def _leer_json(ruta: Path) -> dict:
    if not ruta.exists():
        return {}
    try:
        with open(ruta, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _merge_json(ruta: Path, cambios: dict) -> None:
    """Merge no destructivo (igual que config_ui.set_seccion)."""
    actual = _leer_json(ruta)
    for k, v in cambios.items():
        if isinstance(v, dict) and isinstance(actual.get(k), dict):
            actual[k].update(v)
        elif isinstance(v, list) and isinstance(actual.get(k), list):
            actual[k].extend(v)
        else:
            actual[k] = v
    _escribir_json(ruta, actual)


def _siguiente_numero(carpeta: Path, prefijo: str) -> int:
    """Cuenta cuántos archivos con ese prefijo existen ya."""
    existentes = list(carpeta.glob(f"{prefijo}_*.json"))
    return len(existentes) + 1


# ─────────────────────────────────────────────────────────────
# API pública
# ─────────────────────────────────────────────────────────────

def guardar_solicitud(id_solicitud: str, respuesta: dict, meta: dict) -> Path | None:
    """
    Guarda la respuesta de SolicitaDescarga.
    Devuelve la ruta del snapshot creado (o None si el historial está off).
    """
    if not _historial_activo():
        return None
    try:
        carpeta = _crear_snapshot(id_solicitud, meta)
        _escribir_json(carpeta / "01_solicita.json", respuesta)
        _merge_json(carpeta / "meta.json", {
            "archivos": ["01_solicita.json"],
        })
        return carpeta
    except Exception as e:
        _log_error(f"guardar_solicitud: {e}")
        return None


def guardar_verificacion(id_solicitud: str, respuesta: dict) -> None:
    """Guarda cada verificación de estado del SAT."""
    if not _historial_activo():
        return
    try:
        carpeta = _buscar_snapshot(id_solicitud)
        if carpeta is None:
            return
        n = _siguiente_numero(carpeta, "02_verifica")
        archivo = f"02_verifica_{n}.json"
        _escribir_json(carpeta / archivo, respuesta)
        _merge_json(carpeta / "meta.json", {
            "verificaciones": [{
                "n": n,
                "hora": _ahora().isoformat(timespec="seconds"),
                "estado": str(respuesta.get("estado", "?")),
                "mensaje": respuesta.get("mensaje", ""),
            }],
            "archivos": [archivo],
        })
    except Exception as e:
        _log_error(f"guardar_verificacion: {e}")


def guardar_descarga(
    id_solicitud: str,
    id_paquete: str,
    respuesta: dict,
    zip_bytes: bytes | None = None,
) -> None:
    """
    Guarda la respuesta de DescargaMasiva y, si hay, el ZIP tal cual.
    """
    if not _historial_activo():
        return
    try:
        carpeta = _buscar_snapshot(id_solicitud)
        if carpeta is None:
            return

        # JSON de la respuesta
        n = _siguiente_numero(carpeta, "03_descarga")
        archivo_json = f"03_descarga_{n}.json"
        _escribir_json(carpeta / archivo_json, respuesta)

        archivos_nuevos = [archivo_json]

        # ZIP si lo hay
        if zip_bytes:
            archivo_zip = f"03_descarga_{n}.zip"
            (carpeta / archivo_zip).write_bytes(zip_bytes)
            archivos_nuevos.append(archivo_zip)

            # Extraer XMLs a subcarpeta
            xmls_dir = carpeta / "xmls"
            xmls_dir.mkdir(exist_ok=True)
            try:
                with zipfile.ZipFile(carpeta / archivo_zip, "r") as z:
                    z.extractall(xmls_dir)
                archivos_nuevos.append("xmls/")
            except Exception as e:
                _log_error(f"extract zip: {e}")

        _merge_json(carpeta / "meta.json", {"archivos": archivos_nuevos})
    except Exception as e:
        _log_error(f"guardar_descarga: {e}")


def cerrar_snapshot(id_solicitud: str, estado_final: str, num_xmls: int) -> None:
    """Marca el snapshot como terminado."""
    if not _historial_activo():
        return
    try:
        carpeta = _buscar_snapshot(id_solicitud)
        if carpeta is None:
            return
        _merge_json(carpeta / "meta.json", {
            "fecha_fin": _ahora().isoformat(timespec="seconds"),
            "estado_final": estado_final,
            "num_xmls": num_xmls,
        })
    except Exception as e:
        _log_error(f"cerrar_snapshot: {e}")


def guardar_error(etapa: str, error: Exception, contexto: dict | None = None) -> None:
    """Guarda errores del SAT para reproducirlos después."""
    if not _historial_activo():
        return
    try:
        ERRORES_DIR.mkdir(parents=True, exist_ok=True)
        nombre = f"{_timestamp()}_{etapa}.json"
        _escribir_json(ERRORES_DIR / nombre, {
            "etapa": etapa,
            "tipo": type(error).__name__,
            "mensaje": str(error),
            "contexto": contexto or {},
            "hora": _ahora().isoformat(timespec="seconds"),
        })
    except Exception as e:
        _log_error(f"guardar_error: {e}")


# ─────────────────────────────────────────────────────────────
# Utilidades
# ─────────────────────────────────────────────────────────────

def _buscar_snapshot(id_solicitud: str) -> Path | None:
    """Encuentra la carpeta del snapshot por id_solicitud."""
    if not HISTORIAL_DIR.exists():
        return None
    # El nombre incluye el id, así que basta con glob
    candidatos = list(HISTORIAL_DIR.glob(f"*_{id_solicitud}"))
    if not candidatos:
        return None
    # El más reciente (por si acaso hay colisiones)
    return sorted(candidatos, reverse=True)[0]


def listar_snapshots() -> list[dict]:
    """Devuelve los snapshots ordenados del más reciente al más viejo."""
    if not HISTORIAL_DIR.exists():
        return []
    resultado = []
    for carpeta in sorted(HISTORIAL_DIR.iterdir(), reverse=True):
        if not carpeta.is_dir() or carpeta.name == "_errores":
            continue
        meta = _leer_json(carpeta / "meta.json")
        if meta:
            meta["_carpeta"] = str(carpeta)
            resultado.append(meta)
    return resultado


def ruta_xmls_de_snapshot(id_o_carpeta: str) -> Path | None:
    """
    Devuelve la carpeta de XMLs de un snapshot, aceptando:
      - id_solicitud ("ABC123")
      - nombre de carpeta ("2026-10-11_1032_ABC123")
    """
    HISTORIAL_DIR.mkdir(parents=True, exist_ok=True)

    # ¿Es nombre de carpeta?
    posible = HISTORIAL_DIR / id_o_carpeta
    if posible.is_dir():
        xmls = posible / "xmls"
        return xmls if xmls.is_dir() else None

    # ¿Es id_solicitud?
    carpeta = _buscar_snapshot(id_o_carpeta)
    if carpeta:
        xmls = carpeta / "xmls"
        return xmls if xmls.is_dir() else None

    return None


def _log_error(msg: str) -> None:
    """Log a stderr sin romper nada."""
    import sys
    print(f"[sat_historial] {msg}", file=sys.stderr)