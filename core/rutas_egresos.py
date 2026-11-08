# -*- coding: utf-8 -*-
"""
core/rutas_egresos.py
Rutas de carpetas para el módulo de Egresos.
"""

import sys
from datetime import datetime
from pathlib import Path
from shared.campos import MESES_ES


BASE_DIR = Path(__file__).parent.parent / "uploads" / "egresos" / "contabilidad"


def _carpeta_datos():
    if getattr(sys, 'frozen', False):
        carpeta = Path.home() / "Documents" / "Vet Suite" / "egresos"
    else:
        carpeta = Path(__file__).parent.parent / "uploads" / "egresos"
    carpeta.mkdir(parents=True, exist_ok=True)
    return carpeta


_CARPETA_DATOS = _carpeta_datos()


def ruta_egreso(anio=None, mes=None):
    """
    Carpeta base de Egresos de un mes/año.
    Ejemplo: ~/Documents/Contabilidad 2026/Contabilidad septiembre/Egreso/
    """
    hoy = datetime.now()
    anio = anio or hoy.year
    mes = mes or hoy.month
    return (
        BASE_DIR / f"Contabilidad {anio}"
        / f"Contabilidad {MESES_ES[mes - 1]}"
        / "Egreso"
    )


def ruta_pue(anio=None, mes=None):
    """Carpeta de facturas PUE."""
    return ruta_egreso(anio, mes) / "PUE"


def ruta_ppd(anio=None, mes=None):
    """Carpeta de facturas PPD."""
    return ruta_egreso(anio, mes) / "PPD"


def ruta_animalia(anio=None, mes=None):
    """Carpeta de facturas de Animalia (se excluyen del reporte)."""
    return ruta_egreso(anio, mes) / "Animalia"


def ruta_deposito_egreso(anio=None, mes=None):
    """Carpeta donde se guardan los Excel de Egresos."""
    return ruta_egreso(anio, mes) / "Deposito_Egreso"


def ruta_registros_egresos(anio):
    """Ruta al archivo de registros de egresos del año."""
    return _CARPETA_DATOS / f"registros_egresos_{anio}.json"


def ruta_pdf_original(anio=None, mes=None):
    """Carpeta donde se guardan los PDFs descargados."""
    return ruta_egreso(anio, mes) / "PDFs"


# Acceso público a la carpeta de datos (para persistencia_egresos)
CARPETA_DATOS = _CARPETA_DATOS