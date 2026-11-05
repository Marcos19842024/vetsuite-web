"""
Gestor de archivos de Egresos.
Centraliza rutas y operaciones: guardar XML, generar PDF, mover a PUE/PPD, etc.
"""
import shutil
from datetime import datetime
from pathlib import Path


BASE_DIR = Path(__file__).parent.parent
UPLOADS = BASE_DIR / "uploads" / "egresos"
TEMPORALES = UPLOADS / "temporales"
XMLS = UPLOADS / "xml"
PDFS = UPLOADS / "pdf"
RECHAZADOS = UPLOADS / "rechazados"
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

SUCURSALES = {"Baalak", "Animalia"}
METODOS = {"PUE", "PPD"}
FORMAS = {"Efectivo", "TC", "TD", "Transferencia", "PPD"}


def inicializar():
    for carpeta in (TEMPORALES, XMLS, PDFS, RECHAZADOS, LOGS):
        carpeta.mkdir(parents=True, exist_ok=True)


def _mes_de_fecha(fecha_iso):
    """'2026-10-15' -> (2026, '10_octubre')."""
    try:
        dt = datetime.strptime(fecha_iso[:10], "%Y-%m-%d")
    except (ValueError, TypeError):
        ahora = datetime.now()
        return ahora.year, MESES[ahora.month - 1]
    return dt.year, MESES[dt.month - 1]


def carpeta_xml(anio, mes, sucursal, metodo, forma):
    """uploads/egresos/xml/<año>/<mes>/<sucursal>/<metodo>/<forma>/."""
    suc = sucursal if sucursal in SUCURSALES else "Baalak"
    met = metodo if metodo in METODOS else "PUE"
    frm = forma if forma in FORMAS else "Efectivo"
    return XMLS / str(anio) / mes / suc / met / frm


def carpeta_pdf(anio, mes, sucursal, metodo, forma):
    """uploads/egresos/pdf/<año>/<mes>/<sucursal>/<metodo>/<forma>/."""
    suc = sucursal if sucursal in SUCURSALES else "Baalak"
    met = metodo if metodo in METODOS else "PUE"
    frm = forma if forma in FORMAS else "Efectivo"
    return PDFS / str(anio) / mes / suc / met / frm


def carpeta_rechazado(anio, mes):
    return RECHAZADOS / str(anio) / mes


def mover_xml_a_destino(xml_path, anio, mes, sucursal, metodo, forma,
                         serie="", folio=""):
    """
    Mueve un XML a su carpeta final y lo renombra.
    Devuelve el Path final.
    """
    destino = carpeta_xml(anio, mes, sucursal, metodo, forma)
    destino.mkdir(parents=True, exist_ok=True)

    if not folio:
        folio = Path(xml_path).stem

    nombre = f"{serie}-{folio}.xml" if serie else f"{folio}.xml"
    target = destino / nombre
    contador = 1
    while target.exists():
        base = Path(nombre).stem
        target = destino / f"{base}_{contador}.xml"
        contador += 1

    shutil.move(str(xml_path), str(target))
    return target


def generar_pdf_desde_xml(xml_path, anio, mes, sucursal, metodo, forma,
                           serie="", folio=""):
    """
    Genera un PDF a partir de un XML y lo guarda en la carpeta de PDFs.
    El PDF se nombra igual que el XML (serie-folio.pdf o folio.pdf).
    Devuelve el Path al PDF generado, o None si falla.
    """
    try:
        from cfdi_pdf import CFDIPDF

        destino = carpeta_pdf(anio, mes, sucursal, metodo, forma)
        destino.mkdir(parents=True, exist_ok=True)

        pdf_gen = CFDIPDF(template="minimal")
        pdf_bytes, filename_original = pdf_gen.render_bytes(xml_path=str(xml_path))

        # Renombrar al mismo nombre base que el XML
        if folio:
            nombre_base = f"{serie}-{folio}" if serie else folio
            target = destino / f"{nombre_base}.pdf"
        else:
            target = destino / filename_original

        # Si ya existe, agregar sufijo
        contador = 1
        while target.exists():
            base = target.stem
            if "_" not in base.split("-")[-1]:
                target = destino / f"{base}_{contador}.pdf"
            else:
                target = destino / f"{base}_{contador}.pdf"
            contador += 1

        with open(target, "wb") as f:
            f.write(pdf_bytes)

        return target
    except Exception as e:
        print(f"WARN: No se pudo generar PDF para {xml_path}: {e}")
        return None


def mover_a_rechazado(xml_path, anio, mes, error_msg=""):
    """Mueve un XML inválido a rechazados con un .error.txt al lado."""
    destino = carpeta_rechazado(anio, mes)
    destino.mkdir(parents=True, exist_ok=True)

    xml_final = destino / Path(xml_path).name
    contador = 1
    while xml_final.exists():
        xml_final = destino / f"{Path(xml_path).stem}_{contador}.xml"
        contador += 1

    shutil.move(str(xml_path), str(xml_final))

    if error_msg:
        error_path = xml_final.with_suffix(".error.txt")
        error_path.write_text(
            f"Rechazado el {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"Error: {error_msg}\n",
            encoding="utf-8",
        )
    return xml_final


def mover_xml_a_sucursal(xml_path, sucursal_actual, sucursal_destino,
                          metodo, forma, anio, mes, serie="", folio=""):
    """
    Mueve un XML de una sucursal a otra (ej. Animalia → Baalak).
    También mueve el PDF correspondiente si existe.
    Devuelve (ok, mensaje).
    """
    origen = carpeta_xml(anio, mes, sucursal_actual, metodo, forma)
    destino = carpeta_xml(anio, mes, sucursal_destino, metodo, forma)
    destino.mkdir(parents=True, exist_ok=True)

    xml_path = Path(xml_path)
    if not xml_path.exists():
        return False, f"No existe el archivo: {xml_path}"

    # Renombrar según serie/folio
    if not folio:
        folio = xml_path.stem
    nombre = f"{serie}-{folio}.xml" if serie else f"{folio}.xml"
    target = destino / nombre
    contador = 1
    while target.exists():
        base = Path(nombre).stem
        target = destino / f"{base}_{contador}.xml"
        contador += 1

    try:
        shutil.move(str(xml_path), str(target))

        # Mover el PDF si existe
        pdf_origen_dir = carpeta_pdf(anio, mes, sucursal_actual, metodo, forma)
        pdf_destino_dir = carpeta_pdf(anio, mes, sucursal_destino, metodo, forma)
        if pdf_origen_dir.exists():
            pdf_nombre = f"{serie}-{folio}.pdf" if serie else f"{folio}.pdf"
            pdf_origen = pdf_origen_dir / pdf_nombre
            if pdf_origen.exists():
                pdf_destino_dir.mkdir(parents=True, exist_ok=True)
                pdf_target = pdf_destino_dir / pdf_nombre
                contador = 1
                while pdf_target.exists():
                    base = Path(pdf_nombre).stem
                    pdf_target = pdf_destino_dir / f"{base}_{contador}.pdf"
                    contador += 1
                shutil.move(str(pdf_origen), str(pdf_target))

        return True, str(target)
    except Exception as e:
        return False, str(e)


def resolver_path_upload(ruta_relativa):
    """Convierte ruta relativa en path absoluto con anti-traversal."""
    if not ruta_relativa:
        return None
    ruta_limpia = ruta_relativa.replace("\\", "/").lstrip("/")
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


def listar_xmls_mes(anio, mes, sucursal=None):
    """
    Lista todos los XMLs de un mes (opcionalmente de una sucursal).
    Devuelve lista de dicts: {path, sucursal, metodo, forma, serie, folio}.
    """
    base = XMLS / str(anio) / mes
    if not base.exists():
        return []

    resultado = []
    for f in base.rglob("*.xml"):
        if not f.is_file():
            continue
        partes = f.relative_to(base).parts
        if len(partes) < 3:
            continue
        suc = partes[0]
        met = partes[1]
        frm = partes[2]
        if sucursal and suc != sucursal:
            continue
        resultado.append({
            "path": f,
            "sucursal": suc,
            "metodo": met,
            "forma": frm,
            "nombre": f.stem,
        })
    return resultado