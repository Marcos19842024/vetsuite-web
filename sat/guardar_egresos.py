# -*- coding: utf-8 -*-
"""
sat/guardar_egresos.py
Guarda las facturas de Egresos en un archivo JSON por año.

Los JSON de Egresos viven SIEMPRE en la carpeta del módulo:
  - Dev:  <raíz proyecto>/egresos/
  - Prod: ~/Documents/Vet Suite/egresos/

La ruta se delega a core.rutas_egresos (única fuente de verdad).
"""
import json
from datetime import datetime
from pathlib import Path

from core.rutas_egresos import ruta_registros_egresos


def cargar_db_egresos(anio):
    """Carga los registros de egresos del año."""
    ruta = ruta_registros_egresos(anio)
    if ruta.exists():
        try:
            with open(ruta, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def guardar_db_egresos(regs, anio):
    """Guarda los registros de egresos."""
    ruta = ruta_registros_egresos(anio)
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(regs, f, ensure_ascii=False, indent=2)


def existe_uuid_egresos(registros, uuid, ignorar_id=None):
    """Verifica si un UUID ya existe."""
    if not uuid:
        return False
    uuid = str(uuid).strip().upper()
    for r in registros:
        if ignorar_id is not None and r.get("id") == ignorar_id:
            continue
        if str(r.get("uuid", "")).strip().upper() == uuid:
            return True
    return False


def _sucursal_para_rfc(rfc):
    """
    Consulta el archivo de proveedores-sucursal y devuelve la sucursal
    asignada al RFC (o None si no está registrado).
    """
    if not rfc:
        return None
    try:
        from config.config_egresos import cargar_proveedores_sucursal
        proveedores = cargar_proveedores_sucursal()
        rfc = str(rfc).strip().upper()
        # Buscar sin importar mayúsculas
        for k, v in proveedores.items():
            if str(k).strip().upper() == rfc:
                return v
    except Exception:
        pass
    return None


def guardar_facturas(facturas, anio=None, agregar_sucursal=True):
    """
    Guarda las facturas procesadas en el archivo del año.
    
    Auto-clasifica la sucursal consultando proveedores_sucursal.json:
      - Si el RFC está registrado → usa esa sucursal.
      - Si no → default "Baalak".
    
    Devuelve:
      - (nuevas, duplicadas)
    """
    if anio is None:
        anio = datetime.now().year

    # Cargar registros existentes
    registros = cargar_db_egresos(anio)

    nuevas = 0
    duplicadas = 0

    for f in facturas:
        uuid = f.get("uuid", "")

        # Verificar duplicado
        if existe_uuid_egresos(registros, uuid):
            duplicadas += 1
            continue

        # Agregar ID y campos extra
        f["id"] = int(datetime.now().timestamp() * 1000) + nuevas
        f["anio"] = anio
        f["mes"] = _mes_desde_fecha(f.get("fecha", ""))

        if agregar_sucursal:
            # Auto-clasificar por RFC
            rfc = f.get("rfc_emisor", "")
            sucursal_auto = _sucursal_para_rfc(rfc)
            f["sucursal"] = sucursal_auto or "Baalak"

        # Determinar forma_pago_texto (para carpeta)
        metodo = f.get("metodo_pago", "PUE")
        if metodo == "PPD":
            f["forma_pago_texto"] = "PPD"
        else:
            # PUE: usar la forma de pago del XML
            forma = f.get("forma_pago_texto", "")
            if not forma:
                forma = _forma_pago_desde_codigo(f.get("forma_pago", ""))
            f["forma_pago_texto"] = forma or "Efectivo"

        registros.append(f)
        nuevas += 1

    # Guardar
    guardar_db_egresos(registros, anio)

    return nuevas, duplicadas


def _mes_desde_fecha(fecha):
    """Extrae el mes de una fecha 'dd/mm/yyyy'."""
    from config.campos import MESES_ES
    try:
        partes = fecha.split("/")
        if len(partes) == 3:
            mes_num = int(partes[1])
            return MESES_ES[mes_num - 1]
    except Exception:
        pass
    return ""


def _forma_pago_desde_codigo(codigo):
    """Convierte el código SAT de forma de pago a texto de carpeta."""
    mapa = {
        "01": "Efectivo",
        "03": "Transferencia",
        "04": "TC",
        "28": "TD",
    }
    return mapa.get(str(codigo).strip(), "Efectivo")