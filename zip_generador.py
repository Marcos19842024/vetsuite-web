"""
Genera el ZIP mensual con la estructura de la app de escritorio:
  Contabilidad AAAA/
    Contabilidad <mes>/
      Ingreso/
        Facturas <Sucursal>/
          DD-MM-YYYY/
            <archivos>
        Deposito/
          resumen_<sucursal>_<mes>_<anio>.xlsx
"""
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

import shared.uploads_manager as um
from excel_web import generar_excel


def _fecha_ddmmyyyy(fecha_str):
    """
    Acepta 'YYYY-MM-DD' o 'DD/MM/YYYY' y devuelve 'DD-MM-YYYY'.
    """
    if not fecha_str:
        return "sin_fecha"
    s = str(fecha_str).strip()[:10]
    # Intentar ISO
    try:
        dt = datetime.strptime(s, "%Y-%m-%d")
        return dt.strftime("%d-%m-%Y")
    except ValueError:
        pass
    # Intentar DD/MM/YYYY
    try:
        dt = datetime.strptime(s, "%d/%m/%Y")
        return dt.strftime("%d-%m-%Y")
    except ValueError:
        pass
    return s.replace("/", "-") or "sin_fecha"


def generar_zip_mensual(anio, mes_idx, sucursal, registros):
    """
    anio: 2026
    mes_idx: 10 (octubre)
    sucursal: 'Baalak' o 'Prado'
    registros: lista de dicts (datos_json deserializados).

    Devuelve el path al ZIP temporal.
    """
    mes_nombre_es = um.MESES_ES[mes_idx - 1]
    mes_nombre_cap = mes_nombre_es.capitalize()

    tmp = tempfile.NamedTemporaryFile(
        prefix=f"contabilidad_{anio}_{mes_nombre_es}_",
        suffix=".zip",
        delete=False,
    )
    tmp.close()

    prefijo = f"Contabilidad {anio}/Contabilidad {mes_nombre_es}"

    # Agrupar registros por fecha (para carpetas DD-MM-YYYY)
    por_fecha = {}
    for r in registros:
        fecha_str = r.get("fecha", "")
        fecha_carpeta = _fecha_ddmmyyyy(fecha_str)
        por_fecha.setdefault(fecha_carpeta, []).append(r)

    with zipfile.ZipFile(tmp.name, "w", zipfile.ZIP_DEFLATED) as zf:
        # ---- 1. Archivos de facturas ----
        for fecha_carpeta, regs in por_fecha.items():
            for r in regs:
                no_factura = str(r.get("no_factura", "")).strip()
                if not no_factura:
                    continue

                anio_r = anio
                mes_r = um.MESES[mes_idx - 1]
                xml_path, pdf_path = um.buscar_archivos_factura(
                    anio_r, mes_r, sucursal, no_factura
                )

                if not xml_path and not pdf_path:
                    uuid = r.get("folio_fiscal", "")
                    if uuid:
                        xml_path, pdf_path = um.buscar_archivos_factura(
                            anio_r, mes_r, sucursal, uuid
                        )

                for archivo in (xml_path, pdf_path):
                    if archivo and archivo.exists():
                        ruta_en_zip = (
                            f"{prefijo}/Ingreso/"
                            f"Facturas {sucursal}/"
                            f"{fecha_carpeta}/"
                            f"{archivo.name}"
                        )
                        zf.write(archivo, ruta_en_zip)

        # ---- 2. Excel ----
        if registros:
            xlsx_path = generar_excel(
                registros,
                titulo_hoja=f"{mes_nombre_cap} {anio}",
            )
            try:
                ruta_excel = (
                    f"{prefijo}/Ingreso/"
                    f"Deposito/"
                    f"resumen_{sucursal.lower()}_{mes_nombre_es}_{anio}.xlsx"
                )
                zf.write(xlsx_path, ruta_excel)
            finally:
                Path(xlsx_path).unlink(missing_ok=True)

    return tmp.name