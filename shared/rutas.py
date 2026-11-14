# -*- coding: utf-8 -*-
"""
shared/rutas.py
Fuente única de verdad para las rutas de archivos del proyecto.

Todo el código debe importar de aquí en vez de hardcodear
Path(__file__).parent / "...", que se rompe cuando el archivo se mueve
de carpeta.
"""
from pathlib import Path

# Raíz del proyecto = carpeta que contiene main.py, shared/, json/, etc.
ROOT = Path(__file__).resolve().parent.parent

# Carpetas base
JSON_DIR = ROOT / "json"
UPLOADS_DIR = ROOT / "uploads"
DB_FILE = ROOT / "vetsuite.db"
CONVENIOS_DIR = UPLOADS_DIR / "convenios"

# JSON de configuración (read-write desde la app)

# --- Jobs ---
JOBS_STATE                = JSON_DIR / "jobs_state.json"

# --- Admin_Ips ---
IP_PERMISOS               = JSON_DIR / "ip_permisos.json"

# --- Ingresos ---
CATALOGO_QVET             = JSON_DIR / "catalogo_qvet.json"
CATEGORIAS_MANUALES       = JSON_DIR / "categorias_manuales.json"
GMAIL_CONFIG              = JSON_DIR / "gmail_config.json"

# --- Egresos ---
EGRESOS_CONFIG            = JSON_DIR / "egresos_config.json"
PROVEEDORES_SUCURSAL      = JSON_DIR / "proveedores_sucursal.json"
SOLICITUD_SAT_ACTIVA      = JSON_DIR / "solicitud_sat_activa.json"
CONFIG_EGRESOS            = JSON_DIR / "config_egresos.json"
PROVEEDORES_TC            = JSON_DIR / "proveedores_tc.json"
OBSERVACIONES_EGRESOS     = JSON_DIR / "observaciones_egresos.json"

# --- Recordatorios ---
RECORDATORIOS_CONFIG      = JSON_DIR / "recordatorios_config.json"

# --- Servicios_Externos ---
SERVICIOS_EXTERNOS_CONFIG = JSON_DIR / "servicios_externos_config.json"

# --- Convenios ---
CONVENIOS_CONFIG = JSON_DIR / "convenios_config.json"
CONVENIOS_ALERTAS_VISTAS = JSON_DIR / "convenios_alertas_vistas.json"