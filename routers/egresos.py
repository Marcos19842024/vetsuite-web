import json
import shutil
import tempfile
import threading
import time
import zipfile
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, FileResponse

from templates_shared import templates

from db import get_conn
import jobs
import egresos.manager as em
from egresos import sat_wrapper as sat
from egresos.excel_egresos import generar_excel_pue, generar_excel_ppd

router = APIRouter(prefix="/egresos", tags=["egresos"])

BASE_DIR = Path(__file__).parent.parent
MESES_ES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]

em.inicializar()

_jobs_sat_activos = {}
_jobs_lock = threading.Lock()
TIMEOUT_SAT_SEGUNDOS = 3600


def _listar_sucursales(conn):
    return [r["sucursal"] for r in conn.execute(
        "SELECT DISTINCT sucursal FROM egresos WHERE sucursal <> '' ORDER BY sucursal"
    ).fetchall()]


# ============================================================
# LISTAR
# ============================================================
@router.get("", response_class=HTMLResponse)
def listar(
    request: Request,
    desde: str = "",
    hasta: str = "",
    sucursal: str = "",
    metodo: str = "",
    forma: str = "",
    resumen: str = "",
):
    sql = "SELECT * FROM egresos WHERE 1=1"
    params = []
    if desde:
        sql += " AND fecha >= ?"; params.append(desde)
    if hasta:
        sql += " AND fecha <= ?"; params.append(hasta)
    if sucursal:
        sql += " AND sucursal = ?"; params.append(sucursal)
    if metodo:
        sql += " AND metodo_pago = ?"; params.append(metodo)
    if forma:
        sql += " AND forma_pago = ?"; params.append(forma)
    sql += " ORDER BY fecha ASC, id ASC"

    conn = get_conn()
    rows = conn.execute(sql, params).fetchall()
    sucursales = _listar_sucursales(conn)

    total = sum(r["total"] for r in rows)
    pue = [r for r in rows if (r["metodo_pago"] or "") != "PPD"]
    ppd = [r for r in rows if (r["metodo_pago"] or "") == "PPD"]
    total_pue = sum(r["total"] for r in pue)
    total_ppd = sum(r["total"] for r in ppd)
    conn.close()

    cfg = sat.cargar_config()
    configurado = bool(
        cfg.get("rfc_receptor") and cfg.get("certificado_cer")
        and cfg.get("certificado_key") and cfg.get("password_fiel")
    )

    job_activo = None
    with _jobs_lock:
        for jid, ev in _jobs_sat_activos.items():
            j = jobs.obtener_job(jid)
            if j and j.get("estado") not in ("ok", "error", "cancelado"):
                job_activo = j
                break

    solicitud_pendiente = sat.cargar_solicitud_activa()

    return templates.TemplateResponse(
        "egresos.html",
        {
            "request": request, "rows": rows, "total": total,
            "total_pue": total_pue, "total_ppd": total_ppd,
            "n_pue": len(pue), "n_ppd": len(ppd),
            "sucursales": sucursales,
            "filtros": {"desde": desde, "hasta": hasta, "sucursal": sucursal, "metodo": metodo, "forma": forma},
            "resumen": resumen, "configurado": configurado, "cfg": cfg,
            "job_activo": job_activo, "solicitud_pendiente": solicitud_pendiente,
            "anio_actual": datetime.now().year, "mes_actual": datetime.now().month,
        },
    )


# ============================================================
# CONFIGURACIÓN E.FIRMA (SUBIDA DE ARCHIVOS)
# ============================================================
@router.post("/config")
def config_guardar(
    rfc_receptor: str = Form(""),
    password_fiel: str = Form(""),
    certificado_cer: UploadFile = File(None),
    certificado_key: UploadFile = File(None),
):
    cfg = sat.cargar_config()
    cfg["rfc_receptor"] = rfc_receptor.strip().upper()
    cfg["password_fiel"] = password_fiel.strip()

    carpeta_efirma = BASE_DIR / "uploads" / "efirma"
    carpeta_efirma.mkdir(parents=True, exist_ok=True)

    if certificado_cer and certificado_cer.filename:
        ruta_cer = carpeta_efirma / "certificado.cer"
        with open(ruta_cer, "wb") as f:
            shutil.copyfileobj(certificado_cer.file, f)
        cfg["certificado_cer"] = str(ruta_cer)

    if certificado_key and certificado_key.filename:
        ruta_key = carpeta_efirma / "llave.key"
        with open(ruta_key, "wb") as f:
            shutil.copyfileobj(certificado_key.file, f)
        cfg["certificado_key"] = str(ruta_key)

    sat.guardar_config(cfg)
    return JSONResponse({"status": "ok"})


@router.post("/probar-fiel")
def probar_fiel_endpoint(
    rfc_receptor: str = Form(""),
    password_fiel: str = Form(""),
    certificado_cer: UploadFile = File(None),
    certificado_key: UploadFile = File(None),
):
    cfg = sat.cargar_config()
    cer_path = cfg.get("certificado_cer", "") or ""
    key_path = cfg.get("certificado_key", "") or ""

    if certificado_cer is not None and certificado_cer.filename:
        tmp_cer = BASE_DIR / "uploads" / "efirma" / "temp_test.cer"
        tmp_cer.parent.mkdir(parents=True, exist_ok=True)
        with open(tmp_cer, "wb") as f:
            shutil.copyfileobj(certificado_cer.file, f)
        cer_path = str(tmp_cer)

    if certificado_key is not None and certificado_key.filename:
        tmp_key = BASE_DIR / "uploads" / "efirma" / "temp_test.key"
        with open(tmp_key, "wb") as f:
            shutil.copyfileobj(certificado_key.file, f)
        key_path = str(tmp_key)

    try:
        if not rfc_receptor.strip():
            return JSONResponse({"ok": False, "mensaje": "Falta el RFC"})
        if not cer_path or not Path(cer_path).exists():
            return JSONResponse({"ok": False, "mensaje": "Falta el archivo .cer"})
        if not key_path or not Path(key_path).exists():
            return JSONResponse({"ok": False, "mensaje": "Falta el archivo .key"})
        if not password_fiel.strip():
            return JSONResponse({"ok": False, "mensaje": "Falta la contraseña"})

        resultado = sat.probar_fiel(
            rfc_receptor.strip().upper(),
            cer_path,
            key_path,
            password_fiel.strip(),
        )
        return JSONResponse(resultado)
    except Exception as e:
        return JSONResponse({
            "ok": False,
            "mensaje": f"Error: {type(e).__name__}: {e}",
        })
    finally:
        if certificado_cer is not None and certificado_cer.filename:
            Path(cer_path).unlink(missing_ok=True)
        if certificado_key is not None and certificado_key.filename:
            Path(key_path).unlink(missing_ok=True)


# ============================================================
# JOB DEL SAT
# ============================================================
def _job_solicitar_sat(job_id, fecha_inicio, fecha_fin, cancelar_evt):
    try:
        jobs.actualizar_job(job_id, estado="solicitando", progreso=5)
        jobs.agregar_mensaje(job_id, "Solicitando descarga al SAT...")

        cfg = sat.cargar_config()
        rfc = cfg.get("rfc_receptor", "")
        cer = cfg.get("certificado_cer", "")
        key = cfg.get("certificado_key", "")
        pwd = cfg.get("password_fiel", "")

        if not all([rfc, cer, key, pwd]):
            jobs.actualizar_job(job_id, estado="error",
                                 terminado=datetime.now().isoformat())
            jobs.agregar_mensaje(job_id, "Configuración incompleta")
            return

        try:
            fi = datetime.strptime(fecha_inicio, "%Y-%m-%d")
            ff = datetime.strptime(fecha_fin, "%Y-%m-%d").replace(
                hour=23, minute=59, second=59
            )
        except ValueError:
            jobs.actualizar_job(job_id, estado="error",
                                 terminado=datetime.now().isoformat())
            jobs.agregar_mensaje(job_id, "Fechas inválidas")
            return

        sat.guardar_solicitud_activa({
            "fecha_inicio": fecha_inicio,
            "fecha_fin": fecha_fin,
            "fecha_solicitud": datetime.now().isoformat(timespec="seconds"),
            "estado_solicitud": "solicitando",
        })

        resultado = sat.solicitar_descarga(rfc, cer, key, pwd, fi, ff)
        id_solicitud = resultado.get("id_solicitud", "")

        cod_estatus = str(resultado.get("cod_estatus", ""))
        if cod_estatus == "5005" or "5005" in str(resultado.get("error", "")):
            datos_previos = sat.cargar_solicitud_activa()
            if datos_previos and datos_previos.get("id_solicitud"):
                id_solicitud = datos_previos["id_solicitud"]
                jobs.agregar_mensaje(
                    job_id,
                    f"Solicitud duplicada (5005). Reutilizando ID: {id_solicitud[:8]}..."
                )
            else:
                jobs.actualizar_job(job_id, estado="error",
                                     terminado=datetime.now().isoformat())
                jobs.agregar_mensaje(
                    job_id,
                    "El SAT dice que ya existe una solicitud para este período (5005), "
                    "pero no tenemos el ID guardado. Espera unos minutos o cambia el rango."
                )
                return

        if not id_solicitud:
            error_msg = resultado.get("error") or resultado.get("mensaje", "Sin id_solicitud")
            jobs.actualizar_job(job_id, estado="error",
                                 terminado=datetime.now().isoformat())
            jobs.agregar_mensaje(job_id, f"SAT rechazó: {error_msg}")
            sat.limpiar_solicitud_activa()
            return

        datos = sat.cargar_solicitud_activa() or {}
        datos.update({
            "id_solicitud": id_solicitud,
            "rfc": rfc,
            "estado_solicitud": "1",
        })
        sat.guardar_solicitud_activa(datos)

        jobs.actualizar_job(job_id, estado="verificando", progreso=15,
                             id_solicitud=id_solicitud)
        jobs.agregar_mensaje(job_id, "Solicitud aceptada. Esperando SAT...")

        inicio = time.time()
        paquetes = []

        while True:
            if cancelar_evt.is_set():
                jobs.actualizar_job(job_id, estado="cancelado",
                                     terminado=datetime.now().isoformat())
                return
            if time.time() - inicio > TIMEOUT_SAT_SEGUNDOS:
                jobs.actualizar_job(job_id, estado="error",
                                     terminado=datetime.now().isoformat())
                jobs.agregar_mensaje(job_id, "Timeout (1 hora)")
                return

            time.sleep(30)
            res_v = sat.verificar_solicitud(rfc, cer, key, pwd, id_solicitud)
            estado_sat = str(res_v.get("estado", "?"))
            num_cfdis = str(res_v.get("numero_cfdis", "0"))
            msg = res_v.get("mensaje", "")
            paquetes = res_v.get("paquetes", [])

            datos = sat.cargar_solicitud_activa() or {}
            datos.update({
                "estado_solicitud": estado_sat,
                "numero_cfdis": num_cfdis,
                "paquetes": paquetes,
            })
            sat.guardar_solicitud_activa(datos)

            jobs.actualizar_job(
                job_id,
                progreso=min(15 + int((time.time() - inicio) / 3600 * 50), 65),
                estado_sat=estado_sat,
            )
            jobs.agregar_mensaje(job_id, f"SAT: {estado_sat} - {num_cfdis} CFDIs")

            if estado_sat == "3":
                break
            elif estado_sat in ("4", "5", "6"):
                jobs.actualizar_job(job_id, estado="error",
                                     terminado=datetime.now().isoformat())
                jobs.agregar_mensaje(job_id, f"Error SAT: {msg}")
                sat.limpiar_solicitud_activa()
                return

        jobs.actualizar_job(job_id, estado="descargando", progreso=70)
        jobs.agregar_mensaje(job_id, f"Descargando {len(paquetes)} paquetes...")

        carpeta_tmp = em.TEMPORALES / job_id
        carpeta_tmp.mkdir(parents=True, exist_ok=True)
        sat.descargar_paquetes(rfc, cer, key, pwd, paquetes, carpeta_tmp, id_solicitud)

        jobs.actualizar_job(job_id, estado="procesando", progreso=80)
        jobs.agregar_mensaje(job_id, "Procesando XMLs...")

        facturas = sat.procesar_xmls(carpeta_tmp)
        jobs.agregar_mensaje(job_id, f"Facturas válidas: {len(facturas)}")

        nuevas, duplicadas, errores_mover = 0, 0, 0
        pdfs_generados = 0
        prov = sat.cargar_proveedores_sucursal()

        for f in facturas:
            try:
                uuid_f = (f.get("uuid") or "").strip().upper()
                if not uuid_f:
                    continue

                conn = get_conn()
                if conn.execute(
                    "SELECT 1 FROM egresos WHERE uuid = ?", (uuid_f,)
                ).fetchone():
                    conn.close()
                    duplicadas += 1
                    continue

                rfc_emisor = (f.get("rfc_emisor") or "").strip().upper()
                sucursal = prov.get(rfc_emisor, "Baalak")

                fecha_iso = ""
                if f.get("fecha"):
                    try:
                        fecha_iso = datetime.strptime(
                            f["fecha"], "%d/%m/%Y"
                        ).strftime("%Y-%m-%d")
                    except ValueError:
                        pass

                anio, mes = em._mes_de_fecha(fecha_iso)
                ruta_xml = Path(f.get("ruta_xml", ""))

                if ruta_xml.exists():
                    try:
                        xml_final = em.mover_xml_a_destino(
                            ruta_xml, anio, mes, sucursal,
                            f.get("metodo_pago", "PUE"),
                            f.get("forma_pago_texto", "Efectivo"),
                            f.get("serie", ""),
                            f.get("folio", ""),
                        )
                        # Generar PDF
                        if xml_final and xml_final.exists():
                            pdf_path = em.generar_pdf_desde_xml(
                                xml_final, anio, mes, sucursal,
                                f.get("metodo_pago", "PUE"),
                                f.get("forma_pago_texto", "Efectivo"),
                                f.get("serie", ""),
                                f.get("folio", ""),
                            )
                            if pdf_path:
                                pdfs_generados += 1
                    except Exception as e:
                        errores_mover += 1
                        jobs.agregar_mensaje(job_id, f"Error moviendo/generando PDF: {e}")

                conn.execute(
                    "INSERT INTO egresos "
                    "(fecha, folio, uuid, proveedor, rfc, total, sucursal, "
                    "metodo_pago, forma_pago, notas, serie) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        fecha_iso,
                        f.get("folio", ""),
                        uuid_f,
                        f.get("nombre_emisor", ""),
                        rfc_emisor,
                        f.get("total", 0),
                        sucursal,
                        f.get("metodo_pago", "PUE"),
                        f.get("forma_pago_texto", "Efectivo"),
                        f.get("observacion", ""),
                        f.get("serie", ""),
                    ),
                )
                conn.commit()
                conn.close()
                nuevas += 1
            except Exception as e:
                jobs.agregar_mensaje(job_id, f"Error factura: {e}")

        shutil.rmtree(carpeta_tmp, ignore_errors=True)
        sat.limpiar_solicitud_activa()

        res = (
            f"Importadas: {nuevas} | Duplicadas: {duplicadas} | "
            f"PDFs: {pdfs_generados} | Errores: {errores_mover}"
        )
        jobs.actualizar_job(
            job_id, estado="ok", progreso=100,
            resultado={"resumen": res},
            terminado=datetime.now().isoformat(),
        )
        jobs.agregar_mensaje(job_id, res)

    except Exception as e:
        jobs.actualizar_job(job_id, estado="error",
                             terminado=datetime.now().isoformat())
        jobs.agregar_mensaje(job_id, f"Error fatal: {e}")


@router.post("/solicitar")
def solicitar(fecha_inicio: str = Form(...), fecha_fin: str = Form(...)):
    jobs.limpiar_jobs_viejos()
    job_id = jobs.crear_job()
    evt = threading.Event()
    with _jobs_lock:
        _jobs_sat_activos[job_id] = evt
    threading.Thread(
        target=_job_solicitar_sat,
        args=(job_id, fecha_inicio, fecha_fin, evt),
        daemon=True,
    ).start()
    return JSONResponse({"job_id": job_id})


@router.get("/estado-solicitud/{job_id}")
def estado_solicitud(job_id: str):
    job = jobs.obtener_job(job_id)
    if not job:
        return JSONResponse({"error": "No encontrado"}, status_code=404)
    return JSONResponse(job)


@router.post("/cancelar/{job_id}")
def cancelar_job(job_id: str):
    with _jobs_lock:
        ev = _jobs_sat_activos.get(job_id)
        if ev:
            ev.set()
    return JSONResponse({"status": "cancelado"})


@router.post("/retomar")
def retomar_solicitud():
    datos = sat.cargar_solicitud_activa()
    if not datos:
        return JSONResponse({"error": "No hay solicitud"}, status_code=400)
    fi = datos.get("fecha_inicio", "")
    ff = datos.get("fecha_fin", "")
    if not fi or not ff:
        return JSONResponse({"error": "Inválida"}, status_code=400)

    jobs.limpiar_jobs_viejos()
    job_id = jobs.crear_job()
    evt = threading.Event()
    with _jobs_lock:
        _jobs_sat_activos[job_id] = evt
    threading.Thread(
        target=_job_solicitar_sat,
        args=(job_id, fi, ff, evt),
        daemon=True,
    ).start()
    return JSONResponse({"job_id": job_id})


# ============================================================
# CAMBIAR SUCURSAL
# ============================================================
@router.post("/cambiar-sucursal/{uuid}")
def cambiar_sucursal(uuid: str, sucursal_nueva: str = Form(...)):
    if sucursal_nueva not in ("Baalak", "Animalia"):
        return JSONResponse({"error": "Sucursal inválida"}, status_code=400)

    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM egresos WHERE uuid = ?", (uuid,)
    ).fetchone()
    conn.close()

    if not row:
        return JSONResponse({"error": "Factura no encontrada"}, status_code=404)

    r = dict(row)
    sucursal_actual = r.get("sucursal") or "Baalak"
    if sucursal_actual == sucursal_nueva:
        return JSONResponse({"status": "sin_cambio"})

    fecha_iso = r.get("fecha", "")
    anio, mes = em._mes_de_fecha(fecha_iso)  # mes = "10_octubre"

    metodo = r.get("metodo_pago") or "PUE"
    forma = "PPD" if metodo == "PPD" else (r.get("forma_pago") or "Efectivo")
    serie = (r.get("serie") or "").strip()
    folio = r.get("folio", "")
    nombre_xml = f"{serie}-{folio}.xml" if serie else f"{folio}.xml"

    # ✅ mes ya es "10_octubre", se pasa directo
    xml_actual = em.carpeta_xml(
        anio, mes, sucursal_actual, metodo, forma
    ) / nombre_xml

    if xml_actual.exists():
        ok, msg = em.mover_xml_a_sucursal(
            xml_actual,
            sucursal_actual,
            sucursal_nueva,
            metodo, forma,
            anio, mes,       # ✅ mes directo
            serie, folio,
        )
        if not ok:
            return JSONResponse({"error": f"No se pudo mover el XML: {msg}"}, status_code=500)

    conn = get_conn()
    conn.execute(
        "UPDATE egresos SET sucursal = ? WHERE uuid = ?",
        (sucursal_nueva, uuid),
    )
    conn.commit()
    conn.close()

    rfc = (r.get("rfc") or "").strip().upper()
    if rfc:
        prov = sat.cargar_proveedores_sucursal()
        prov[rfc] = sucursal_nueva
        sat.guardar_proveedores_sucursal(prov)

    return JSONResponse({"status": "ok", "sucursal": sucursal_nueva})


@router.get("/arbol")
def arbol_egresos():
    """
    Estructura: {anio: {mes: {sucursal: {PUE: {n,total}, PPD: {n,total}}}}}
    """
    conn = get_conn()
    rows = conn.execute(
        "SELECT fecha, sucursal, metodo_pago, total FROM egresos ORDER BY fecha"
    ).fetchall()
    conn.close()

    arbol = {}
    for r in rows:
        fecha = r["fecha"] or ""
        if len(fecha) < 7:
            continue
        anio = fecha[:4]
        mes = fecha[5:7]
        sucursal = r["sucursal"] or "_sin_sucursal"
        metodo = (r["metodo_pago"] or "PUE").upper()
        if metodo not in ("PUE", "PPD"):
            metodo = "PUE"
        total = r["total"] or 0

        nodo = arbol.setdefault(anio, {}).setdefault(mes, {}).setdefault(
            sucursal, {"PUE": {"n": 0, "total": 0.0},
                       "PPD": {"n": 0, "total": 0.0}}
        )
        nodo[metodo]["n"] += 1
        nodo[metodo]["total"] += total

    for anio, meses in arbol.items():
        for mes, sucs in meses.items():
            for suc, metodos in sucs.items():
                metodos["_total"] = {
                    "n": metodos["PUE"]["n"] + metodos["PPD"]["n"],
                    "total": round(metodos["PUE"]["total"] + metodos["PPD"]["total"], 2),
                }
                metodos["PUE"]["total"] = round(metodos["PUE"]["total"], 2)
                metodos["PPD"]["total"] = round(metodos["PPD"]["total"], 2)

            meses[mes]["_total"] = {
                "n": sum(s["_total"]["n"] for s in sucs.values()),
                "total": round(sum(s["_total"]["total"] for s in sucs.values()), 2),
            }

        arbol[anio]["_total"] = {
            "n": sum(m["_total"]["n"] for m in meses.values()),
            "total": round(sum(m["_total"]["total"] for m in meses.values()), 2),
        }

    # Total global (a nivel raíz, para el footer del modal)
    arbol["_total"] = {
        "n": sum(
            v["_total"]["n"]
            for k, v in arbol.items()
            if k != "_total"
        ),
        "total": round(sum(
            v["_total"]["total"]
            for k, v in arbol.items()
            if k != "_total"
        ), 2),
    }

    # ⬇️ AQUÍ ESTÁ LA CLAVE: headers anti-cache
    return JSONResponse(
        arbol,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


# ============================================================
# ZIP
# ============================================================
@router.get("/zip")
def zip_mensual(anio: int, mes: int, sucursal: str):
    if not (1 <= mes <= 12):
        return RedirectResponse("/egresos?resumen=Mes inválido", status_code=303)

    mes_nombre_es = MESES_ES[mes - 1]
    mes_str = f"{anio}-{mes:02d}"

    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM egresos WHERE fecha LIKE ? AND sucursal = ? "
        "ORDER BY fecha ASC",
        (f"{mes_str}%", sucursal),
    ).fetchall()
    conn.close()

    if not rows:
        return RedirectResponse(
            f"/egresos?resumen=Sin facturas", status_code=303
        )

    registros = [dict(r) for r in rows]
    pue = [r for r in registros if (r.get("metodo_pago") or "") != "PPD"]
    ppd = [r for r in registros if (r.get("metodo_pago") or "") == "PPD"]

    tmp = tempfile.NamedTemporaryFile(
        prefix="egresos_", suffix=".zip", delete=False
    )
    tmp.close()
    prefijo = f"Contabilidad {anio}/Contabilidad {mes_nombre_es}/Egreso"

    with zipfile.ZipFile(tmp.name, "w", zipfile.ZIP_DEFLATED) as zf:
        for r in registros:
            metodo = r.get("metodo_pago") or "PUE"
            forma = "PPD" if metodo == "PPD" else (r.get("forma_pago") or "Efectivo")
            serie = (r.get("serie") or "").strip()
            folio = r.get("folio", "")
            nombre_base = f"{serie}-{folio}" if serie else f"{folio}"
            nombre_xml = f"{nombre_base}.xml"
            nombre_pdf = f"{nombre_base}.pdf"

            ruta_xml = (
                em.carpeta_xml(anio, em.MESES[mes - 1], sucursal, metodo, forma)
                / nombre_xml
            )
            if ruta_xml.exists():
                zf.write(
                    ruta_xml,
                    f"{prefijo}/{sucursal}/{metodo}/{forma}/{nombre_xml}",
                )

            ruta_pdf = (
                em.carpeta_pdf(anio, em.MESES[mes - 1], sucursal, metodo, forma)
                / nombre_pdf
            )
            if ruta_pdf.exists():
                zf.write(
                    ruta_pdf,
                    f"{prefijo}/{sucursal}/{metodo}/{forma}/{nombre_pdf}",
                )

        if pue:
            xlsx = tempfile.NamedTemporaryFile(
                prefix="pue_", suffix=".xlsx", delete=False
            )
            xlsx.close()
            try:
                generar_excel_pue(
                    pue, xlsx.name, mes_nombre_es.capitalize(), anio
                )
                zf.write(
                    xlsx.name,
                    f"{prefijo}/Deposito_Egreso/"
                    f"RELACION FACTURAS PUE - {mes_nombre_es} {anio}.xlsx",
                )
            finally:
                Path(xlsx.name).unlink(missing_ok=True)

        if ppd:
            xlsx = tempfile.NamedTemporaryFile(
                prefix="ppd_", suffix=".xlsx", delete=False
            )
            xlsx.close()
            try:
                generar_excel_ppd(
                    ppd, xlsx.name, mes_nombre_es.capitalize(), anio
                )
                zf.write(
                    xlsx.name,
                    f"{prefijo}/Deposito_Egreso/"
                    f"RELACION FACTURAS PPD - {mes_nombre_es} {anio}.xlsx",
                )
            finally:
                Path(xlsx.name).unlink(missing_ok=True)

    return FileResponse(
        tmp.name,
        filename=f"egresos_{anio}_{mes_nombre_es}_{sucursal.lower()}.zip",
        media_type="application/zip",
    )


# ============================================================
# RECHAZADOS
# ============================================================
@router.get("/rechazados", response_class=HTMLResponse)
def rechazados(request: Request, mensaje: str = ""):
    base = em.RECHAZADOS
    lista = []

    if base.exists():
        for carpeta in sorted(base.rglob("*")):
            if not carpeta.is_dir():
                continue
            for xml in carpeta.glob("*.xml"):
                error_txt = xml.with_suffix(".error.txt")
                error = ""
                if error_txt.exists():
                    try:
                        error = error_txt.read_text(encoding="utf-8")
                    except Exception:
                        pass
                lista.append({
                    "carpeta_rel": str(carpeta.relative_to(base)),
                    "nombre": xml.stem,
                    "xml": xml,
                    "error": error,
                })

    return templates.TemplateResponse(
        "egresos_rechazados.html",
        {
            "request": request,
            "rechazados": lista,
            "n_rechazados": len(lista),
            "mensaje": mensaje,
        },
    )


@router.get("/rechazados/ver/{carpeta_rel:path}/{nombre}")
def ver_rechazado(carpeta_rel: str, nombre: str):
    xml = em.RECHAZADOS / carpeta_rel / f"{nombre}.xml"
    if not xml.exists():
        return RedirectResponse(
            "/egresos/rechazados?mensaje=Archivo no encontrado",
            status_code=303,
        )
    ruta_rel = xml.relative_to(em.UPLOADS).as_posix()
    return RedirectResponse(f"/uploads/egresos/{ruta_rel}", status_code=303)


@router.post("/rechazados/eliminar")
def eliminar_rechazado(
    carpeta_rel: str = Form(...),
    nombre: str = Form(...),
):
    xml = em.RECHAZADOS / carpeta_rel / f"{nombre}.xml"
    error = em.RECHAZADOS / carpeta_rel / f"{nombre}.error.txt"

    eliminados = 0
    if xml.exists():
        try:
            xml.unlink()
            eliminados += 1
        except Exception:
            pass
    if error.exists():
        try:
            error.unlink()
        except Exception:
            pass

    carpeta = em.RECHAZADOS / carpeta_rel
    if carpeta.exists():
        try:
            if not any(carpeta.iterdir()):
                carpeta.rmdir()
        except Exception:
            pass

    return RedirectResponse(
        f"/egresos/rechazados?mensaje={eliminados} archivo(s) eliminados",
        status_code=303,
    )


# ============================================================
# HISTORIAL DEL SAT
# ============================================================
@router.get("/historial", response_class=HTMLResponse)
def historial(request: Request, mensaje: str = ""):
    from core import sat_historial as hist

    snapshots = []
    if hist.HISTORIAL_DIR.exists():
        for carpeta in sorted(hist.HISTORIAL_DIR.iterdir(), reverse=True):
            if not carpeta.is_dir() or carpeta.name == "_errores":
                continue

            meta_path = carpeta / "meta.json"
            meta = {}
            if meta_path.exists():
                try:
                    meta = json.loads(meta_path.read_text(encoding="utf-8"))
                except Exception:
                    pass

            xmls_dir = carpeta / "xmls"
            num_xmls = len(list(xmls_dir.glob("*.xml"))) if xmls_dir.exists() else 0

            snapshots.append({
                "carpeta": carpeta.name,
                "id_solicitud": meta.get("id_solicitud", ""),
                "fecha_inicio": meta.get("fecha_inicio", ""),
                "fecha_fin": meta.get("fecha_fin", ""),
                "estado_final": meta.get("estado_final", ""),
                "num_xmls": num_xmls,
            })

    return templates.TemplateResponse(
        "egresos_historial.html",
        {
            "request": request,
            "snapshots": snapshots,
            "mensaje": mensaje,
        },
    )


@router.post("/historial/reprocesar/{carpeta}")
def reprocesar_historial(carpeta: str):
    from core import sat_historial as hist

    snapshot = hist.HISTORIAL_DIR / carpeta
    if not snapshot.exists():
        return RedirectResponse(
            "/egresos/historial?mensaje=Snapshot no encontrado",
            status_code=303,
        )

    xmls_dir = snapshot / "xmls"
    if not xmls_dir.exists():
        return RedirectResponse(
            "/egresos/historial?mensaje=No hay XMLs en ese snapshot",
            status_code=303,
        )

    facturas = sat.procesar_xmls(xmls_dir)
    nuevas = 0
    duplicadas = 0
    errores = 0
    pdfs_generados = 0
    prov = sat.cargar_proveedores_sucursal()

    for f in facturas:
        try:
            uuid_f = (f.get("uuid") or "").strip().upper()
            if not uuid_f:
                continue

            conn = get_conn()
            if conn.execute(
                "SELECT 1 FROM egresos WHERE uuid = ?", (uuid_f,)
            ).fetchone():
                conn.close()
                duplicadas += 1
                continue

            rfc_emisor = (f.get("rfc_emisor") or "").strip().upper()
            sucursal = prov.get(rfc_emisor, "Baalak")

            fecha_iso = ""
            if f.get("fecha"):
                try:
                    fecha_iso = datetime.strptime(
                        f["fecha"], "%d/%m/%Y"
                    ).strftime("%Y-%m-%d")
                except ValueError:
                    pass

            anio, mes = em._mes_de_fecha(fecha_iso)
            ruta_xml = Path(f.get("ruta_xml", ""))

            if ruta_xml.exists():
                try:
                    xml_final = em.mover_xml_a_destino(
                        ruta_xml, anio, mes, sucursal,
                        f.get("metodo_pago", "PUE"),
                        f.get("forma_pago_texto", "Efectivo"),
                        f.get("serie", ""),
                        f.get("folio", ""),
                    )
                    if xml_final and xml_final.exists():
                        pdf_path = em.generar_pdf_desde_xml(
                            xml_final, anio, mes, sucursal,
                            f.get("metodo_pago", "PUE"),
                            f.get("forma_pago_texto", "Efectivo"),
                            f.get("serie", ""),
                            f.get("folio", ""),
                        )
                        if pdf_path:
                            pdfs_generados += 1
                except Exception:
                    errores += 1

            conn.execute(
                "INSERT INTO egresos "
                "(fecha, folio, uuid, proveedor, rfc, total, sucursal, "
                "metodo_pago, forma_pago, notas, serie) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    fecha_iso,
                    f.get("folio", ""),
                    uuid_f,
                    f.get("nombre_emisor", ""),
                    rfc_emisor,
                    f.get("total", 0),
                    sucursal,
                    f.get("metodo_pago", "PUE"),
                    f.get("forma_pago_texto", "Efectivo"),
                    f.get("observacion", ""),
                    f.get("serie", ""),
                ),
            )
            conn.commit()
            conn.close()
            nuevas += 1
        except Exception:
            errores += 1

    resumen = (
        f"Reprocesadas: {nuevas} | Duplicadas: {duplicadas} | "
        f"PDFs: {pdfs_generados} | Errores: {errores}"
    )
    return RedirectResponse(
        f"/egresos/historial?mensaje={resumen}",
        status_code=303,
    )


# ============================================================
# RESET
# ============================================================
@router.post("/reset")
def reset_egresos():
    for carpeta in (em.XMLS, em.PDFS, em.RECHAZADOS, em.LOGS, em.TEMPORALES):
        if carpeta.exists():
            for f in list(carpeta.rglob("*")):
                if f.is_file():
                    try:
                        f.unlink()
                    except Exception:
                        pass
            for d in sorted(carpeta.rglob("*"), reverse=True):
                if d.is_dir():
                    try:
                        if not any(d.iterdir()):
                            d.rmdir()
                    except Exception:
                        pass

    conn = get_conn()
    n = conn.execute("SELECT COUNT(*) FROM egresos").fetchone()[0]
    conn.execute("DELETE FROM egresos")
    conn.commit()
    conn.close()

    sat.limpiar_solicitud_activa()
    return RedirectResponse(
        f"/egresos?resumen=Reset: {n} registros eliminados", status_code=303
    )