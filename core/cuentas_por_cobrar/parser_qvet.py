# core/cuentas_por_cobrar/parser_qvet.py
"""
Parser del Excel de QVET para Cuentas por Cobrar.

Columnas esperadas (configurables en QVET):
  FECHA ALBARÁN, CLÍNICA, CLIENTE_NOMBRE, VALES, A CUENTA,
  CLIENTE_TELEFONO1, CLIENTE_EMAIL, FECHA FACTURA, TOTAL IMPORTE,
  Cobrado linea, DEUDA, NÚMERO FACTURA, IMPORTE EN VENCIMIENTOS,
  PACIENTE, NÚM.ALBARÁN, NHC, OBSERVACIONES FACTURA,
  CODIGO ALBARAN, IDMASCOTA, IDCLIENTE
"""

from __future__ import annotations
from datetime import datetime
from pathlib import Path
from typing import Any

import openpyxl

from core.cuentas_por_cobrar.calculos import es_institucional, normalizar_fecha, normalizar_telefono


COLUMNAS = {
    "FECHA ALBARAN":         "fecha_albaran",
    "CLINICA":               "sucursal",
    "CLIENTE_NOMBRE":        "cliente_nombre",
    "VALES":                 "vales",
    "A CUENTA":              "a_cuenta",
    "CLIENTE_TELEFONO1":     "telefono",
    "CLIENTE_EMAIL":         "email",
    "FECHA FACTURA":         "fecha_factura",
    "TOTAL IMPORTE":         "total_importe",
    "COBRADO LINEA":         "cobrado_linea",
    "DEUDA":                 "deuda",
    "NUMERO FACTURA":        "numero_factura",
    "IMPORTE EN VENCIMIENTOS":"importe_vencimientos",
    "PACIENTE":              "paciente",
    "NUM.ALBARAN":           "num_albaran",
    "NHC":                   "nhc",
    "OBSERVACIONES FACTURA": "observaciones_factura",
    "CODIGO ALBARAN":        "codigo_albaran",
    "IDMASCOTA":             "idmascota_qvet",
    "IDCLIENTE":             "idcliente_qvet",
}


def _norm_header(s: Any) -> str:
    if s is None:
        return ""
    s = str(s).strip().upper()
    for a, b in (("Á","A"),("É","E"),("Í","I"),("Ó","O"),("Ú","U"),("Ñ","N")):
        s = s.replace(a, b)
    return " ".join(s.split())


def _safe_str(v: Any) -> str:
    if v is None:
        return ""
    s = str(v).strip()
    if s.lower() in ("none", "null"):
        return ""
    return s


def _to_float(v: Any) -> float:
    if v is None or v == "":
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).replace(",", "").replace("$", "").strip()
    if not s:
        return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def _to_int(v: Any) -> int:
    try:
        return int(float(_to_float(v)))
    except (ValueError, TypeError):
        return 0


def _detectar_encabezado(ws) -> tuple[int, dict[str, int]]:
    for i, fila in enumerate(ws.iter_rows(values_only=True)):
        if not fila:
            continue
        norm = [_norm_header(c) for c in fila]
        if "IDCLIENTE" in norm and "CODIGO ALBARAN" in norm:
            indices: dict[str, int] = {}
            for j, h in enumerate(norm):
                clave = COLUMNAS.get(h)
                if clave:
                    indices[clave] = j
            requeridas = {"idcliente_qvet", "codigo_albaran", "deuda", "total_importe"}
            if requeridas.issubset(indices.keys()):
                return i, indices
    raise ValueError(
        "No se encontró encabezado con IDCLIENTE y CODIGO ALBARAN. "
        "¿Es el Excel de QVET correcto?"
    )


def parsear_excel_qvet(ruta_xlsx: str | Path) -> dict:
    ruta = Path(ruta_xlsx)
    wb = openpyxl.load_workbook(ruta, data_only=True)

    try:
        ws = wb["Table"] if "Table" in wb.sheetnames else wb.active
        fila_enc, col = _detectar_encabezado(ws)

        clientes: dict[str, dict] = {}
        omitidos = 0
        filas_leidas = 0
        total_importe = 0.0
        total_cobrado = 0.0
        total_deuda = 0.0

        for fila in ws.iter_rows(min_row=fila_enc + 2, values_only=True):
            if not fila:
                continue
            filas_leidas += 1

            def get(clave: str, default=None):
                idx = col.get(clave)
                if idx is None or idx >= len(fila):
                    return default
                return fila[idx]

            idcliente      = _safe_str(get("idcliente_qvet"))
            codigo_albaran = _safe_str(get("codigo_albaran"))
            if not idcliente or not codigo_albaran:
                omitidos += 1
                continue

            nombre = _safe_str(get("cliente_nombre")) or f"Cliente {idcliente}"
            institucional = es_institucional(nombre)

            telefono = normalizar_telefono(_safe_str(get("telefono")))
            email    = _safe_str(get("email"))
            sucursal = _safe_str(get("sucursal"))

            alb = {
                "codigo_albaran":  codigo_albaran,
                "num_albaran":     _safe_str(get("num_albaran")),
                "idmascota_qvet":  _safe_str(get("idmascota_qvet")),
                "paciente":        _safe_str(get("paciente")),
                "nhc":             _safe_str(get("nhc")),
                "fecha_albaran":   normalizar_fecha(get("fecha_albaran")),
                "fecha_factura":   normalizar_fecha(get("fecha_factura")),
                "numero_factura":  _safe_str(get("numero_factura")),
                "observaciones_factura": _safe_str(get("observaciones_factura")),
                "total_importe":   _to_float(get("total_importe")),
                "cobrado_linea":   _to_float(get("cobrado_linea")),
                "a_cuenta":        _to_float(get("a_cuenta")),
                "vales":           _to_int(get("vales")),
                "deuda":           _to_float(get("deuda")),
            }

            total_importe += alb["total_importe"]
            total_cobrado += alb["cobrado_linea"]
            total_deuda   += alb["deuda"]

            cliente = clientes.get(idcliente)
            if cliente is None:
                cliente = {
                    "idcliente_qvet":   idcliente,
                    "nombre":           nombre,
                    "telefono":         telefono,
                    "email":            email,
                    "sucursal":         sucursal,
                    "es_institucional": institucional,
                    "albaranes":        [],
                    "monto_total":      0.0,
                    "monto_cobrado":    0.0,
                    "saldo":            0.0,
                    "n_albaranes":      0,
                    "fecha_mas_antigua": "",
                }
                clientes[idcliente] = cliente
            else:
                # Conservar el teléfono/email del primer albarán si viene vacío
                if not cliente["telefono"] and telefono:
                    cliente["telefono"] = telefono
                if not cliente["email"] and email:
                    cliente["email"] = email
                if not cliente["sucursal"] and sucursal:
                    cliente["sucursal"] = sucursal

            cliente["albaranes"].append(alb)
            cliente["monto_total"]   += alb["total_importe"]
            cliente["monto_cobrado"] += alb["cobrado_linea"]
            cliente["saldo"]         += alb["deuda"]
            cliente["n_albaranes"]   += 1
            if not cliente["fecha_mas_antigua"] or alb["fecha_albaran"] < cliente["fecha_mas_antigua"]:
                cliente["fecha_mas_antigua"] = alb["fecha_albaran"]

        return {
            "clientes": list(clientes.values()),
            "omitidos": omitidos,
            "total_importe": round(total_importe, 2),
            "total_cobrado": round(total_cobrado, 2),
            "total_deuda":   round(total_deuda, 2),
            "filas_leidas":  filas_leidas,
        }
    finally:
        wb.close()