# core/rutas_recordatorios.py
"""
Rutas de datos para el módulo de Recordatorios (versión web).

Equivalente a core/rutas_recordatorios.py de la app de escritorio,
pero apuntando a uploads/recordatorios/ dentro de vetsuite_web.
"""

import json
from pathlib import Path

# Raíz del proyecto web (vetsuite_web/)
BASE_DIR = Path(__file__).resolve().parent.parent

CARPETA_DATOS    = BASE_DIR / "uploads" / "recordatorios"
CARPETA_REPORTES = BASE_DIR / "uploads" / "recordatorios" / "reportes"

CARPETA_DATOS.mkdir(parents=True, exist_ok=True)
CARPETA_REPORTES.mkdir(parents=True, exist_ok=True)

HISTORIAL_FILE = CARPETA_DATOS / "historial_recordatorios.json"
AGENDA_CACHE   = CARPETA_DATOS / "agenda_importada.json"
VACUNAS_CACHE  = CARPETA_DATOS / "vacunas_importada.json"

# Configuración del módulo (sucursal activa, nombre clínica, plantillas)
from shared.rutas import RECORDATORIOS_CONFIG as CONFIG_FILE


def cargar_json(path, default):
    if not Path(path).exists():
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def guardar_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)