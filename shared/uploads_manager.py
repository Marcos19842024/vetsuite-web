"""
Gestor de archivos subidos.
Centraliza rutas y operaciones: mover a destino final, reorganizar,
servir archivos al navegador, etc.
"""
import shutil
from datetime import datetime
from pathlib import Path


from shared.rutas import ROOT, UPLOADS_DIR
UPLOADS = UPLOADS_DIR
TEMPORALES = UPLOADS / "temporales"
FACTURAS = UPLOADS / "facturas"
RECHAZADOS = UPLOADS / "rechazados"
SIN_PDF = UPLOADS / "sin_pdf"
DUPLICADOS = UPLOADS / "duplicados"
LOGS = UPLOADS / "logs"

MESES = [
    "01_enero", "02_febrero", "03_marzo", "04_abril",
    "05_mayo", "06_junio", "07_julio", "08_agosto",
    "09_septiembre", "10_octubre", "11_noviembre", "12_diciembre",
]

MESES_ES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]

# Mapeo de series (del asunto del correo) a sucursal
SERIE_A_SUCURSAL = {
    "S1": "Baalak",
    "PRADOS": "Prado",
    "PRADO": "Prado",
}

SUCURSALES_VALIDAS = {"Baalak", "Prado"}
SIN_SUCURSAL = "_sin_sucursal"


def inicializar():
    """Crea todas las carpetas necesarias."""
    for carpeta in (TEMPORALES, FACTURAS, RECHAZADOS, SIN_PDF,
                    DUPLICADOS, LOGS):
        carpeta.mkdir(parents=True, exist_ok=True)


def serie_a_sucursal(serie):
    """'S1' -> 'Baalak', 'Prados' -> 'Prado', 'S1/8448' -> 'Baalak', otro -> ''."""
    if not serie:
        return ""
    s = str(serie).strip().upper()
    # Si viene con slash, tomar la parte antes del slash (la serie)
    if "/" in s:
        s = s.split("/")[0].strip()
    return SERIE_A_SUCURSAL.get(s, "")


def _mes_de_fecha(fecha_iso):
    """'2026-10-15' -> (2026, '10_octubre')."""
    try:
        dt = datetime.strptime(fecha_iso[:10], "%Y-%m-%d")
    except (ValueError, TypeError):
        ahora = datetime.now()
        return ahora.year, MESES[ahora.month - 1]
    return dt.year, MESES[dt.month - 1]


def carpeta_factura(anio, mes, sucursal):
    """Ruta a uploads/facturas/<anio>/<mes>/<sucursal>/."""
    suc = sucursal if sucursal in SUCURSALES_VALIDAS else SIN_SUCURSAL
    return FACTURAS / str(anio) / mes / suc


def carpeta_rechazado(anio, mes):
    return RECHAZADOS / str(anio) / mes


def carpeta_sin_pdf(anio, mes):
    return SIN_PDF / str(anio) / mes


def carpeta_duplicado(anio, mes):
    return DUPLICADOS / str(anio) / mes


def mover_a_destino(xml_path, pdf_path, anio, mes, sucursal):
    """
    Mueve XML y PDF a la carpeta final.
    Si el archivo ya existe en destino, lo renombra con sufijo _1, _2...
    Devuelve (xml_final, pdf_final) con las rutas nuevas.
    """
    destino = carpeta_factura(anio, mes, sucursal)
    destino.mkdir(parents=True, exist_ok=True)

    def _mover(origen):
        if origen is None or not Path(origen).exists():
            return None
        origen = Path(origen)
        target = destino / origen.name
        contador = 1
        while target.exists():
            target = destino / f"{origen.stem}_{contador}{origen.suffix}"
            contador += 1
        shutil.move(str(origen), str(target))
        return target

    return _mover(xml_path), _mover(pdf_path)


def mover_a_rechazado(xml_path, pdf_path, anio, mes, error_msg=""):
    """Mueve el par a rechazados y escribe un .error.txt al lado."""
    destino = carpeta_rechazado(anio, mes)
    destino.mkdir(parents=True, exist_ok=True)

    def _mover(origen):
        if origen is None or not Path(origen).exists():
            return None
        origen = Path(origen)
        target = destino / origen.name
        contador = 1
        while target.exists():
            target = destino / f"{origen.stem}_{contador}{origen.suffix}"
            contador += 1
        shutil.move(str(origen), str(target))
        return target

    xml_final = _mover(xml_path)
    pdf_final = _mover(pdf_path)

    # Escribir .error.txt al lado del XML (o del PDF si no hay XML)
    referencia = xml_final or pdf_final
    if referencia and error_msg:
        error_path = referencia.with_suffix(".error.txt")
        error_path.write_text(
            f"Rechazado el {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"Error: {error_msg}\n",
            encoding="utf-8",
        )

    return xml_final, pdf_final


def mover_a_sin_pdf(xml_path, anio, mes):
    """Mueve un XML huérfano a sin_pdf/."""
    if xml_path is None or not Path(xml_path).exists():
        return None
    destino = carpeta_sin_pdf(anio, mes)
    destino.mkdir(parents=True, exist_ok=True)
    origen = Path(xml_path)
    target = destino / origen.name
    contador = 1
    while target.exists():
        target = destino / f"{origen.stem}_{contador}{origen.suffix}"
        contador += 1
    shutil.move(str(origen), str(target))
    return target


def mover_a_duplicado(xml_path, pdf_path, anio, mes):
    """Mueve un par duplicado a duplicados/."""
    destino = carpeta_duplicado(anio, mes)
    destino.mkdir(parents=True, exist_ok=True)

    def _mover(origen):
        if origen is None or not Path(origen).exists():
            return None
        origen = Path(origen)
        target = destino / origen.name
        contador = 1
        while target.exists():
            target = destino / f"{origen.stem}_{contador}{origen.suffix}"
            contador += 1
        shutil.move(str(origen), str(target))
        return target

    return _mover(xml_path), _mover(pdf_path)


def mover_entre_sucursales(anio, mes, sucursal_origen, sucursal_destino,
                            nombre_base):
    """
    Mueve un par XML+PDF de una sucursal a otra.
    nombre_base: 'S1-8386' o '8386' (sin extensión).
    Devuelve (ok, mensaje).
    """
    origen = carpeta_factura(anio, mes, sucursal_origen)
    destino = carpeta_factura(anio, mes, sucursal_destino)

    if not origen.exists():
        return False, f"No existe la carpeta de origen: {origen}"

    movidos = 0
    for ext in (".xml", ".pdf"):
        archivo = origen / f"{nombre_base}{ext}"
        if archivo.exists():
            destino.mkdir(parents=True, exist_ok=True)
            target = destino / archivo.name
            contador = 1
            while target.exists():
                target = destino / f"{archivo.stem}_{contador}{ext}"
                contador += 1
            shutil.move(str(archivo), str(target))
            movidos += 1

    return True, f"{movidos} archivo(s) movidos de {sucursal_origen} a {sucursal_destino}"


def buscar_archivos_factura(anio, mes, sucursal, nombre_base):
    """
    Devuelve (xml_path, pdf_path) si existen en la carpeta.
    nombre_base sin extensión.
    """
    carpeta = carpeta_factura(anio, mes, sucursal)
    if not carpeta.exists():
        return None, None
    xml_path = None
    pdf_path = None
    for f in carpeta.iterdir():
        if not f.is_file():
            continue
        if f.stem == nombre_base:
            if f.suffix.lower() == ".xml":
                xml_path = f
            elif f.suffix.lower() == ".pdf":
                pdf_path = f
    return xml_path, pdf_path


def resolver_path_upload(ruta_relativa):
    """
    Convierte 'facturas/2026/10_octubre/Baalak/8386.xml' en path absoluto.
    Verifica que esté dentro de UPLOADS (anti path-traversal).
    Devuelve Path o None si es inválido.
    """
    if not ruta_relativa:
        return None
    ruta_limpia = ruta_relativa.replace("\\", "/").lstrip("/")
    # Rechazar cualquier intento de subir de nivel
    if ".." in ruta_limpia.split("/"):
        return None
    candidato = (UPLOADS / ruta_limpia).resolve()
    try:
        candidato.relative_to(UPLOADS.resolve())
    except ValueError:
        return None
    if not candidato.exists() or not candidato.is_file():
        return None
    return candidato


def listar_archivos_factura(anio, mes, sucursal):
    """
    Devuelve lista de dicts con {xml, pdf} encontrados en la carpeta.
    Útil para el ZIP.
    """
    carpeta = carpeta_factura(anio, mes, sucursal)
    if not carpeta.exists():
        return []

    # Agrupar por nombre base
    grupos = {}
    for f in carpeta.iterdir():
        if not f.is_file():
            continue
        base = f.stem
        grupos.setdefault(base, {})
        if f.suffix.lower() == ".xml":
            grupos[base]["xml"] = f
        elif f.suffix.lower() == ".pdf":
            grupos[base]["pdf"] = f

    resultado = []
    for base, files in grupos.items():
        resultado.append({
            "nombre_base": base,
            "xml": files.get("xml"),
            "pdf": files.get("pdf"),
        })
    return resultado

def mover_y_renombrar(xml_path, pdf_path, anio, mes, sucursal, folio):
    """
    Mueve XML y PDF a destino final renombrándolos a <folio>.<ext>.
    Si ya existe un archivo con ese nombre, agrega sufijo _1, _2...
    Devuelve (xml_final, pdf_final).
    """
    destino = carpeta_factura(anio, mes, sucursal)
    destino.mkdir(parents=True, exist_ok=True)
    folio = str(folio).strip()
    if not folio:
        # Sin folio no podemos renombrar: usar el nombre original
        def _mover_sin_renombrar(origen):
            if origen is None or not Path(origen).exists():
                return None
            origen = Path(origen)
            target = destino / origen.name
            contador = 1
            while target.exists():
                target = destino / f"{origen.stem}_{contador}{origen.suffix}"
                contador += 1
            shutil.move(str(origen), str(target))
            return target
        return _mover_sin_renombrar(xml_path), _mover_sin_renombrar(pdf_path)

    def _mover(origen, extension):
        if origen is None or not Path(origen).exists():
            return None
        origen = Path(origen)
        target = destino / f"{folio}{extension}"
        contador = 1
        while target.exists():
            target = destino / f"{folio}_{contador}{extension}"
            contador += 1
        shutil.move(str(origen), str(target))
        return target

    return _mover(xml_path, ".xml"), _mover(pdf_path, ".pdf")

def reset_ingresos():
    """
    Borra TODOS los archivos del módulo Ingresos y el caché de correos.
    Devuelve un dict con estadísticas.
    """
    stats = {
        "archivos_borrados": 0,
        "carpetas_borradas": 0,
        "cache_borrado": False,
    }

    # 1. Borrar contenido de cada carpeta (excepto la carpeta raíz)
    for carpeta in (FACTURAS, RECHAZADOS, SIN_PDF, DUPLICADOS,
                    LOGS, TEMPORALES):
        if not carpeta.exists():
            continue
        for f in list(carpeta.rglob("*")):
            if f.is_file():
                try:
                    f.unlink()
                    stats["archivos_borrados"] += 1
                except Exception:
                    pass
        # Borrar subcarpetas vacías (de abajo hacia arriba)
        for d in sorted(carpeta.rglob("*"), reverse=True):
            if d.is_dir():
                try:
                    if not any(d.iterdir()):
                        d.rmdir()
                        stats["carpetas_borradas"] += 1
                except Exception:
                    pass

    # 2. Borrar caché de correos procesados
    cache = UPLOADS / "correos_procesados.json"
    if cache.exists():
        try:
            cache.unlink()
            stats["cache_borrado"] = True
        except Exception:
            pass

    return stats