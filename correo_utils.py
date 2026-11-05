"""
Agrupa los archivos descargados del correo (XML+PDF por correo).
"""
import re
import xml.etree.ElementTree as ET
from pathlib import Path


def agrupar_facturas_descargadas(carpeta, archivos_por_correo=None):
    grupos = {}
    contador = 0

    if archivos_por_correo:
        for _, archivos in archivos_por_correo.items():
            xml_path = None
            pdf_path = None

            for ruta_str in archivos:
                ruta = Path(ruta_str)
                if not ruta.exists():
                    continue
                ext = ruta.suffix.lower()
                if ext == ".xml" and xml_path is None:
                    xml_path = ruta
                elif ext == ".pdf" and pdf_path is None:
                    pdf_path = ruta

            if not xml_path:
                continue

            try:
                NS = {"cfdi": "http://www.sat.gob.mx/cfd/4"}
                tree = ET.parse(str(xml_path))
                root = tree.getroot()
                folio = (root.get("Folio") or "").strip()
                serie = (root.get("Serie") or "").strip()
                if folio.isdigit():
                    folio = str(int(folio))
                uuid = ""
                for elem in root.iter():
                    if elem.tag.endswith("TimbreFiscalDigital"):
                        uuid = elem.get("UUID", "")
                        break
            except Exception:
                continue

            contador += 1
            grupos[contador] = {
                "xml": xml_path,
                "pdf": pdf_path,
                "no_factura": folio,
                "serie": serie,
                "uuid": uuid,
            }

        return grupos

    for archivo in sorted(carpeta.glob("*.xml")):
        try:
            NS = {"cfdi": "http://www.sat.gob.mx/cfd/4"}
            tree = ET.parse(str(archivo))
            root = tree.getroot()
            folio = (root.get("Folio") or "").strip()
            serie = (root.get("Serie") or "").strip()
            if folio.isdigit():
                folio = str(int(folio))
            if not folio:
                continue
            uuid = ""
            for elem in root.iter():
                if elem.tag.endswith("TimbreFiscalDigital"):
                    uuid = elem.get("UUID", "")
                    break
            contador += 1
            grupos[f"grupo_{contador}"] = {
                "xml": archivo,
                "pdf": None,
                "no_factura": folio,
                "serie": serie,
                "uuid": uuid,
            }
        except Exception:
            continue

    for archivo in sorted(carpeta.glob("*.pdf")):
        nombre = archivo.stem
        no_factura = None
        partes = nombre.split("_")
        if partes and partes[-1].isdigit():
            no_factura = str(int(partes[-1]))
        if not no_factura:
            m = re.search(r"_(\d+)$", nombre)
            if m:
                no_factura = str(int(m.group(1)))
        if not no_factura:
            digitos = re.findall(r"\d+", nombre)
            if digitos:
                no_factura = str(int(max(digitos, key=len)))
        if not no_factura:
            continue
        for clave, grp in grupos.items():
            if grp.get("no_factura") == no_factura and grp.get("pdf") is None:
                grp["pdf"] = archivo
                break

    return grupos