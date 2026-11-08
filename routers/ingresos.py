import json
import shutil
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, Form, UploadFile, File, BackgroundTasks
from fastapi.responses import (
    HTMLResponse, RedirectResponse, JSONResponse, FileResponse,
)

from shared.templates_shared import templates

from shared.db import get_conn
from lector_facturas import (
    cargar_catalogo,
    procesar_factura,
    agrupar_por_categoria,
    agregar_producto_catalogo,
    borrar_producto_catalogo,
    recargar_catalogo,
    cargar_excepciones_manuales,
    normalizar
)
from shared import jobs
from shared import uploads_manager as um
from correo_facturas import descargar_adjuntos_gmail
from correo_utils import agrupar_facturas_descargadas
from excel_web import generar_excel
from zip_generador import generar_zip_mensual

router = APIRouter(prefix="/ingresos", tags=["ingresos"])

BASE_DIR = Path(__file__).parent.parent
GMAIL_CONFIG = BASE_DIR / "gmail_config.json"

CATEGORIAS = ["U", "ACCESORIOS", "MEDICAMENTOS", "HIGIENE",
              "ESTETICA", "TRANSPORTE", "PENSION", "VACUNA", "CLINICA"]

um.inicializar()


def _listar_sucursales(conn):
    return [r["sucursal"] for r in conn.execute(
        "SELECT DISTINCT sucursal FROM ingresos WHERE sucursal <> '' ORDER BY sucursal"
    ).fetchall()]


def _cargar_config_gmail():
    if not GMAIL_CONFIG.exists():
        return {}
    try:
        return json.loads(GMAIL_CONFIG.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _contar_rechazados():
    total = 0
    for base in (um.RECHAZADOS, um.SIN_PDF, um.DUPLICADOS):
        if base.exists():
            for f in base.rglob("*.error.txt"):
                total += 1
            for f in base.rglob("*.xml"):
                if not (f.with_suffix(".error.txt")).exists():
                    total += 1
    return total


def _construir_datos_json(datos, agrupado, detalle):
    """Arma el dict completo que se guarda en la columna datos_json."""
    datos_completos = dict(datos)
    mapa = {
        ("U", "importe"): "u_importe",
        ("U", "iva"): "u_iva",
        ("ACCESORIOS", "importe"): "ac_importe",
        ("ACCESORIOS", "iva"): "ac_iva",
        ("MEDICAMENTOS", "importe"): "med_importe",
        ("MEDICAMENTOS", "sin_iva"): "med_sin_iva",
        ("MEDICAMENTOS", "iva"): "med_iva",
        ("HIGIENE", "importe"): "hig_importe",
        ("HIGIENE", "sin_iva"): "hig_sin_iva",
        ("HIGIENE", "iva"): "hig_iva",
        ("HIGIENE", "sin_ieps_6"): "hig_sin_ieps_6",
        ("HIGIENE", "ieps_6"): "hig_ieps_6",
        ("HIGIENE", "sin_ieps_7"): "hig_sin_ieps_7",
        ("HIGIENE", "ieps_7"): "hig_ieps_7",
        ("ESTETICA", "importe"): "est_importe",
        ("ESTETICA", "iva"): "est_iva",
        ("TRANSPORTE", "importe"): "tra_importe",
        ("TRANSPORTE", "iva"): "tra_iva",
        ("PENSION", "importe"): "pen_importe",
        ("PENSION", "iva"): "pen_iva",
        ("VACUNA", "importe"): "vac_importe",
        ("CLINICA", "importe"): "cli_importe",
    }
    for cat, vals in agrupado.items():
        for campo, valor in vals.items():
            clave = mapa.get((cat, campo))
            if clave:
                datos_completos[clave] = valor
    for campo, expr in detalle.items():
        datos_completos[f"{campo}__expr"] = expr
    pagos = datos.get("pagos", {})
    for k in ("efectivo", "tc", "td", "cheque", "transfer", "vale"):
        datos_completos[k] = pagos.get(k, 0)
    return datos_completos


# ============================================================
# LISTAR
# ============================================================
@router.get("", response_class=HTMLResponse)
def listar(
    request: Request,
    desde: str = "",
    hasta: str = "",
    sucursal: str = "",
    resumen: str = "",
):
    sql = "SELECT * FROM ingresos WHERE 1=1"
    params = []
    if desde:
        sql += " AND fecha >= ?"
        params.append(desde)
    if hasta:
        sql += " AND fecha <= ?"
        params.append(hasta)
    if sucursal:
        sql += " AND sucursal = ?"
        params.append(sucursal)
    sql += " ORDER BY fecha ASC, id ASC"

    conn = get_conn()
    rows = conn.execute(sql, params).fetchall()
    sucursales = _listar_sucursales(conn)
    total = sum(r["total"] for r in rows)
    conn.close()

    cfg = _cargar_config_gmail()

    return templates.TemplateResponse(
        "ingresos.html",
        {
            "request": request,
            "rows": rows,
            "total": total,
            "edit": None,
            "prefill": None,
            "productos": None,
            "avisos": [],
            "no_catalogados": [],
            "remisiones_con_problema": [],
            "filtros": {"desde": desde, "hasta": hasta, "sucursal": sucursal},
            "sucursales": sucursales,
            "resumen": resumen,
            "gmail_configurado": bool(cfg.get("usuario") and cfg.get("password_app")),
            "cfg": cfg,
            "rechazados_count": _contar_rechazados(),
            "anio_actual": datetime.now().year,
            "mes_actual": datetime.now().month,
        },
    )


# ============================================================
# CRUD MANUAL
# ============================================================
@router.post("/nuevo")
def crear(
    fecha: str = Form(...),
    folio: str = Form(""),
    folio_fiscal: str = Form(""),
    cliente: str = Form(""),
    rfc: str = Form(""),
    total: float = Form(0),
    sucursal: str = Form(""),
    notas: str = Form(""),
):
    conn = get_conn()
    conn.execute(
        "INSERT INTO ingresos "
        "(fecha, folio, folio_fiscal, cliente, rfc, total, sucursal, notas, datos_json) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL)",
        (fecha, folio, folio_fiscal, cliente, rfc, total, sucursal, notas),
    )
    conn.commit()
    conn.close()
    return RedirectResponse("/ingresos", status_code=303)


@router.get("/editar/{id}", response_class=HTMLResponse)
def editar_form(request: Request, id: int):
    conn = get_conn()
    row = conn.execute("SELECT * FROM ingresos WHERE id=?", (id,)).fetchone()
    rows = conn.execute(
        "SELECT * FROM ingresos ORDER BY fecha ASC, id ASC"
    ).fetchall()
    sucursales = _listar_sucursales(conn)
    total = sum(r["total"] for r in rows)
    conn.close()
    cfg = _cargar_config_gmail()
    return templates.TemplateResponse(
        "ingresos.html",
        {
            "request": request,
            "rows": rows,
            "total": total,
            "edit": row,
            "prefill": None,
            "productos": None,
            "avisos": [],
            "no_catalogados": [],
            "remisiones_con_problema": [],
            "filtros": {"desde": "", "hasta": "", "sucursal": ""},
            "sucursales": sucursales,
            "resumen": "",
            "gmail_configurado": bool(cfg.get("usuario") and cfg.get("password_app")),
            "cfg": cfg,
            "rechazados_count": _contar_rechazados(),
            "anio_actual": datetime.now().year,
            "mes_actual": datetime.now().month,
        },
    )


@router.post("/editar/{id}")
def editar(
    id: int,
    fecha: str = Form(...),
    folio: str = Form(""),
    folio_fiscal: str = Form(""),
    cliente: str = Form(""),
    rfc: str = Form(""),
    total: float = Form(0),
    sucursal: str = Form(""),
    notas: str = Form(""),
):
    conn = get_conn()
    row = conn.execute("SELECT * FROM ingresos WHERE id=?", (id,)).fetchone()
    sucursal_vieja = row["sucursal"] if row else ""

    conn.execute(
        "UPDATE ingresos SET fecha=?, folio=?, folio_fiscal=?, cliente=?, "
        "rfc=?, total=?, sucursal=?, notas=? WHERE id=?",
        (fecha, folio, folio_fiscal, cliente, rfc, total, sucursal, notas, id),
    )
    conn.commit()
    conn.close()

    # Mover archivos si cambió la sucursal
    if row and sucursal and sucursal != sucursal_vieja:
        try:
            anio, mes = um._mes_de_fecha(fecha)
            nombre_base = str(folio or folio_fiscal or "").strip()
            if nombre_base:
                um.mover_entre_sucursales(
                    anio, mes,
                    sucursal_vieja or um.SIN_SUCURSAL,
                    sucursal,
                    nombre_base,
                )
        except Exception:
            pass

    return RedirectResponse("/ingresos", status_code=303)


@router.post("/borrar/{id}")
def borrar(id: int):
    conn = get_conn()
    conn.execute("DELETE FROM ingresos WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return RedirectResponse("/ingresos", status_code=303)


# ============================================================
# SUBIR XML + PDF MANUAL
# ============================================================
@router.post("/subir", response_class=HTMLResponse)
async def subir(
    request: Request,
    xml: UploadFile = File(...),
    pdf: UploadFile = File(...),
):
    tmpdir = Path(tempfile.mkdtemp(prefix="vetsuite_"))
    ruta_xml = tmpdir / (xml.filename or "factura.xml")
    ruta_pdf = tmpdir / (pdf.filename or "factura.pdf")

    try:
        with open(ruta_xml, "wb") as f:
            shutil.copyfileobj(xml.file, f)
        with open(ruta_pdf, "wb") as f:
            shutil.copyfileobj(pdf.file, f)

        datos = procesar_factura(str(ruta_xml), str(ruta_pdf))
        agrupado, detalle, avisos, no_catalogados = agrupar_por_categoria(datos)

        fecha_iso = ""
        if datos.get("fecha"):
            try:
                fecha_iso = datetime.strptime(
                    datos["fecha"], "%d/%m/%Y"
                ).strftime("%Y-%m-%d")
            except ValueError:
                fecha_iso = ""

        productos = []
        for rem, prods in datos.get("productos_por_remision", {}).items():
            for p in prods:
                productos.append({
                    "remision": rem,
                    "nombre": p.get("nombre", ""),
                    "cantidad": p.get("cantidad", 0),
                    "importe": p.get("importe_pdf", 0),
                    "tipo": p.get("tipo_impuesto", ""),
                    "tasa": p.get("tasa_num", 0),
                })

        datos_completos = _construir_datos_json(datos, agrupado, detalle)

        prefill = {
            "fecha": fecha_iso,
            "folio": datos.get("no_factura", ""),
            "folio_fiscal": datos.get("folio_fiscal", ""),
            "cliente": datos.get("nombre", ""),
            "rfc": datos.get("rfc", ""),
            "total": datos.get("total", 0),
            "sucursal": "",
            "notas": datos.get("qvet", ""),
            "datos_json": json.dumps(datos_completos, ensure_ascii=False, default=str),
            "xml_tmp": str(ruta_xml),
            "pdf_tmp": str(ruta_pdf),
        }

        conn = get_conn()
        rows = conn.execute(
            "SELECT * FROM ingresos ORDER BY fecha ASC, id ASC"
        ).fetchall()
        total_tabla = sum(r["total"] for r in rows)
        sucursales = _listar_sucursales(conn)
        conn.close()
        cfg = _cargar_config_gmail()

        return templates.TemplateResponse(
            "ingresos.html",
            {
                "request": request,
                "rows": rows,
                "total": total_tabla,
                "edit": None,
                "prefill": prefill,
                "productos": productos,
                "avisos": avisos,
                "no_catalogados": no_catalogados,
                "remisiones_con_problema": datos.get("remisiones_con_problema", []),
                "filtros": {"desde": "", "hasta": "", "sucursal": ""},
                "sucursales": sucursales,
                "resumen": "",
                "gmail_configurado": bool(cfg.get("usuario") and cfg.get("password_app")),
                "cfg": cfg,
                "rechazados_count": _contar_rechazados(),
                "anio_actual": datetime.now().year,
                "mes_actual": datetime.now().month,
            },
        )
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


@router.post("/guardar-con-datos")
def guardar_con_datos(
    fecha: str = Form(...),
    folio: str = Form(""),
    folio_fiscal: str = Form(""),
    cliente: str = Form(""),
    rfc: str = Form(""),
    total: float = Form(0),
    sucursal: str = Form(""),
    notas: str = Form(""),
    datos_json: str = Form(""),
):
    conn = get_conn()
    conn.execute(
        "INSERT INTO ingresos "
        "(fecha, folio, folio_fiscal, cliente, rfc, total, sucursal, notas, datos_json) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (fecha, folio, folio_fiscal, cliente, rfc, total, sucursal, notas, datos_json),
    )
    conn.commit()
    conn.close()
    return RedirectResponse("/ingresos", status_code=303)


# ============================================================
# DESCARGA DE GMAIL
# ============================================================
def _procesar_descarga(job_id, modo, valor_n, desde, hasta):
    try:
        jobs.actualizar_job(job_id, estado="corriendo", progreso=1)
        jobs.agregar_mensaje(job_id, "Cargando configuracion...")

        cfg = _cargar_config_gmail()
        if not (cfg.get("usuario") and cfg.get("password_app") and cfg.get("etiqueta")):
            jobs.actualizar_job(job_id, estado="error",
                                 terminado=datetime.now().isoformat())
            jobs.agregar_mensaje(job_id, "Configuracion de Gmail incompleta")
            return

        solo_no_leidos = (modo == "no_leidos")
        fecha_desde = None
        fecha_hasta = None
        if modo == "rango":
            fecha_desde = desde or None
            fecha_hasta = hasta or None
        elif modo == "ultimos":
            try:
                n = int(valor_n or 10)
            except ValueError:
                n = 10
            fecha_desde = (datetime.now() - timedelta(days=n)).strftime("%Y-%m-%d")

        def on_log(msg):
            if jobs.obtener_job(job_id) is None:
                return
            jobs.agregar_mensaje(job_id, msg)

        def on_progreso(texto):
            job_actual = jobs.obtener_job(job_id)
            if job_actual is None:
                return
            progreso_actual = job_actual.get("progreso", 0)
            jobs.actualizar_job(
                job_id,
                progreso=max(2, progreso_actual)
            )
            jobs.agregar_mensaje(job_id, texto)
        jobs.actualizar_job(job_id, progreso=5)

        # Descargar a temporales
        carpeta_tmp = um.TEMPORALES / job_id
        carpeta_tmp.mkdir(parents=True, exist_ok=True)

        descargados, errores, info = descargar_adjuntos_gmail(
            usuario=cfg["usuario"],
            password_app=cfg["password_app"],
            etiqueta=cfg["etiqueta"],
            filtro_remitente=cfg.get("filtro_remitente") or None,
            solo_no_leidos=solo_no_leidos,
            fecha_desde=fecha_desde,
            fecha_hasta=fecha_hasta,
            usar_cache=True,
            carpeta_destino=carpeta_tmp,
            callback_log=on_log,
            callback_progreso=on_progreso,
        )

        jobs.actualizar_job(job_id, progreso=40)
        jobs.agregar_mensaje(
            job_id,
            f"Descarga completa: {len(descargados)} archivos, {len(errores)} errores"
        )

        archivos_por_correo = info.get("archivos_por_correo", {})
        grupos = agrupar_facturas_descargadas(carpeta_tmp, archivos_por_correo)
        jobs.actualizar_job(job_id, progreso=50)
        jobs.agregar_mensaje(job_id, f"Facturas agrupadas: {len(grupos)}")

        conn = get_conn()
        importadas = 0
        duplicadas = 0
        sin_pdf = 0
        parse_errors = []
        todos_avisos = []
        todos_no_catalogados = []
        vistos_avisos = set()
        vistos_no_cat = set()

        qvet_por_archivo = info.get("qvet_por_archivo", {})

        for i, (clave, g) in enumerate(grupos.items(), 1):
            pct = 50 + int((i / max(len(grupos), 1)) * 45)
            jobs.actualizar_job(job_id, progreso=pct)

            xml_path = g.get("xml")
            pdf_path = g.get("pdf")
            no_factura = g.get("no_factura", "")

            if not xml_path:
                sin_pdf += 1
                continue

            # Leer fecha y serie del XML para determinar destino
            try:
                from lector_facturas import leer_xml_factura
                datos_cab = leer_xml_factura(str(xml_path))
            except Exception:
                datos_cab = {}

            fecha_iso = ""
            if datos_cab.get("fecha"):
                try:
                    fecha_iso = datetime.strptime(
                        datos_cab["fecha"], "%d/%m/%Y"
                    ).strftime("%Y-%m-%d")
                except ValueError:
                    fecha_iso = ""

            anio, mes = um._mes_de_fecha(fecha_iso)

            # Determinar sucursal por el asunto del correo (QVET)
            nombre_xml = Path(xml_path).name
            qvet_asunto = qvet_por_archivo.get(nombre_xml, "")
            serie = ""
            if qvet_asunto and "/" in qvet_asunto:
                serie = qvet_asunto.split("/")[0]
            elif datos_cab.get("serie"):
                serie = datos_cab["serie"]
            sucursal = um.serie_a_sucursal(serie)

            if not pdf_path:
                sin_pdf += 1
                um.mover_a_sin_pdf(xml_path, anio, mes)
                jobs.agregar_mensaje(
                    job_id,
                    f"Sin PDF: {xml_path.name} -> sin_pdf/{anio}/{mes}/"
                )
                continue

            uuid = g.get("uuid", "")
            if uuid:
                existe = conn.execute(
                    "SELECT id, datos_json FROM ingresos WHERE folio_fiscal = ?",
                    (uuid,),
                ).fetchone()
                if existe:
                    tiene_datos = existe["datos_json"] and existe["datos_json"].strip()
                    if tiene_datos:
                        # Duplicado real: ya está procesado con datos_json
                        duplicadas += 1
                        um.mover_a_duplicado(xml_path, pdf_path, anio, mes)
                        continue
                    else:
                        # Duplicado, pero el registro no tiene datos_json.
                        # Mover a facturas/ para que "Revisar histórico" lo procese.
                        if pdf_path:
                            um.mover_y_renombrar(xml_path, pdf_path, anio, mes, sucursal,
                                                datos_cab.get("folio") or datos_cab.get("no_factura", ""))
                        else:
                            um.mover_a_sin_pdf(xml_path, anio, mes)
                        # Nota: NO insertamos, solo movemos
                        jobs.agregar_mensaje(
                            job_id,
                            f"Duplicado sin datos_json: {xml_path.name} movido a facturas/"
                        )
                        continue

            try:
                datos = procesar_factura(str(xml_path), str(pdf_path))
                agrupado, detalle, avisos, no_catalogados = agrupar_por_categoria(datos)

                for a in avisos:
                    k = (a["categoria_actual"], a["producto"].strip().upper())
                    if k not in vistos_avisos:
                        vistos_avisos.add(k)
                        todos_avisos.append(a)
                for n in no_catalogados:
                    k = ("U", n["producto"].strip().upper())
                    if k not in vistos_no_cat:
                        vistos_no_cat.add(k)
                        todos_no_catalogados.append(n)

                datos_completos = _construir_datos_json(datos, agrupado, detalle)

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

                # Mover a destino final renombrando a <folio>.xml / <folio>.pdf
                um.mover_y_renombrar(
                    xml_path, pdf_path, anio, mes, sucursal,
                    datos.get("no_factura", ""),
                )

                importadas += 1
            except Exception as e:
                parse_errors.append(f"{xml_path.name}: {e}")
                um.mover_a_rechazado(xml_path, pdf_path, anio, mes, str(e))
                jobs.agregar_mensaje(
                    job_id,
                    f"Error parseando {xml_path.name}: {e}"
                )

        conn.commit()
        conn.close()

        # Limpiar temporales del job
        try:
            shutil.rmtree(carpeta_tmp, ignore_errors=True)
        except Exception:
            pass

        resumen = (
            f"Importadas: {importadas} | Duplicadas: {duplicadas} | "
            f"Sin PDF: {sin_pdf} | Errores: {len(errores) + len(parse_errors)}"
        )
        if todos_avisos or todos_no_catalogados:
            resumen += (
                f" | No catalogados: {len(todos_no_catalogados)}"
                f" | A reclasificar: {len(todos_avisos)}"
            )

        jobs.actualizar_job(
            job_id,
            estado="ok",
            progreso=100,
            resultado={
                "importadas": importadas,
                "duplicadas": duplicadas,
                "sin_pdf": sin_pdf,
                "errores_descarga": len(errores),
                "errores_parseo": len(parse_errors),
                "avisos": todos_avisos,
                "no_catalogados": todos_no_catalogados,
                "resumen": resumen,
            },
            terminado=datetime.now().isoformat(),
        )
        jobs.agregar_mensaje(job_id, resumen)

    except Exception as e:
        jobs.actualizar_job(job_id, estado="error",
                             terminado=datetime.now().isoformat())
        jobs.agregar_mensaje(job_id, f"Error fatal: {e}")


@router.post("/descargar-gmail")
def descargar_gmail(
    background_tasks: BackgroundTasks,
    modo: str = Form("no_leidos"),
    valor_n: str = Form("10"),
    desde: str = Form(""),
    hasta: str = Form(""),
):
    jobs.limpiar_jobs_viejos()
    job_id = jobs.crear_job()
    background_tasks.add_task(
        _procesar_descarga, job_id, modo, valor_n, desde, hasta
    )
    return JSONResponse({"job_id": job_id})


@router.get("/estado-descarga/{job_id}")
def estado_descarga(job_id: str):
    job = jobs.obtener_job(job_id)
    if not job:
        return JSONResponse({"error": "job no encontrado"}, status_code=404)
    return JSONResponse(job)


# ============================================================
# REVISAR HISTÓRICO
# ============================================================
@router.post("/revisar-todo")
def revisar_todo():
    conn = get_conn()
    pendientes = conn.execute(
        "SELECT id, fecha, folio, folio_fiscal, sucursal FROM ingresos "
        "WHERE datos_json IS NULL OR datos_json = ''"
    ).fetchall()

    actualizados = 0
    sin_archivos = 0
    errores = []

    for p in pendientes:
        anio, mes = um._mes_de_fecha(p["fecha"])
        sucursal = p["sucursal"] or um.SIN_SUCURSAL
        nombre_base = str(p["folio"] or "").strip()

        xml_path, pdf_path = um.buscar_archivos_factura(
            anio, mes, sucursal, nombre_base
        )

        # Fallback: buscar por UUID
        if not xml_path and not pdf_path and p["folio_fiscal"]:
            xml_path, pdf_path = um.buscar_archivos_factura(
                anio, mes, sucursal, p["folio_fiscal"]
            )

        if not (xml_path and pdf_path):
            sin_archivos += 1
            continue

        try:
            datos = procesar_factura(str(xml_path), str(pdf_path))
            agrupado, detalle, avisos, no_catalogados = agrupar_por_categoria(datos)
            datos_completos = _construir_datos_json(datos, agrupado, detalle)
            conn.execute(
                "UPDATE ingresos SET datos_json=? WHERE id=?",
                (json.dumps(datos_completos, ensure_ascii=False, default=str), p["id"]),
            )
            actualizados += 1
        except Exception as e:
            errores.append(f"ID {p['id']}: {e}")

    conn.commit()
    conn.close()

    resumen = (
        f"Revisados: {actualizados} | "
        f"Sin archivos: {sin_archivos} | "
        f"Errores: {len(errores)}"
    )
    return RedirectResponse(f"/ingresos?resumen={resumen}", status_code=303)


@router.get("/arbol")
def arbol_ingresos():
    """
    Devuelve la jerarquía de registros para el modal de reportes.
    Estructura: {anio: {mes: {sucursal: {n, total}}}}
    """
    conn = get_conn()
    rows = conn.execute(
        "SELECT fecha, sucursal, total FROM ingresos ORDER BY fecha"
    ).fetchall()
    conn.close()

    # Agrupar
    arbol = {}
    for r in rows:
        fecha = r["fecha"] or ""
        if len(fecha) < 7:
            continue
        anio = fecha[:4]
        mes = fecha[5:7]
        sucursal = r["sucursal"] or "_sin_sucursal"
        total = r["total"] or 0

        arbol.setdefault(anio, {}).setdefault(mes, {}).setdefault(
            sucursal, {"n": 0, "total": 0.0}
        )
        arbol[anio][mes][sucursal]["n"] += 1
        arbol[anio][mes][sucursal]["total"] += total

    # Totales por mes y por año (los calcula el cliente, pero los mandamos
    # para simplificar el render)
    for anio, meses in arbol.items():
        for mes, sucs in meses.items():
            meses[mes]["_total"] = {
                "n": sum(s["n"] for s in sucs.values()),
                "total": round(sum(s["total"] for s in sucs.values()), 2),
            }
        arbol[anio]["_total"] = {
            "n": sum(m["_total"]["n"] for m in meses.values()),
            "total": round(sum(m["_total"]["total"] for m in meses.values()), 2),
        }

    # Total global (a nivel raíz)
    arbol["_total"] = {
        "n": sum(v["_total"]["n"] for k, v in arbol.items() if k != "_total"),
        "total": round(sum(
            v["_total"]["total"] for k, v in arbol.items() if k != "_total"
        ), 2),
    }

    return JSONResponse(
        arbol,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


# ============================================================
# RECLASIFICAR
# ============================================================
@router.get("/reclasificar", response_class=HTMLResponse)
def reclasificar_form(request: Request, mensaje: str = ""):
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, datos_json FROM ingresos WHERE datos_json IS NOT NULL"
    ).fetchall()
    conn.close()

    # Unión de AMBAS fuentes, con la MISMA normalización que usa el parser
    exc_manuales = cargar_excepciones_manuales()      # claves ya normalizadas
    catalogo_qvet = cargar_catalogo()                  # claves ya normalizadas
    ya_catalogados = set(exc_manuales.keys()) | set(catalogo_qvet.keys())

    no_catalogados = {}
    for r in rows:
        try:
            dj = json.loads(r["datos_json"])
        except Exception:
            continue
        for rem, prods in dj.get("productos_por_remision", {}).items():
            for p in prods:
                nombre = (p.get("nombre") or "").strip()
                if not nombre:
                    continue
                clave = normalizar(nombre)             # ← misma función que el parser
                if not clave:
                    continue
                if clave in ya_catalogados:
                    continue
                if clave not in no_catalogados:
                    no_catalogados[clave] = {
                        "producto": nombre,
                        "producto_norm": clave,
                        "categoria_actual": "U",
                        "motivo": "no_catalogado",
                    }

    # Catálogo actual para mostrarlo (solo excepciones manuales, que son las editables)
    catalogo_lista = [
        {"producto": k, "categoria": v}
        for k, v in sorted(exc_manuales.items())
    ]

    return templates.TemplateResponse(
        "reclasificar.html",
        {
            "request": request,
            "pendientes": list(no_catalogados.values()),
            "catalogo": catalogo_lista,
            "categorias": CATEGORIAS,
            "mensaje": mensaje,
        },
    )


@router.post("/reclasificar/guardar-async")
async def reclasificar_guardar_async(request: Request):
    form = await request.form()
    productos = {}
    categorias = {}
    for key, value in form.items():
        if key.startswith("producto_"):
            productos[key.split("_", 1)[1]] = value
        elif key.startswith("categoria_"):
            categorias[key.split("_", 1)[1]] = value

    guardados = 0
    for idx, prod in productos.items():
        cat = categorias.get(idx, "U")
        # Guardar con la MISMA normalización que usa el parser
        clave = normalizar(prod)
        if not clave:
            continue
        ok, _ = agregar_producto_catalogo(clave, cat)
        if ok:
            guardados += 1

    recargar_catalogo()
    return RedirectResponse(
        f"/ingresos/reclasificar?mensaje={guardados} productos guardados",
        status_code=303,
    )


# ============================================================
# EXCEL
# ============================================================
@router.get("/excel")
def excel(
    desde: str = "",
    hasta: str = "",
    sucursal: str = "",
):
    sql = "SELECT * FROM ingresos WHERE datos_json IS NOT NULL AND datos_json <> ''"
    params = []
    if desde:
        sql += " AND fecha >= ?"
        params.append(desde)
    if hasta:
        sql += " AND fecha <= ?"
        params.append(hasta)
    if sucursal:
        sql += " AND sucursal = ?"
        params.append(sucursal)
    sql += " ORDER BY fecha ASC, id ASC"

    conn = get_conn()
    rows = conn.execute(sql, params).fetchall()
    conn.close()

    registros = []
    for r in rows:
        try:
            registros.append(json.loads(r["datos_json"]))
        except Exception:
            continue

    if not registros:
        return RedirectResponse(
            "/ingresos?resumen=No hay facturas procesadas para el rango",
            status_code=303,
        )

    titulo = f"{desde} a {hasta}" if desde and hasta else "Ingresos"
    path = generar_excel(registros, titulo_hoja=titulo)
    return FileResponse(
        path,
        filename=f"ingresos_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


# ============================================================
# ZIP
# ============================================================
@router.get("/zip")
def zip_mensual(
    anio: int,
    mes: int,
    sucursal: str,
):
    if sucursal not in um.SUCURSALES_VALIDAS:
        return RedirectResponse(
            f"/ingresos?resumen=Sucursal invalida: {sucursal}",
            status_code=303,
        )
    if not (1 <= mes <= 12):
        return RedirectResponse(
            "/ingresos?resumen=Mes invalido", status_code=303
        )

    # Traer registros del mes/sucursal
    mes_str = f"{anio}-{mes:02d}"
    sql = (
        "SELECT * FROM ingresos "
        "WHERE fecha LIKE ? AND sucursal = ? "
        "AND datos_json IS NOT NULL AND datos_json <> '' "
        "ORDER BY fecha ASC, id ASC"
    )
    conn = get_conn()
    rows = conn.execute(sql, (f"{mes_str}%", sucursal)).fetchall()
    conn.close()

    if not rows:
        return RedirectResponse(
            f"/ingresos?resumen=No hay facturas para {sucursal} {mes_str}",
            status_code=303,
        )

    registros = []
    for r in rows:
        try:
            registros.append(json.loads(r["datos_json"]))
        except Exception:
            continue

    path = generar_zip_mensual(anio, mes, sucursal, registros)
    nombre = f"contabilidad_{anio}_{um.MESES_ES[mes-1]}_{sucursal.lower()}.zip"
    return FileResponse(path, filename=nombre, media_type="application/zip")

# ============================================================
# RESET
# ============================================================
@router.post("/reset")
def reset_ingresos_completo():
    """
    Reset total del módulo Ingresos:
    - Borra todos los archivos (facturas, rechazados, sin_pdf, duplicados,
      logs, temporales)
    - Borra el caché de correos procesados
    - Borra todos los registros de la tabla ingresos
    NO toca: catálogo QVET, categorías manuales, gmail_config.json,
             tablas egresos y recordatorios.
    """
    from shared.db import borrar_todos_ingresos

    stats_files = um.reset_ingresos()
    eliminados_bd = borrar_todos_ingresos()

    resumen = (
        f"Reset completado: {eliminados_bd} registros y "
        f"{stats_files['archivos_borrados']} archivos eliminados"
    )
    if stats_files["cache_borrado"]:
        resumen += " (caché de correos incluido)"

    return RedirectResponse(
        f"/ingresos?resumen={resumen}", status_code=303
    )

# ============================================================
# CATÁLOGO (consulta + edición + agregar)
# ============================================================
@router.get("/catalogo", response_class=HTMLResponse)
def ver_catalogo(
    request: Request,
    q: str = "",
    categoria: str = "",
):
    base = cargar_catalogo()
    manuales = cargar_excepciones_manuales()

    # Combinar: manuales pisan a base
    items = {}
    for k, v in base.items():
        items[k] = {"producto_norm": k, "categoria": v, "origen": "base"}
    for k, v in manuales.items():
        items[k] = {"producto_norm": k, "categoria": v, "origen": "manual"}

    # Mandamos TODOS los items; el filtrado real es client-side.
    lista = list(items.values())
    lista.sort(key=lambda x: x["producto_norm"])

    conteo = {c: 0 for c in CATEGORIAS}
    for v in items.values():
        conteo[v["categoria"]] = conteo.get(v["categoria"], 0) + 1

    return templates.TemplateResponse(
        "catalogo.html",
        {
            "request": request,
            "items": lista,
            "total": len(items),
            "total_base": len(base),
            "total_manual": len(manuales),
            "filtrados": len(lista),         # el cliente lo recalcula
            "categorias": CATEGORIAS,
            "conteo": conteo,
            "q": q,                          # el cliente pre-llena el input
            "categoria_activa": categoria,   # el cliente pre-marca el chip
        },
    )


@router.post("/catalogo/actualizar")
def actualizar_categoria(
    producto: str = Form(...),
    categoria: str = Form(...),
):
    """Guarda/actualiza la categoría en categorias_manuales.json."""
    if categoria not in CATEGORIAS:
        return JSONResponse({"ok": False, "error": "categoría inválida"}, status_code=400)
    ok, msg = agregar_producto_catalogo(producto, categoria)
    if ok:
        recargar_catalogo()
    return JSONResponse({"ok": ok, "msg": msg})


@router.post("/catalogo/agregar")
def agregar_catalogo(
    producto: str = Form(...),
    categoria: str = Form(...),
):
    """Agrega un producto nuevo (queda en categorias_manuales.json)."""
    if not producto.strip():
        return JSONResponse({"ok": False, "error": "producto vacío"}, status_code=400)
    if categoria not in CATEGORIAS:
        return JSONResponse({"ok": False, "error": "categoría inválida"}, status_code=400)
    ok, msg = agregar_producto_catalogo(producto, categoria)
    if ok:
        recargar_catalogo()
    return JSONResponse({"ok": ok, "msg": msg})


@router.post("/catalogo/eliminar")
def eliminar_override(producto: str = Form(...)):
    """Quita la corrección manual. El producto vuelve a su categoría base (o U)."""
    ok = borrar_producto_catalogo(producto)
    if ok:
        recargar_catalogo()
        return JSONResponse({"ok": True})
    return JSONResponse({"ok": False, "error": "no existe el override"}, status_code=404)


@router.post("/reclasificar-sucursales")
def reclasificar_sucursales():
    conn = get_conn()
    pendientes = conn.execute(
        "SELECT id, fecha, folio, folio_fiscal, sucursal FROM ingresos "
        "WHERE sucursal IS NULL OR sucursal = '' OR sucursal = '_sin_sucursal'"
    ).fetchall()

    actualizadas = 0
    errores = []

    for p in pendientes:
        try:
            anio, mes = um._mes_de_fecha(p["fecha"])
            nombre_base = str(p["folio"] or p["folio_fiscal"] or "").strip()
            xml_path, _ = um.buscar_archivos_factura(anio, mes, "", nombre_base)
            if not xml_path and p["folio_fiscal"]:
                xml_path, _ = um.buscar_archivos_factura(anio, mes, "", p["folio_fiscal"])
            if not xml_path:
                errores.append(f"ID {p['id']}: sin XML")
                continue

            from lector_facturas import leer_xml_factura
            datos = leer_xml_factura(str(xml_path))
            serie = datos.get("serie", "")
            sucursal = um.serie_a_sucursal(serie)
            if sucursal and sucursal != um.SIN_SUCURSAL:
                conn.execute(
                    "UPDATE ingresos SET sucursal=? WHERE id=?",
                    (sucursal, p["id"])
                )
                actualizadas += 1
        except Exception as e:
            errores.append(f"ID {p['id']}: {e}")

    conn.commit()
    conn.close()

    resumen = f"Reclasificadas: {actualizadas} | Errores: {len(errores)}"
    return RedirectResponse(f"/ingresos?resumen={resumen}", status_code=303)


# ============================================================
# VER ARCHIVOS (PDF / XML)
# ============================================================
def _buscar_archivo(row, extension):
    """
    Devuelve el Path del archivo (xml o pdf) de una factura,
    o None si no lo encuentra.
    """
    anio, mes = um._mes_de_fecha(row["fecha"])
    sucursal = row["sucursal"] or um.SIN_SUCURSAL
    nombre_base = str(row["folio"] or row["folio_fiscal"] or "").strip()

    xml_path, pdf_path = um.buscar_archivos_factura(
        anio, mes, sucursal, nombre_base
    )
    # Fallback por UUID
    if not (xml_path or pdf_path) and row["folio_fiscal"]:
        xml_path, pdf_path = um.buscar_archivos_factura(
            anio, mes, sucursal, row["folio_fiscal"]
        )
    # Fallback: buscar en cualquier sucursal (por si quedó mal clasificada)
    if not (xml_path or pdf_path):
        for suc in um.SUCURSALES_VALIDAS | {um.SIN_SUCURSAL}:
            xml_path, pdf_path = um.buscar_archivos_factura(
                anio, mes, suc, nombre_base
            )
            if xml_path or pdf_path:
                break

    return xml_path if extension == ".xml" else pdf_path


@router.get("/ver-pdf/{id}")
def ver_pdf(id: int):
    conn = get_conn()
    row = conn.execute("SELECT * FROM ingresos WHERE id=?", (id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "Factura no encontrada")

    pdf_path = _buscar_archivo(row, ".pdf")
    if not pdf_path or not Path(pdf_path).exists():
        raise HTTPException(404, "PDF no encontrado en disco")

    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{Path(pdf_path).name}"',
            "Cache-Control": "no-store",
        },
    )


@router.get("/ver-xml/{id}")
def ver_xml(id: int):
    conn = get_conn()
    row = conn.execute("SELECT * FROM ingresos WHERE id=?", (id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "Factura no encontrada")

    xml_path = _buscar_archivo(row, ".xml")
    if not xml_path or not Path(xml_path).exists():
        raise HTTPException(404, "XML no encontrado en disco")

    return FileResponse(
        xml_path,
        media_type="application/xml",
        headers={
            "Content-Disposition": f'inline; filename="{Path(xml_path).name}"',
            "Cache-Control": "no-store",
        },
    )