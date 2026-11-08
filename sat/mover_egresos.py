# -*- coding: utf-8 -*-
"""
sat/mover_egresos.py
Renombra y mueve los XML de Egresos a sus carpetas correspondientes.

Estructura:
  Egreso/
  ├── Animalia/
  │   ├── PUE/
  │   │   ├── Efectivo/
  │   │   ├── TC/
  │   │   ├── TD/
  │   │   ├── Transferencia/
  │   │   └── PPD/
  │   └── PPD/
  │       ├── Efectivo/
  │       ├── TC/
  │       ├── TD/
  │       ├── Transferencia/
  │       └── PPD/
  └── Baalak/
      └── (misma estructura)

Nombre del archivo: <serie>-<folio>.xml (o <folio>.xml si no hay serie).
La numeracion de linea NO se guarda en el archivo ni en el JSON:
se calcula al vuelo en la tabla y en el Excel.
"""

import shutil
from datetime import datetime
from pathlib import Path

from shared.campos import MESES_ES
from core.rutas_egresos import CARPETA_DATOS


# Formas de pago válidas (nombre de carpeta)
FORMAS_PAGO_VALIDAS = ["Efectivo", "TC", "TD", "Transferencia", "PPD"]


def ruta_egreso(anio, mes_idx):
    """Carpeta base de Egresos."""
    return (
        CARPETA_DATOS / f"Contabilidad {anio}"
        / f"Contabilidad {MESES_ES[mes_idx - 1]}"
        / "Egreso"
    )


def _ruta_carpeta(anio, mes_idx, sucursal, metodo, forma_pago):
    """
    Devuelve la ruta a la carpeta específica según
    sucursal + metodo + forma_pago.
    """
    sucursal = "Animalia" if str(sucursal).strip() == "Animalia" else "Baalak"
    metodo = "PPD" if str(metodo).strip() == "PPD" else "PUE"

    if metodo == "PPD":
        forma = "PPD"
    else:
        forma = str(forma_pago).strip()
        if forma not in FORMAS_PAGO_VALIDAS or forma == "PPD":
            forma = "Efectivo"

    return ruta_egreso(anio, mes_idx) / sucursal / metodo / forma


def _nombre_desde_registro(reg, extension):
    """
    Construye el nombre del archivo a partir de serie + folio.
    Ej: S1 + 8389 -> "S1-8389.xml"
        (sin serie) 8389 -> "8389.xml"
    """
    serie = str(reg.get("serie", "")).strip()
    folio = str(reg.get("folio", "")).strip()
    if not folio:
        return None
    if serie:
        return f"{serie}-{folio}{extension}"
    return f"{folio}{extension}"


def _limpiar_carpeta_si_vacia(carpeta):
    """Elimina la carpeta si está vacía. Sube recursivamente."""
    try:
        carpeta = Path(carpeta)
        # Recorremos hacia arriba hasta la carpeta Egreso
        for _ in range(5):  # máximo 5 niveles
            if not carpeta.exists():
                return
            if any(carpeta.iterdir()):
                return
            # No borrar carpetas "Egreso" o superiores
            if carpeta.name == "Egreso":
                return
            carpeta.rmdir()
            carpeta = carpeta.parent
    except Exception:
        pass


def _ordenar_facturas(facturas):
    """Ordena por fecha ascendente, luego por folio."""
    def _orden(r):
        try:
            partes = r.get("fecha", "").split("/")
            if len(partes) == 3:
                return (int(partes[2]), int(partes[1]), int(partes[0]),
                        str(r.get("folio", "")))
        except Exception:
            pass
        return (0, 0, 0, "")
    return sorted(facturas, key=_orden)


def _parsear_fecha_ddmmyyyy(fecha_str):
    """
    Parsea 'dd/mm/yyyy' → (anio, mes) o (None, None) si falla.
    """
    try:
        partes = str(fecha_str).strip().split("/")
        if len(partes) != 3:
            return None, None
        dia, mes, anio = int(partes[0]), int(partes[1]), int(partes[2])
        if not (1 <= mes <= 12):
            return None, None
        return anio, mes
    except Exception:
        return None, None


def mover_y_renombrar_egresos(registros, anio, mes_idx, carpeta_origen):
    """
    Renombra y mueve los XML de Egresos a sus carpetas según
    la FECHA REAL de cada factura (no el mes de la solicitud),
    más sucursal, método y forma de pago.

    Los parámetros anio/mes_idx se mantienen por compatibilidad con
    el llamador, pero se IGNORAN para calcular la carpeta destino.
    La carpeta destino se deriva de reg["fecha"] (dd/mm/yyyy).

    Actualiza cada registro con:
      - ruta_xml / ruta_xml_destino
      - carpeta (sucursal/metodo/forma)

    NO guarda 'linea'. La numeración se calcula al vuelo.

    Devuelve:
      - (movidos, errores)
    """
    carpeta_origen = Path(carpeta_origen)
    movidos = []
    errores = []

    # Agrupar por (anio_real, mes_real, sucursal, metodo, forma)
    from collections import defaultdict
    por_grupo = defaultdict(list)
    sin_fecha = []

    for reg in registros:
        anio_real, mes_real = _parsear_fecha_ddmmyyyy(reg.get("fecha", ""))
        if anio_real is None:
            sin_fecha.append(reg)
            continue

        sucursal = reg.get("sucursal", "Baalak")
        metodo = reg.get("metodo_pago", "PUE")
        forma = reg.get("forma_pago_texto", "Efectivo")
        if metodo == "PPD":
            forma = "PPD"
        elif forma not in FORMAS_PAGO_VALIDAS or forma == "PPD":
            forma = "Efectivo"

        clave = (anio_real, mes_real, sucursal, metodo, forma)
        por_grupo[clave].append(reg)

    # Registros sin fecha válida: reportar pero no mover
    for reg in sin_fecha:
        errores.append((reg.get("folio", "?"), "Fecha inválida o vacía"))

    # Procesar cada grupo
    for clave, facturas in por_grupo.items():
        anio_real, mes_real, sucursal, metodo, forma = clave
        carpeta_destino = _ruta_carpeta(anio_real, mes_real, sucursal, metodo, forma)
        carpeta_destino.mkdir(parents=True, exist_ok=True)

        for reg in facturas:
            folio = reg.get("folio", "")
            if not folio:
                errores.append((reg.get("id", "?"), "Sin folio"))
                continue

            nombre_xml = _nombre_desde_registro(reg, ".xml")
            if not nombre_xml:
                errores.append((folio, "No se pudo construir el nombre"))
                continue

            ruta_destino = carpeta_destino / nombre_xml

            # Buscar XML origen
            ruta_origen_str = reg.get("ruta_xml", "") or reg.get("ruta_xml_destino", "")
            ruta_origen = Path(ruta_origen_str) if ruta_origen_str else None

            if not ruta_origen or not ruta_origen.exists():
                candidatos = list(carpeta_origen.glob(f"*{folio}*.xml"))
                if not candidatos:
                    uuid_str = reg.get("uuid", "")
                    if uuid_str:
                        candidatos = list(carpeta_origen.glob(f"*{uuid_str}*.xml"))
                if candidatos:
                    ruta_origen = candidatos[0]

            # Si ya está en destino
            if ruta_origen and ruta_origen.exists():
                if ruta_origen.resolve() == ruta_destino.resolve():
                    reg["ruta_xml"] = str(ruta_destino)
                    reg["ruta_xml_destino"] = str(ruta_destino)
                    reg["carpeta"] = f"{sucursal}/{metodo}/{forma}"
                    movidos.append({
                        "folio": folio,
                        "destino": str(ruta_destino),
                    })
                    continue

                # Mover
                try:
                    if ruta_destino.exists():
                        ruta_destino.unlink()
                    shutil.move(str(ruta_origen), str(ruta_destino))
                    reg["ruta_xml"] = str(ruta_destino)
                    reg["ruta_xml_destino"] = str(ruta_destino)
                    reg["carpeta"] = f"{sucursal}/{metodo}/{forma}"

                    # Mover el PDF si existe junto al XML
                    ruta_pdf_str = reg.get("ruta_pdf", "")
                    if ruta_pdf_str:
                        p_pdf = Path(ruta_pdf_str)
                        if p_pdf.exists():
                            nombre_pdf = _nombre_desde_registro(reg, ".PDF")
                            if nombre_pdf:
                                destino_pdf = carpeta_destino / nombre_pdf
                                try:
                                    if destino_pdf.exists() and destino_pdf.resolve() != p_pdf.resolve():
                                        destino_pdf.unlink()
                                    if p_pdf.resolve() != destino_pdf.resolve():
                                        shutil.move(str(p_pdf), str(destino_pdf))
                                    reg["ruta_pdf"] = str(destino_pdf)
                                except Exception:
                                    pass

                    movidos.append({
                        "folio": folio,
                        "origen": str(ruta_origen),
                        "destino": str(ruta_destino),
                    })

                    # Limpiar carpeta origen si quedó vacía
                    _limpiar_carpeta_si_vacia(ruta_origen.parent)

                except Exception as e:
                    errores.append((folio, str(e)))
            else:
                if ruta_destino.exists():
                    reg["ruta_xml"] = str(ruta_destino)
                    reg["ruta_xml_destino"] = str(ruta_destino)
                    reg["carpeta"] = f"{sucursal}/{metodo}/{forma}"
                    movidos.append({
                        "folio": folio,
                        "destino": str(ruta_destino),
                    })
                else:
                    errores.append((folio, "XML origen no encontrado"))

    # Guardar el JSON
    from sat.guardar_egresos import guardar_db_egresos
    guardar_db_egresos(registros, anio)

    return movidos, errores


def mover_un_registro(registro, anio, mes_idx):
    """
    Mueve UN solo registro cuando cambia su sucursal o forma de pago.

    Devuelve (ok, mensaje).
    """
    try:
        sucursal = registro.get("sucursal", "Baalak")
        metodo = registro.get("metodo_pago", "PUE")
        forma = registro.get("forma_pago_texto", "Efectivo")
        if metodo == "PPD":
            forma = "PPD"

        carpeta_destino = _ruta_carpeta(anio, mes_idx, sucursal, metodo, forma)
        carpeta_destino.mkdir(parents=True, exist_ok=True)

        folio = registro.get("folio", "")
        nombre_xml = _nombre_desde_registro(registro, ".xml")
        if not nombre_xml:
            return False, "Sin folio"

        ruta_destino = carpeta_destino / nombre_xml

        ruta_origen_str = registro.get("ruta_xml", "") or registro.get("ruta_xml_destino", "")
        ruta_origen = Path(ruta_origen_str) if ruta_origen_str else None

        # Si ya está en destino, no hacer nada
        if (ruta_origen and ruta_origen.exists()
                and ruta_origen.resolve() == ruta_destino.resolve()):
            return True, "Sin cambios"

        # Mover XML
        if ruta_origen and ruta_origen.exists():
            if ruta_destino.exists() and ruta_destino.resolve() != ruta_origen.resolve():
                ruta_destino.unlink()
            shutil.move(str(ruta_origen), str(ruta_destino))

            # Limpiar carpeta origen si quedó vacía
            _limpiar_carpeta_si_vacia(ruta_origen.parent)

        registro["ruta_xml"] = str(ruta_destino)
        registro["ruta_xml_destino"] = str(ruta_destino)

        # Mover PDF si existe
        ruta_pdf_str = registro.get("ruta_pdf", "")
        if ruta_pdf_str:
            p_pdf = Path(ruta_pdf_str)
            if p_pdf.exists():
                nombre_pdf = _nombre_desde_registro(registro, ".PDF")
                if nombre_pdf:
                    destino_pdf = carpeta_destino / nombre_pdf
                    try:
                        if destino_pdf.exists() and destino_pdf.resolve() != p_pdf.resolve():
                            destino_pdf.unlink()
                        if p_pdf.resolve() != destino_pdf.resolve():
                            shutil.move(str(p_pdf), str(destino_pdf))
                        registro["ruta_pdf"] = str(destino_pdf)
                    except Exception:
                        pass

        registro["carpeta"] = f"{sucursal}/{metodo}/{forma}"

        return True, f"Movido a {sucursal}/{metodo}/{forma}/"

    except Exception as e:
        return False, str(e)