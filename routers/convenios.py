"""Router de Convenios de Pago."""
import datetime
import json

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from core.convenios.helpers import (
    buscar_ingreso_por_cliente,
    calcular_estado_pago,
    cargar_alertas_vistas,
    fecha_legible,
    generar_folio,
    marcar_alerta_vista,
)
from core.convenios.numero_a_letras import numero_a_letras
from shared.db import get_conn
from shared.rutas import CONVENIOS_CONFIG
from shared.templates_shared import templates

router = APIRouter(prefix="/convenios", tags=["convenios"])


def _cfg() -> dict:
    try:
        with open(CONVENIOS_CONFIG, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"clinica": {}, "alertas": {"dias_por_vencer": 3}}


@router.get("/numero-a-letras")
def numero_a_letras_endpoint(monto: float = 0):
    return JSONResponse({"ok": True, "letra": numero_a_letras(monto)})


# ---------- Listado ----------

@router.get("", response_class=HTMLResponse)
def listado(request: Request):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM convenios ORDER BY fecha DESC, id DESC"
    ).fetchall()
    convenios = []
    vistas = cargar_alertas_vistas()
    hoy = datetime.date.today()
    dias_por_vencer = int(_cfg().get("alertas", {}).get("dias_por_vencer", 3))
    alertas = []
    for r in rows:
        est = calcular_estado_pago(conn, r["id"])
        item = dict(r)
        item.update(est)
        # Calcular estado de alerta
        alerta = None
        if r["estado"] not in ("pagado", "cancelado") and r["fecha_vencimiento"]:
            try:
                fv = datetime.date.fromisoformat(r["fecha_vencimiento"])
                dias = (fv - hoy).days
                if dias < 0:
                    alerta = {"tipo": "vencido", "dias": -dias}
                elif dias <= dias_por_vencer:
                    alerta = {"tipo": "por_vencer", "dias": dias}
            except Exception:
                pass
        item["alerta"] = alerta
        convenios.append(item)
        if alerta and r["id"] not in vistas:
            alertas.append({**item, "alerta": alerta})
    conn.close()
    return templates.TemplateResponse(
        "convenios.html",
        {
            "request": request,
            "convenios": convenios,
            "alertas": alertas,
            "cfg": _cfg(),
        },
    )


# ---------- Formulario ----------

@router.get("/nuevo", response_class=HTMLResponse)
def nuevo(request: Request):
    return templates.TemplateResponse(
        "convenios_form.html",
        {"request": request, "conv": None, "pagos": [], "cfg": _cfg()},
    )


@router.get("/{cid}/editar", response_class=HTMLResponse)
def editar(cid: int, request: Request):
    conn = get_conn()
    conv = conn.execute("SELECT * FROM convenios WHERE id=?", (cid,)).fetchone()
    pagos_rows = conn.execute(
        "SELECT * FROM convenios_pagos WHERE convenio_id=? ORDER BY numero",
        (cid,),
    ).fetchall()
    conn.close()
    if not conv:
        return HTMLResponse("Convenio no encontrado", status_code=404)
    # Convertir a dict para que Jinja2 pueda serializar con tojson
    conv = dict(conv)
    pagos = [dict(p) for p in pagos_rows]
    return templates.TemplateResponse(
        "convenios_form.html",
        {"request": request, "conv": conv, "pagos": pagos, "cfg": _cfg()},
    )


# ---------- Búsqueda de cliente / factura ----------

@router.get("/buscar-cliente")
def buscar_cliente(q: str = "", rfc: str = ""):
    conn = get_conn()
    ing = buscar_ingreso_por_cliente(conn, q, rfc)
    conn.close()
    return JSONResponse({"ok": True, "ingreso": ing})


# ---------- Guardar ----------

@router.post("/guardar")
async def guardar(request: Request):
    data = await request.json()
    conn = get_conn()
    total = float(data.get("monto_total") or 0)
    letra = data.get("monto_letra") or numero_a_letras(total)
    pagos = data.get("pagos") or []
    suma_pagos = sum(float(p.get("importe") or 0) for p in pagos)
    if pagos and abs(suma_pagos - total) > 0.01:
        conn.close()
        return JSONResponse(
            {"ok": False, "error": f"La suma de pagos (${suma_pagos:.2f}) no coincide con el total (${total:.2f})."},
            status_code=400,
        )

    # Vinculación con factura
    ingreso = None
    if data.get("rfc") or data.get("propietario"):
        ingreso = buscar_ingreso_por_cliente(
            conn, data.get("propietario", ""), data.get("rfc", "")
        )
    ingreso_id = data.get("ingreso_id") or (ingreso["id"] if ingreso else None)
    pagado_con_tarjeta = data.get("pagado_con_tarjeta")
    if pagado_con_tarjeta is None and ingreso:
        pagado_con_tarjeta = ingreso["pagado_con_tarjeta"]
    pagado_con_tarjeta = 1 if pagado_con_tarjeta else 0

    cid = data.get("id")
    campos = (
        data.get("fecha", datetime.date.today().isoformat()),
        data.get("propietario", ""),
        data.get("telefono", ""),
        data.get("direccion", ""),
        data.get("mascota", ""),
        data.get("nhc", ""),
        total,
        letra,
        data.get("fecha_vencimiento", ""),
        data.get("lugar_pago", "recepcion"),
        data.get("cuenta_bancaria", ""),
        data.get("notas", ""),
    )
    if cid:
        conn.execute(
            """UPDATE convenios SET fecha=?, propietario=?, telefono=?,
               direccion=?, mascota=?, nhc=?, monto_total=?, monto_letra=?,
               fecha_vencimiento=?, lugar_pago=?, cuenta_bancaria=?, notas=?,
               actualizado_en=CURRENT_TIMESTAMP
               WHERE id=?""",
            campos + (cid,),
        )
        conn.execute("DELETE FROM convenios_pagos WHERE convenio_id=?", (cid,))
    else:
        folio = generar_folio(conn)
        cur = conn.execute(
            """INSERT INTO convenios
               (fecha, propietario, telefono, direccion, mascota, nhc,
                monto_total, monto_letra, fecha_vencimiento, lugar_pago,
                cuenta_bancaria, notas, folio)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            campos + (folio,),
        )
        cid = cur.lastrowid

        for i, p in enumerate(pagos, 1):
            conn.execute(
                """INSERT INTO convenios_pagos
                (convenio_id, numero, fecha, importe, efectuado, fecha_pago,
                    albaran, factura_numero, factura_uuid, tipo_pago, pagado_con_tarjeta)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    cid, i,
                    p.get("fecha", ""),
                    float(p.get("importe") or 0),
                    1 if p.get("efectuado") else 0,
                    p.get("fecha_pago", "") if p.get("efectuado") else "",
                    p.get("albaran", ""),
                    p.get("factura_numero", ""),
                    p.get("factura_uuid", ""),
                    p.get("tipo_pago", ""),
                    1 if p.get("pagado_con_tarjeta") else 0,
                ),
            )

    conn.commit()
    conn.close()
    return JSONResponse({"ok": True, "id": cid})


# ---------- Imprimir ----------

@router.get("/{cid}/imprimir", response_class=HTMLResponse)
def imprimir(cid: int, request: Request):
    conn = get_conn()
    conv = conn.execute("SELECT * FROM convenios WHERE id=?", (cid,)).fetchone()
    pagos_rows = conn.execute(
        "SELECT * FROM convenios_pagos WHERE convenio_id=? ORDER BY numero",
        (cid,),
    ).fetchall()
    conn.close()
    if not conv:
        return HTMLResponse("Convenio no encontrado", status_code=404)
    conv = dict(conv)
    pagos = [dict(p) for p in pagos_rows]
    return templates.TemplateResponse(
        "convenios_print.html",
        {
            "request": request,
            "conv": conv,
            "pagos": pagos,
            "cfg": _cfg(),
            "fecha_legible": fecha_legible,
        },
    )


# ---------- Estados y pagos ----------

@router.post("/{cid}/estado")
async def cambiar_estado(cid: int, request: Request):
    data = await request.json()
    estado = data.get("estado", "borrador")
    if estado not in ("borrador", "impreso", "firmado", "pagado", "cancelado"):
        return JSONResponse({"ok": False, "error": "Estado inválido"}, status_code=400)
    conn = get_conn()
    conn.execute(
        "UPDATE convenios SET estado=?, actualizado_en=CURRENT_TIMESTAMP WHERE id=?",
        (estado, cid),
    )
    conn.commit()
    conn.close()
    return JSONResponse({"ok": True})


@router.post("/{cid}/pago/{pid}/marcar")
async def marcar_pago(cid: int, pid: int, request: Request):
    data = await request.json()
    efectuado = 1 if data.get("efectuado") else 0
    conn = get_conn()
    conn.execute(
        "UPDATE convenios_pagos SET efectuado=?, fecha_pago=? WHERE id=? AND convenio_id=?",
        (
            efectuado,
            datetime.date.today().isoformat() if efectuado else "",
            pid,
            cid,
        ),
    )
    conn.commit()
    # Recalcular estado del convenio
    est = calcular_estado_pago(conn, cid)
    if est["pendiente"] <= 0.01 and est["n_pagos"] > 0:
        conn.execute(
            "UPDATE convenios SET estado='pagado', actualizado_en=CURRENT_TIMESTAMP WHERE id=?",
            (cid,),
        )
        conn.commit()
    conn.close()
    return JSONResponse({"ok": True, "estado_pago": est})


@router.post("/{cid}/eliminar")
async def eliminar(cid: int):
    conn = get_conn()
    conv = conn.execute("SELECT estado FROM convenios WHERE id=?", (cid,)).fetchone()
    if not conv:
        conn.close()
        return JSONResponse({"ok": False, "error": "No encontrado"}, status_code=404)
    if conv["estado"] != "borrador":
        conn.close()
        return JSONResponse(
            {"ok": False, "error": "Solo se pueden eliminar convenios en borrador."},
            status_code=409,
        )
    conn.execute("DELETE FROM convenios_pagos WHERE convenio_id=?", (cid,))
    conn.execute("DELETE FROM convenios WHERE id=?", (cid,))
    conn.commit()
    conn.close()
    return JSONResponse({"ok": True})


@router.post("/{cid}/alerta-vista")
async def alerta_vista(cid: int):
    marcar_alerta_vista(cid)
    return JSONResponse({"ok": True})