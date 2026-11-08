"""
Script de reparación de archivos de Ingresos.
- Renombra XML/PDF a <folio>.<ext>
- Los mueve a uploads/facturas/<año>/<mes>/<sucursal>/
- Rellena datos_json en BD para los registros que lo tienen vacío
- Corrige sucursales inválidas ('Central') en la BD

Uso: python reparar_archivos.py
"""
import json
import re
import shutil
import sqlite3
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

from shared import uploads_manager as um
from lector_facturas import procesar_factura, agrupar_por_categoria
from routers.ingresos import _construir_datos_json

DB_PATH = Path(__file__).parent / "vetsuite.db"
UUID_RE = re.compile(
    r'[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}'
)


def extraer_uuid_xml(ruta_xml):
    try:
        root = ET.parse(ruta_xml).getroot()
        for elem in root.iter():
            if elem.tag.endswith('TimbreFiscalDigital'):
                return elem.get('UUID', '')
    except Exception:
        pass
    return ''


def extraer_info_xml(ruta_xml):
    """Devuelve dict con uuid, folio, serie, fecha (YYYY-MM-DD)."""
    try:
        root = ET.parse(ruta_xml).getroot()
        folio = (root.get('Folio') or '').strip()
        serie = (root.get('Serie') or '').strip()
        fecha_raw = root.get('Fecha', '')
        fecha_iso = ''
        if fecha_raw:
            try:
                fecha_iso = datetime.strptime(fecha_raw[:10], '%Y-%m-%d').strftime('%Y-%m-%d')
            except ValueError:
                pass
        uuid = ''
        for elem in root.iter():
            if elem.tag.endswith('TimbreFiscalDigital'):
                uuid = elem.get('UUID', '')
                break
        return {
            'uuid': uuid,
            'folio': folio,
            'serie': serie,
            'fecha': fecha_iso,
        }
    except Exception:
        return None


def extraer_uuid_pdf(ruta_pdf):
    """Busca el UUID en el texto del PDF."""
    try:
        import pdfplumber
        with pdfplumber.open(ruta_pdf) as pdf:
            texto = "\n".join((p.extract_text() or '') for p in pdf.pages)
        m = UUID_RE.search(texto)
        if m:
            return m.group().lower()
    except Exception:
        pass
    return ''


def main():
    print("=" * 60)
    print("REPARACIÓN DE ARCHIVOS DE INGRESOS")
    print("=" * 60)

    um.inicializar()

    # ============================================================
    # 1. Escanear todos los XMLs y PDFs en uploads/facturas y uploads/duplicados
    # ============================================================
    print("\n[1/5] Escaneando archivos...")
    xmls = []
    pdfs = []
    for base in (um.FACTURAS, um.DUPLICADOS):
        if base.exists():
            for f in base.rglob("*"):
                if not f.is_file():
                    continue
                ext = f.suffix.lower()
                if ext == ".xml":
                    xmls.append(f)
                elif ext == ".pdf":
                    pdfs.append(f)

    print(f"  XMLs encontrados: {len(xmls)}")
    print(f"  PDFs encontrados: {len(pdfs)}")

    # ============================================================
    # 2. Extraer info de cada XML
    # ============================================================
    print("\n[2/5] Extrayendo info de XMLs...")
    info_xml = {}
    for f in xmls:
        info = extraer_info_xml(f)
        if info and info["uuid"]:
            info_xml[info["uuid"].lower()] = {
                **info,
                "path": f,
            }

    print(f"  XMLs con UUID válido: {len(info_xml)}")

    # ============================================================
    # 3. Emparejar con PDFs por UUID
    # ============================================================
    print("\n[3/5] Emparejando con PDFs (por UUID)...")
    pares = {}
    pdf_huerfanos = []

    for f in pdfs:
        uuid = extraer_uuid_pdf(f)
        if uuid and uuid in info_xml:
            pares[uuid] = {
                "xml": info_xml[uuid]["path"],
                "pdf": f,
                "folio": info_xml[uuid]["folio"],
                "serie": info_xml[uuid]["serie"],
                "fecha": info_xml[uuid]["fecha"],
            }
        else:
            pdf_huerfanos.append(f)

    # XMLs sin PDF
    xml_sin_pdf = []
    for uuid, info in info_xml.items():
        if uuid not in pares:
            xml_sin_pdf.append(info["path"])

    print(f"  Pares XML+PDF: {len(pares)}")
    print(f"  XMLs sin PDF:  {len(xml_sin_pdf)}")
    print(f"  PDFs huérfanos: {len(pdf_huerfanos)}")

    # ============================================================
    # 4. Renombrar y mover pares
    # ============================================================
    print("\n[4/5] Renombrando y moviendo archivos...")
    movidos = 0
    renombrados = 0

    for uuid, p in pares.items():
        serie = p["serie"]
        folio = p["folio"]
        fecha = p["fecha"]
        sucursal = um.serie_a_sucursal(serie)
        anio, mes = um._mes_de_fecha(fecha)
        destino = um.carpeta_factura(anio, mes, sucursal)
        destino.mkdir(parents=True, exist_ok=True)

        try:
            target_xml = destino / f"{folio}.xml"
            if p["xml"].resolve() != target_xml.resolve():
                if target_xml.exists() and target_xml.resolve() != p["xml"].resolve():
                    target_xml = destino / f"{folio}_{uuid[:6]}.xml"
                shutil.move(str(p["xml"]), str(target_xml))
                renombrados += 1

            target_pdf = destino / f"{folio}.pdf"
            if p["pdf"].resolve() != target_pdf.resolve():
                if target_pdf.exists() and target_pdf.resolve() != p["pdf"].resolve():
                    target_pdf = destino / f"{folio}_{uuid[:6]}.pdf"
                shutil.move(str(p["pdf"]), str(target_pdf))
                renombrados += 1

            movidos += 1
        except Exception as e:
            print(f"  Error con {folio}: {e}")

    print(f"  Pares movidos: {movidos}")
    print(f"  Archivos renombrados: {renombrados}")

    # XMLs sin PDF: renombrar y mover a sin_pdf
    for xml_path in xml_sin_pdf:
        info = None
        for uuid, i in info_xml.items():
            if i["path"] == xml_path:
                info = i
                break
        if not info:
            continue
        anio, mes = um._mes_de_fecha(info["fecha"])
        destino = um.carpeta_sin_pdf(anio, mes)
        destino.mkdir(parents=True, exist_ok=True)
        target = destino / f"{info['folio']}.xml"
        try:
            shutil.move(str(xml_path), str(target))
        except Exception:
            pass

    # ============================================================
    # 5. Actualizar BD: datos_json y sucursal
    # ============================================================
    print("\n[5/5] Actualizando base de datos...")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    actualizados_datos = 0
    actualizados_sucursal = 0

    # 5a. Primero, para cada par, si el registro existe sin datos_json, procesarlo
    for uuid, p in pares.items():
        row = conn.execute(
            "SELECT id, datos_json FROM ingresos WHERE folio_fiscal = ?",
            (uuid,),
        ).fetchone()
        if not row:
            continue

        tiene_datos = row["datos_json"] and row["datos_json"].strip()
        if tiene_datos:
            continue

        # Procesar
        xml_final = um.carpeta_factura(*um._mes_de_fecha(p["fecha"]), um.serie_a_sucursal(p["serie"])) / f"{p['folio']}.xml"
        pdf_final = um.carpeta_factura(*um._mes_de_fecha(p["fecha"]), um.serie_a_sucursal(p["serie"])) / f"{p['folio']}.pdf"

        if not (xml_final.exists() and pdf_final.exists()):
            continue

        try:
            datos = procesar_factura(str(xml_final), str(pdf_final))
            agrupado, detalle, _, _ = agrupar_por_categoria(datos)
            datos_completos = _construir_datos_json(datos, agrupado, detalle)
            conn.execute(
                "UPDATE ingresos SET datos_json = ?, sucursal = ? WHERE id = ?",
                (
                    json.dumps(datos_completos, ensure_ascii=False, default=str),
                    um.serie_a_sucursal(p["serie"]),
                    row["id"],
                ),
            )
            actualizados_datos += 1
        except Exception as e:
            print(f"  Error procesando {p['folio']}: {e}")

    # 5b. Corregir sucursales inválidas (Central, vacías) para registros sin archivo
    invalidas = conn.execute(
        "SELECT id, folio, folio_fiscal, sucursal, notas FROM ingresos "
        "WHERE sucursal NOT IN ('Baalak', 'Prado') OR sucursal IS NULL OR sucursal = ''"
    ).fetchall()

    for r in invalidas:
        notas = (r["notas"] or "").strip()
        serie = notas.split("/")[0] if "/" in notas else ""
        suc = um.serie_a_sucursal(serie)
        if suc:
            conn.execute(
                "UPDATE ingresos SET sucursal = ? WHERE id = ?",
                (suc, r["id"]),
            )
            actualizados_sucursal += 1
        else:
            # Marcar como _sin_sucursal
            conn.execute(
                "UPDATE ingresos SET sucursal = '_sin_sucursal' WHERE id = ?",
                (r["id"],),
            )
            actualizados_sucursal += 1

    conn.commit()
    conn.close()

    print(f"  Registros con datos_json actualizados: {actualizados_datos}")
    print(f"  Registros con sucursal corregida: {actualizados_sucursal}")

    print("\n" + "=" * 60)
    print("REPARACIÓN COMPLETA")
    print("=" * 60)


if __name__ == "__main__":
    main()