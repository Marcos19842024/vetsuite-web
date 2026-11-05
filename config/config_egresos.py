# -*- coding: utf-8 -*-
"""
config/config_egresos.py
Configuración del módulo de Egresos.
"""

import json
from pathlib import Path

# Importamos la carpeta de datos desde rutas_egresos (única fuente de verdad)
from core.rutas_egresos import CARPETA_DATOS as _CARPETA_DATOS


# Archivos de configuración de egresos
CONFIG_EGRESOS_FILE         = _CARPETA_DATOS / "config_egresos.json"
PROVEEDORES_TC_FILE         = _CARPETA_DATOS / "proveedores_tc.json"
PROVEEDORES_SUCURSAL_FILE   = _CARPETA_DATOS / "proveedores_sucursal.json"
OBSERVACIONES_FILE          = _CARPETA_DATOS / "observaciones_egresos.json"
SOLICITUD_ACTIVA_FILE       = _CARPETA_DATOS / "solicitud_sat_activa.json"


# ============================================================
# CONFIGURACIÓN GENERAL
# ============================================================
CONFIG_EGRESOS_DEFAULT = {
    "rfc_receptor": "",
    "nombre_receptor": "",
    "certificado_cer": "",
    "certificado_key": "",
    "password_fiel": "",
    "ultima_descarga": "",
    "guardar_historial_sat": False,   # ← NUEVO
}


def cargar_config_egresos():
    if CONFIG_EGRESOS_FILE.exists():
        try:
            with open(CONFIG_EGRESOS_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            for k, v in CONFIG_EGRESOS_DEFAULT.items():
                cfg.setdefault(k, v)
            return cfg
        except Exception:
            pass
    return dict(CONFIG_EGRESOS_DEFAULT)


def guardar_config_egresos(cfg):
    with open(CONFIG_EGRESOS_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


# ============================================================
# PROVEEDORES CON TC
# ============================================================
def cargar_proveedores_tc():
    if PROVEEDORES_TC_FILE.exists():
        try:
            with open(PROVEEDORES_TC_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def guardar_proveedores_tc(proveedores):
    with open(PROVEEDORES_TC_FILE, "w", encoding="utf-8") as f:
        json.dump(proveedores, f, ensure_ascii=False, indent=2)


# ============================================================
# PROVEEDORES POR SUCURSAL
# ============================================================
def cargar_proveedores_sucursal():
    if PROVEEDORES_SUCURSAL_FILE.exists():
        try:
            with open(PROVEEDORES_SUCURSAL_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def guardar_proveedores_sucursal(proveedores):
    with open(PROVEEDORES_SUCURSAL_FILE, "w", encoding="utf-8") as f:
        json.dump(proveedores, f, ensure_ascii=False, indent=2)


# ============================================================
# MAPEO DE OBSERVACIONES
# ============================================================
OBSERVACIONES_DEFAULT = {
    "GASOLINA": ["gasolina", "combustible", "pemex", "gas"],
    "INTERNET": ["internet", "telmex", "megacable", "izzi"],
    "CELULAR": ["celular", "telcel", "movistar", "at&t"],
    "ESCUELA": ["escuela", "colegiatura", "educación"],
    "MEMBRESIA": ["membresía", "membresia", "suscripción", "amazon"],
    "GASTOS EN GENERAL": [
        "papelería", "limpieza", "ferretería",
        "medicamento", "alimento", "material",
    ],
    "TRANSPORTE": ["transporte", "ado", "pasaje", "vuelo"],
    "HONORARIOS": ["honorarios", "consultoría", "asesoría"],
}


def cargar_observaciones():
    if OBSERVACIONES_FILE.exists():
        try:
            with open(OBSERVACIONES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return dict(OBSERVACIONES_DEFAULT)


def guardar_observaciones(obs):
    with open(OBSERVACIONES_FILE, "w", encoding="utf-8") as f:
        json.dump(obs, f, ensure_ascii=False, indent=2)


# ============================================================
# SOLICITUDES SAT PENDIENTES
# ============================================================
def cargar_solicitud_activa():
    if not SOLICITUD_ACTIVA_FILE.exists():
        return None
    try:
        with open(SOLICITUD_ACTIVA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def guardar_solicitud_activa(datos):
    with open(SOLICITUD_ACTIVA_FILE, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)


def limpiar_solicitud_activa():
    try:
        if SOLICITUD_ACTIVA_FILE.exists():
            SOLICITUD_ACTIVA_FILE.unlink()
    except Exception:
        pass


def horas_desde_solicitud(datos):
    from datetime import datetime
    if not datos:
        return None
    try:
        fecha = datetime.fromisoformat(datos.get("fecha_solicitud", ""))
        delta = datetime.now() - fecha
        return delta.total_seconds() / 3600
    except Exception:
        return None


# ============================================================
# HISTORIAL DEL SAT
# ============================================================
def historial_sat_activo() -> bool:
    """Devuelve True si el historial del SAT está activado."""
    import os
    if os.getenv("VET_SUITE_HISTORIAL") == "1":
        return True
    return bool(cargar_config_egresos().get("guardar_historial_sat", False))


def activar_historial_sat(activar: bool = True) -> None:
    """Activa/desactiva el historial del SAT y guarda el JSON."""
    cfg = cargar_config_egresos()
    cfg["guardar_historial_sat"] = bool(activar)
    guardar_config_egresos(cfg)