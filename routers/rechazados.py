"""
Página de rechazados, sin_pdf y duplicados del módulo Ingresos.
Permite ver, rescatar, reemplazar PDF y eliminar.
"""
import json
import shutil
import tempfile
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, PlainTextResponse

from shared.templates_shared import templates

from shared.db import get_conn
from shared import uploads_manager as um
from ingresos.lector_facturas import (
    procesar_factura,
    agrupar_por_categoria,
    leer_xml_factura,
)

router = APIRouter(prefix="/ingresos/rechazados", tags=["ingresos"])
BASE_DIR = Path(__file__).parent.parent


# ============================================================
# HELPERS
# ============================================================
def _leer_error_txt(ruta_referencia):
    """Busca un .error.txt al lado del XML o PDF y devuelve su contenido."""
    for ext in (".xml", ".pdf", ".PDF"):
        candidato = ruta_referencia.with_suffix(ext)
        if candidato.exists():
            error_path = candidato.with_suffix(".error.txt")
            if error_path.exists():
                try:
                    return error_path.read_text(encoding="utf-8")
                except Exception:
                    return ""
    return ""


def _buscar_uuid_bd(conn, uuid):
    if not uuid:
        return None
    return conn.execute(
        "SELECT id, fecha, folio, sucursal FROM ingresos WHERE folio_fiscal = ?",
        (uuid,),
    ).fetchone()


def _listar_carpeta(base):
    """
    Devuelve lista de dicts:
    [
      {
        "carpeta_rel": "2026/10_octubre",
        "nombre_base": "8410",
        "xml": Path | None,
        "pdf": Path | None,
        "error": str,
      },
      ...
    ]
    Agrupa por nombre base. Excluye .error.txt y otros.
    """
    resultado = []
    if not base.exists():
        return resultado

    # Agrupar por carpeta + nombre base
    grupos = {}
    for f in base.rglob("*"):
        if not f.is_file():
            continue
        if f.suffix.lower() not in (".xml", ".pdf"):
            continue
        rel_padre = f.parent.relative_to(base)
        clave = (str(rel_padre), f.stem)
        grupos.setdefault(clave, {"xml": None, "pdf": None})

        if f.suffix.lower() == ".xml":
            grupos[clave]["xml"] = f
        elif f.suffix.lower() == ".pdf":
            grupos[clave]["pdf"] = f

    for (carpeta_rel, nombre_base), files in grupos.items():
        error = ""
        referencia = files["xml"] or files["pdf"]
        if referencia:
            error = _leer_error_txt(referencia)

        resultado.append({
            "carpeta_rel": carpeta_rel,
            "nombre_base": nombre_base,
            "xml": files["xml"],
            "pdf": files["pdf"],
            "error": error,
        })

    # Ordenar por carpeta y nombre
    resultado.sort(key=lambda x: (x["carpeta_rel"], x["nombre_base"]))
    return resultado


def _resolver_ruta_upload(path):
    """Devuelve la ruta relativa a uploads/ para usar en el endpoint /uploads."""
    try:
        return path.relative_to(um.UPLOADS).as_posix()
    except Exception:
        return ""


# ============================================================
# LISTAR
# ============================================================
@router.get("", response_class=HTMLResponse)
def listar(request: Request, mensaje: str = "", tab: str = "rechazados"):
    rechazados = _listar_carpeta(um.RECHAZADOS)
    sin_pdf = _listar_carpeta(um.SIN_PDF)
    duplicados = _listar_carpeta(um.DUPLICADOS)

    # Para cada rechazado, intentar leer el XML (folio, uuid, fecha)
    conn = get_conn()
    for item in rechazados:
        item["info"] = None
        if item["xml"]:
            try:
                info = leer_xml_factura(str(item["xml"]))
                item["info"] = info
            except Exception:
                pass
        item["en_bd"] = None
        if item["info"] and item["info"].get("folio_fiscal"):
            item["en_bd"] = _buscar_uuid_bd(conn, item["info"]["folio_fiscal"])

    for item in sin_pdf:
        item["info"] = None
        if item["xml"]:
            try:
                info = leer_xml_factura(str(item["xml"]))
                item["info"] = info
            except Exception:
                pass

    for item in duplicados:
        item["info"] = None
        if item["xml"]:
            try:
                info = leer_xml_factura(str(item["xml"]))
                item["info"] = info
            except Exception:
                pass
        item["en_bd"] = None
        if item["info"] and item["info"].get("folio_fiscal"):
            item["en_bd"] = _buscar_uuid_bd(conn, item["info"]["folio_fiscal"])

    conn.close()

    return templates.TemplateResponse(
        "rechazados.html",
        {
            "request": request,
            "rechazados": rechazados,
            "sin_pdf": sin_pdf,
            "duplicados": duplicados,
            "mensaje": mensaje,
            "tab": tab,
            "n_rechazados": len(rechazados),
            "n_sin_pdf": len(sin_pdf),
            "n_duplicados": len(duplicados),
        },
    )


# ============================================================
# VER ARCHIVOS
# ============================================================
@router.get("/ver/{tipo}/{carpeta_rel:path}/{nombre}/{ext}")
def ver_archivo(
    tipo: str, carpeta_rel: str, nombre: str, ext: str
):
    """Redirige al endpoint /uploads que ya sirve archivos."""
    base_map = {
        "rechazados": um.RECHAZADOS,
        "sin_pdf": um.SIN_PDF,
        "duplicados": um.DUPLICADOS,
    }
    base = base_map.get(tipo)
    if not base:
        return RedirectResponse("/ingresos/rechazados", status_code=303)

    archivo = base / carpeta_rel / f"{nombre}.{ext}"
    if not archivo.exists():
        return RedirectResponse(
            "/ingresos/rechazados?mensaje=Archivo no encontrado",
            status_code=303,
        )

    ruta_rel = _resolver_ruta_upload(archivo)
    return RedirectResponse(f"/uploads/{ruta_rel}", status_code=303)


# ============================================================
# ELIMINAR
# ============================================================
@router.post("/eliminar/{tipo}")
def eliminar(
    tipo: str,
    carpeta_rel: str = Form(...),
    nombre: str = Form(...),
):
    base_map = {
        "rechazados": um.RECHAZADOS,
        "sin_pdf": um.SIN_PDF,
        "duplicados": um.DUPLICADOS,
    }
    base = base_map.get(tipo)
    if not base:
        return RedirectResponse(
            "/ingresos/rechazados?mensaje=Tipo invalido",
            status_code=303,
        )

    eliminados = 0
    for ext in (".xml", ".pdf"):
        f = base / carpeta_rel / f"{nombre}{ext}"
        if f.exists():
            try:
                f.unlink()
                eliminados += 1
            except Exception:
                pass
        # También buscar el .error.txt
        error_f = base / carpeta_rel / f"{nombre}.error.txt"
        if error_f.exists():
            try:
                error_f.unlink()
            except Exception:
                pass

    # Si la carpeta quedó vacía, eliminarla
    carpeta = base / carpeta_rel
    if carpeta.exists():
        try:
            if not any(carpeta.iterdir()):
                carpeta.rmdir()
        except Exception:
            pass

    return RedirectResponse(
        f"/ingresos/rechazados?mensaje={eliminados} archivo(s) eliminados",
        status_code=303,
    )


@router.post("/eliminar-todos-duplicados")
def eliminar_todos_duplicados():
    if not um.DUPLICADOS.exists():
        return RedirectResponse(
            "/ingresos/rechazados?mensaje=No hay duplicados",
            status_code=303,
        )
    eliminados = 0
    for f in list(um.DUPLICADOS.rglob("*")):
        if f.is_file():
            try:
                f.unlink()
                eliminados += 1
            except Exception:
                pass
    # Borrar carpetas vacías
    for d in sorted(um.DUPLICADOS.rglob("*"), reverse=True):
        if d.is_dir():
            try:
                if not any(d.iterdir()):
                    d.rmdir()
            except Exception:
                pass

    return RedirectResponse(
        f"/ingresos/rechazados?mensaje={eliminados} archivo(s) duplicados eliminados&tab=duplicados",
        status_code=303,
    )


# ============================================================
# RESCATAR
# ============================================================
@router.get("/rescatar/{carpeta_rel:path}/{nombre}", response_class=HTMLResponse)
def rescatar_form(request: Request, carpeta_rel: str, nombre: str):
    """Formulario prellenado para rescatar un rechazado."""
    xml_path = um.RECHAZADOS / carpeta_rel / f"{nombre}.xml"
    if not xml_path.exists():
        # Buscar alternativas (puede que esté solo el PDF)
        for f in (um.RECHAZADOS / carpeta_rel).glob(f"{nombre}.*"):
            if f.suffix.lower() == ".xml":
                xml_path = f
                break
        else:
            return RedirectResponse(
                "/ingresos/rechazados?mensaje=No se encontro el XML",
                status_code=303,
            )

    info = {}
    try:
        info = leer_xml_factura(str(xml_path))
    except Exception:
        pass

    fecha_iso = ""
    if info.get("fecha"):
        try:
            fecha_iso = datetime.strptime(
                info["fecha"], "%d/%m/%Y"
            ).strftime("%Y-%m-%d")
        except ValueError:
            fecha_iso = ""

    return templates.TemplateResponse(
        "rechazados_rescatar.html",
        {
            "request": request,
            "carpeta_rel": carpeta_rel,
            "nombre": nombre,
            "prefill": {
                "fecha": fecha_iso,
                "folio": info.get("no_factura", ""),
                "folio_fiscal": info.get("folio_fiscal", ""),
                "cliente": info.get("nombre", ""),
                "rfc": info.get("rfc", ""),
                "total": info.get("total", 0),
                "notas": info.get("qvet", ""),
            },
        },
    )


@router.post("/rescatar/{carpeta_rel:path}/{nombre}")
def rescatar_guardar(
    carpeta_rel: str,
    nombre: str,
    fecha: str = Form(...),
    folio: str = Form(""),
    folio_fiscal: str = Form(""),
    cliente: str = Form(""),
    rfc: str = Form(""),
    total: float = Form(0),
    sucursal: str = Form(""),
    notas: str = Form(""),
):
    """
    Inserta el registro con datos_json = NULL (no hay productos).
    Mueve los archivos a facturas/ y elimina los de rechazados/.
    """
    conn = get_conn()
    conn.execute(
        "INSERT INTO ingresos "
        "(fecha, folio, folio_fiscal, cliente, rfc, total, sucursal, notas, datos_json) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL)",
        (fecha, folio, folio_fiscal, cliente, rfc, total, sucursal, notas),
    )
    conn.commit()
    conn.close()

    # Mover archivos a facturas/
    xml_path = um.RECHAZADOS / carpeta_rel / f"{nombre}.xml"
    pdf_path = None
    for f in (um.RECHAZADOS / carpeta_rel).glob(f"{nombre}.*"):
        if f.suffix.lower() == ".pdf":
            pdf_path = f
            break

    anio, mes = um._mes_de_fecha(fecha)
    if xml_path.exists() or pdf_path:
        um.mover_y_renombrar(xml_path, pdf_path, anio, mes, sucursal, folio)

    # Eliminar .error.txt
    error_f = um.RECHAZADOS / carpeta_rel / f"{nombre}.error.txt"
    if error_f.exists():
        try:
            error_f.unlink()
        except Exception:
            pass

    # Borrar carpeta si quedó vacía
    carpeta = um.RECHAZADOS / carpeta_rel
    if carpeta.exists():
        try:
            if not any(carpeta.iterdir()):
                carpeta.rmdir()
        except Exception:
            pass

    return RedirectResponse(
        f"/ingresos/rechazados?mensaje=Factura {folio} rescatada",
        status_code=303,
    )


# ============================================================
# REEMPLAZAR PDF
# ============================================================
@router.post("/reemplazar-pdf/{carpeta_rel}/{nombre}")
async def reemplazar_pdf(
    carpeta_rel: str,
    nombre: str,
    pdf: UploadFile = File(...),
):
    """
    Reemplaza el PDF de un rechazado y reintenta el parseo.
    Si el parseo tiene éxito, mueve todo a facturas/ y guarda en BD.
    Si falla, deja los archivos en rechazados/ y actualiza el .error.txt.
    """
    carpeta = um.RECHAZADOS / carpeta_rel
    xml_path = carpeta / f"{nombre}.xml"

    if not xml_path.exists():
        return RedirectResponse(
            "/ingresos/rechazados?mensaje=No se encontro el XML original",
            status_code=303,
        )

    # Guardar el PDF nuevo (reemplazando el anterior si existe)
    pdf_viejo = None
    for f in carpeta.glob(f"{nombre}.*"):
        if f.suffix.lower() == ".pdf":
            pdf_viejo = f
            break

    pdf_path = carpeta / f"{nombre}.pdf"
    with open(pdf_path, "wb") as f:
        shutil.copyfileobj(pdf.file, f)

    if pdf_viejo and pdf_viejo != pdf_path and pdf_viejo.exists():
        try:
            pdf_viejo.unlink()
        except Exception:
            pass

    # Intentar procesar
    try:
        datos = procesar_factura(str(xml_path), str(pdf_path))
        agrupado, detalle, _, _ = agrupar_por_categoria(datos)

        # Construir datos_json
        from routers.ingresos import _construir_datos_json
        datos_completos = _construir_datos_json(datos, agrupado, detalle)

        fecha_iso = ""
        if datos.get("fecha"):
            try:
                fecha_iso = datetime.strptime(
                    datos["fecha"], "%d/%m/%Y"
                ).strftime("%Y-%m-%d")
            except ValueError:
                fecha_iso = ""

        # Determinar sucursal por serie del XML
        serie = (datos.get("serie") or "").strip()
        sucursal = um.serie_a_sucursal(serie)

        anio, mes = um._mes_de_fecha(fecha_iso)

        conn = get_conn()
        conn.execute(
            "INSERT INTO ingresos "
            "(fecha, folio, folio_fiscal, cliente, rfc, total, sucursal, notas, datos_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                fecha_iso,
                datos.get("no_factura", ""),
                datos.get("folio_fiscal", ""),
                datos.get("nombre", ""),
                datos.get("rfc", ""),
                datos.get("total", 0),
                sucursal,
                datos.get("qvet", ""),
                json.dumps(datos_completos, ensure_ascii=False, default=str),
            ),
        )
        conn.commit()
        conn.close()

        # Mover a facturas/
        um.mover_y_renombrar(
            xml_path, pdf_path, anio, mes, sucursal,
            datos.get("no_factura", ""),
        )

        # Eliminar .error.txt
        error_f = carpeta / f"{nombre}.error.txt"
        if error_f.exists():
            try:
                error_f.unlink()
            except Exception:
                pass

        # Borrar carpeta si quedó vacía
        if carpeta.exists():
            try:
                if not any(carpeta.iterdir()):
                    carpeta.rmdir()
            except Exception:
                pass

        return RedirectResponse(
            f"/ingresos/rechazados?mensaje=Factura {datos.get('no_factura')} procesada correctamente",
            status_code=303,
        )

    except Exception as e:
        # Parseo falló de nuevo: actualizar .error.txt
        error_path = carpeta / f"{nombre}.error.txt"
        error_path.write_text(
            f"Reintento el {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"Error: {e}\n",
            encoding="utf-8",
        )
        return RedirectResponse(
            f"/ingresos/rechazados?mensaje=El PDF corregido sigue fallando: {str(e)[:80]}",
            status_code=303,
        )