"""Router de Convenios de Pago."""
import datetime
import json

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from core.convenios.helpers import (
    buscar_ingreso_por_cliente,
    calcular_estado_pago,
    cargar_alertas_vistas,
    convenio_tiene_pagos_efectuados,
    fecha_legible,
    generar_folio,
    marcar_alerta_vista,
    password_configurada,
    verificar_password,
)
from core.convenios.numero_a_letras import numero_a_letras
from shared.db import get_conn
from shared.rutas import CONVENIOS_CONFIG
from shared.templates_shared import templates

router = APIRouter(prefix="/convenios", tags=["convenios"])

ESTADOS_VALIDOS = ("borrador", "impreso", "firmado", "pagado", "cancelado")

TRANSICIONES_PERMITIDAS = {
    "borrador":  {"impreso", "cancelado"},
    "impreso":   {"firmado", "borrador", "cancelado"},
    "firmado":   {"pagado", "cancelado"},
    "pagado":    set(),          # estado terminal
    "cancelado": set(),          # estado terminal
}

# Etiquetas legibles para mensajes de error
ESTADO_LABEL = {
    "borrador":  "Borrador",
    "impreso":   "Impreso",
    "firmado":   "Firmado",
    "pagado":    "Pagado",
    "cancelado": "Cancelado",
}

def _cfg() -> dict:
    try:
        with open(CONVENIOS_CONFIG, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"clinica": {}, "alertas": {"dias_por_vencer": 3}, "seguridad": {}}


def _validar_transicion(conn, cid: int, estado_actual: str, nuevo_estado: str) -> tuple[bool, str]:
    """
    Valida si se puede pasar de estado_actual a nuevo_estado.
    Devuelve (ok, mensaje_error).
    """
    if nuevo_estado not in ESTADOS_VALIDOS:
        return False, "Estado inválido."

    if nuevo_estado == estado_actual:
        return True, ""

    # Estados terminales no permiten transición
    if estado_actual in ("pagado", "cancelado"):
        return False, f"El convenio está {ESTADO_LABEL[estado_actual].lower()} y no se puede modificar su estado."

    # Validar que la transición esté permitida
    if nuevo_estado not in TRANSICIONES_PERMITIDAS.get(estado_actual, set()):
        return False, (
            f"No se puede pasar de '{ESTADO_LABEL.get(estado_actual, estado_actual)}' "
            f"a '{ESTADO_LABEL.get(nuevo_estado, nuevo_estado)}'."
        )

    # Regla especial: no se puede pasar a 'pagado' si hay pagos pendientes
    if nuevo_estado == "pagado":
        est = calcular_estado_pago(conn, cid)
        if est["pendiente"] > 0.01:
            return False, (
                f"No se puede marcar como pagado: quedan ${est['pendiente']:.2f} pendientes "
                f"de ${est['total']:.2f}."
            )

    return True, ""

@router.get("/numero-a-letras")
def numero_a_letras_endpoint(monto: float = 0):
    return JSONResponse({"ok": True, "letra": numero_a_letras(monto)})


# ---------- Listado ----------

@router.get("", response_class=HTMLResponse)
def listado(
    request: Request,
    estado: str = "",
    desde: str = "",
    hasta: str = "",
    q: str = "",
):
    conn = get_conn()

    # Filtros server-side: estado y rango de fechas
    where = []
    params = []
    if estado and estado in ("borrador", "impreso", "firmado", "pagado", "cancelado"):
        where.append("estado = ?")
        params.append(estado)
    if desde:
        where.append("fecha >= ?")
        params.append(desde)
    if hasta:
        where.append("fecha <= ?")
        params.append(hasta)

    sql = "SELECT * FROM convenios"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY fecha DESC, id DESC"

    rows = conn.execute(sql, params).fetchall()
    convenios = []
    vistas = cargar_alertas_vistas()
    hoy = datetime.date.today()
    dias_por_vencer = int(_cfg().get("alertas", {}).get("dias_por_vencer", 3))
    alertas = []
    for r in rows:
        est = calcular_estado_pago(conn, r["id"])
        item = dict(r)
        item.update(est)
        item["tiene_efectuados"] = est["n_pagados"] > 0
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
            "filtros": {"estado": estado, "desde": desde, "hasta": hasta, "q": q},
        },
    )


# ---------- Formulario ----------

@router.get("/nuevo", response_class=HTMLResponse)
def nuevo(request: Request):
    return templates.TemplateResponse(
        "convenios_form.html",
        {
            "request": request,
            "conv": None,
            "pagos": [],
            "cfg": _cfg(),
            "tiene_efectuados": False,
            "password_configurada": password_configurada(),
        },
    )


@router.get("/{cid}/editar", response_class=HTMLResponse)
def editar(cid: int, request: Request):
    conn = get_conn()
    conv = conn.execute("SELECT * FROM convenios WHERE id=?", (cid,)).fetchone()
    pagos_rows = conn.execute(
        "SELECT * FROM convenios_pagos WHERE convenio_id=? ORDER BY numero",
        (cid,),
    ).fetchall()
    tiene_efectuados = convenio_tiene_pagos_efectuados(conn, cid)
    conn.close()
    if not conv:
        return HTMLResponse("Convenio no encontrado", status_code=404)
    pagos = [dict(p) for p in pagos_rows]
    return templates.TemplateResponse(
        "convenios_form.html",
        {
            "request": request,
            "conv": conv,
            "pagos": pagos,
            "cfg": _cfg(),
            "tiene_efectuados": tiene_efectuados,
            "password_configurada": password_configurada(),
        },
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
    try:
        cid = data.get("id")

        total = float(data.get("monto_total") or 0)
        letra = data.get("monto_letra") or numero_a_letras(total)
        pagos = data.get("pagos") or []
        suma_pagos = sum(float(p.get("importe") or 0) for p in pagos)

        if pagos and abs(suma_pagos - total) > 0.01:
            return JSONResponse(
                {"ok": False, "error": f"La suma de pagos (${suma_pagos:.2f}) no coincide con el total (${total:.2f})."},
                status_code=400,
            )

        # --- Verificaciones para convenios existentes ---
        if cid:
            conv_actual = conn.execute(
                "SELECT estado, monto_total, fecha, propietario, mascota FROM convenios WHERE id=?",
                (cid,),
            ).fetchone()
            if not conv_actual:
                return JSONResponse(
                    {"ok": False, "error": "Convenio no encontrado."},
                    status_code=404,
                )

            estado_actual = conv_actual["estado"]

            # 1) Estados terminales: no se puede modificar nada estructural
            if estado_actual in ("pagado", "cancelado"):
                cambio_estructural = (
                    abs(total - float(conv_actual["monto_total"])) > 0.01
                    or data.get("fecha") != conv_actual["fecha"]
                    or data.get("propietario") != conv_actual["propietario"]
                    or data.get("mascota") != conv_actual["mascota"]
                )
                if cambio_estructural:
                    return JSONResponse(
                        {"ok": False, "error": f"No se puede modificar un convenio en estado '{estado_actual}'. Solo puedes marcar/desmarcar pagos."},
                        status_code=409,
                    )

            # 2) Si hay pagos efectuados, se requiere contraseña y no se puede
            #    cambiar monto/fecha/propietario/mascota (regla 75).
            if convenio_tiene_pagos_efectuados(conn, cid):
                if password_configurada() and not verificar_password(data.get("password", "")):
                    return JSONResponse(
                        {"ok": False, "error": "Se requiere contraseña para modificar un convenio con pagos efectuados."},
                        status_code=401,
                    )
                cambio_estructural = (
                    abs(total - float(conv_actual["monto_total"])) > 0.01
                    or data.get("fecha") != conv_actual["fecha"]
                    or data.get("propietario") != conv_actual["propietario"]
                    or data.get("mascota") != conv_actual["mascota"]
                )
                if cambio_estructural:
                    return JSONResponse(
                        {"ok": False, "error": "No puedes modificar monto, fecha, propietario ni mascota cuando hay pagos efectuados."},
                        status_code=409,
                    )

        # --- Datos del convenio ---
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

        # --- Upsert de pagos (respeta los efectuados) ---
        pagos_existentes = {
            r["id"]: dict(r)
            for r in conn.execute(
                "SELECT * FROM convenios_pagos WHERE convenio_id=?", (cid,)
            ).fetchall()
        }

        ids_enviados = set()
        for i, p in enumerate(pagos, 1):
            pid = p.get("id")
            if pid and pid in pagos_existentes:
                ids_enviados.add(pid)
                existente = pagos_existentes[pid]
                if existente["efectuado"]:
                    # No se toca un pago efectuado
                    continue
                conn.execute(
                    """UPDATE convenios_pagos SET numero=?, fecha=?, importe=?,
                       efectuado=?, fecha_pago=?, albaran=?, factura_numero=?,
                       factura_uuid=?, tipo_pago=?, pagado_con_tarjeta=?
                       WHERE id=?""",
                    (
                        i, p.get("fecha", ""), float(p.get("importe") or 0),
                        1 if p.get("efectuado") else 0,
                        p.get("fecha_pago", "") if p.get("efectuado") else "",
                        p.get("albaran", ""), p.get("factura_numero", ""),
                        p.get("factura_uuid", ""), p.get("tipo_pago", ""),
                        1 if p.get("pagado_con_tarjeta") else 0,
                        pid,
                    ),
                )
            else:
                cur = conn.execute(
                    """INSERT INTO convenios_pagos
                       (convenio_id, numero, fecha, importe, efectuado, fecha_pago,
                        albaran, factura_numero, factura_uuid, tipo_pago, pagado_con_tarjeta)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        cid, i, p.get("fecha", ""), float(p.get("importe") or 0),
                        1 if p.get("efectuado") else 0,
                        p.get("fecha_pago", "") if p.get("efectuado") else "",
                        p.get("albaran", ""), p.get("factura_numero", ""),
                        p.get("factura_uuid", ""), p.get("tipo_pago", ""),
                        1 if p.get("pagado_con_tarjeta") else 0,
                    ),
                )
                ids_enviados.add(cur.lastrowid)

        # Borrar los que ya no vienen en el payload (solo si no están efectuados)
        for pid, p in pagos_existentes.items():
            if pid not in ids_enviados and not p["efectuado"]:
                conn.execute("DELETE FROM convenios_pagos WHERE id=?", (pid,))

        conn.commit()
        return JSONResponse({"ok": True, "id": cid})
    finally:
        conn.close()


# ---------- Imprimir ----------

@router.get("/{cid}/imprimir", response_class=HTMLResponse)
def imprimir(cid: int, request: Request):
    conn = get_conn()
    conv = conn.execute("SELECT * FROM convenios WHERE id=?", (cid,)).fetchone()
    pagos = conn.execute(
        "SELECT * FROM convenios_pagos WHERE convenio_id=? ORDER BY numero",
        (cid,),
    ).fetchall()
    conn.close()
    if not conv:
        return HTMLResponse("Convenio no encontrado", status_code=404)
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
    nuevo_estado = (data.get("estado") or "").strip()

    conn = get_conn()
    try:
        conv = conn.execute("SELECT estado FROM convenios WHERE id=?", (cid,)).fetchone()
        if not conv:
            return JSONResponse(
                {"ok": False, "error": "Convenio no encontrado."},
                status_code=404,
            )

        estado_actual = (conv["estado"] or "borrador").strip()

        ok, error = _validar_transicion(conn, cid, estado_actual, nuevo_estado)
        if not ok:
            return JSONResponse({"ok": False, "error": error}, status_code=409)

        conn.execute(
            "UPDATE convenios SET estado=?, actualizado_en=CURRENT_TIMESTAMP WHERE id=?",
            (nuevo_estado, cid),
        )
        conn.commit()
        return JSONResponse({
            "ok": True,
            "estado_anterior": estado_actual,
            "estado_nuevo": nuevo_estado,
        })
    finally:
        conn.close()


@router.post("/{cid}/pago/{pid}/marcar")
async def marcar_pago(cid: int, pid: int, request: Request):
    data = await request.json()
    efectuado = 1 if data.get("efectuado") else 0

    conn = get_conn()
    try:
        # Verificar que el convenio no esté cancelado
        conv = conn.execute("SELECT estado FROM convenios WHERE id=?", (cid,)).fetchone()
        if not conv:
            return JSONResponse({"ok": False, "error": "Convenio no encontrado."}, status_code=404)
        if conv["estado"] == "cancelado":
            return JSONResponse(
                {"ok": False, "error": "No se puede modificar un convenio cancelado."},
                status_code=409,
            )

        conn.execute(
            "UPDATE convenios_pagos SET efectuado=?, fecha_pago=? WHERE id=? AND convenio_id=?",
            (
                efectuado,
                datetime.date.today().isoformat() if efectuado else "",
                pid,
                cid,
            ),
        )

        est = calcular_estado_pago(conn, cid)
        if est["pendiente"] <= 0.01 and est["n_pagos"] > 0 and conv["estado"] != "pagado":
            conn.execute(
                "UPDATE convenios SET estado='pagado', actualizado_en=CURRENT_TIMESTAMP WHERE id=?",
                (cid,),
            )

        conn.commit()
        return JSONResponse({"ok": True, "estado_pago": est})
    finally:
        conn.close()


@router.post("/{cid}/eliminar")
async def eliminar(cid: int):
    conn = get_conn()
    conv = conn.execute("SELECT estado FROM convenios WHERE id=?", (cid,)).fetchone()
    if not conv:
        conn.close()
        return JSONResponse({"ok": False, "error": "No encontrado"}, status_code=404)
    if convenio_tiene_pagos_efectuados(conn, cid):
        conn.close()
        return JSONResponse(
            {"ok": False, "error": "No se puede eliminar un convenio con pagos efectuados."},
            status_code=409,
        )
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


# ---------- Exportar Excel ----------

@router.get("/excel")
def exportar_excel(
    estado: str = "",
    desde: str = "",
    hasta: str = "",
    q: str = "",
):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    from fastapi.responses import StreamingResponse
    import io
    from datetime import datetime

    conn = get_conn()

    # Mismos filtros que el listado
    where = []
    params = []
    if estado and estado in ("borrador", "impreso", "firmado", "pagado", "cancelado"):
        where.append("estado = ?")
        params.append(estado)
    if desde:
        where.append("fecha >= ?")
        params.append(desde)
    if hasta:
        where.append("fecha <= ?")
        params.append(hasta)

    sql = "SELECT * FROM convenios"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY fecha DESC, id DESC"

    rows = conn.execute(sql, params).fetchall()

    # Filtro por texto (client-side en el listado, aquí lo aplicamos en Python)
    if q:
        ql = q.lower().strip()
        rows = [
            r for r in rows
            if any(ql in (str(r[c] or "")).lower() for c in
                   ("folio", "propietario", "mascota", "nhc", "telefono", "notas"))
        ]

    wb = Workbook()

    # Hoja 1: Convenios
    ws = wb.active
    assert ws is not None
    ws.title = "Convenios"

    headers = ["Folio", "Fecha", "Propietario", "Teléfono", "Mascota", "NHC",
               "Monto total", "Pagado", "Pendiente", "Vencimiento",
               "Estado", "Lugar de pago", "Notas"]
    ws.append(headers)
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="206BC4")
        cell.alignment = Alignment(horizontal="center", vertical="center")

    for r in rows:
        est = calcular_estado_pago(conn, r["id"])
        ws.append([
            r["folio"] or "",
            r["fecha"] or "",
            r["propietario"] or "",
            r["telefono"] or "",
            r["mascota"] or "",
            r["nhc"] or "",
            float(r["monto_total"] or 0),
            est["pagado"],
            est["pendiente"],
            r["fecha_vencimiento"] or "",
            r["estado"] or "",
            r["lugar_pago"] or "",
            r["notas"] or "",
        ])

    # Formato de moneda
    for row in ws.iter_rows(min_row=2, min_col=7, max_col=9):
        for cell in row:
            cell.number_format = '"$"#,##0.00'

    # Anchos de columna
    anchos = [14, 12, 30, 14, 18, 10, 14, 14, 14, 14, 12, 16, 30]
    for i, w in enumerate(anchos, 1):
        ws.column_dimensions[chr(64 + i)].width = w

    ws.freeze_panes = "A2"

    # Hoja 2: Pagos
    ws2 = wb.create_sheet("Pagos")
    headers2 = ["Folio", "Propietario", "# Pago", "Fecha", "Importe",
                "Efectuado", "Fecha de pago", "Albarán", "Factura",
                "UUID factura", "Tipo de pago"]
    ws2.append(headers2)
    for cell in ws2[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="206BC4")
        cell.alignment = Alignment(horizontal="center", vertical="center")

    for r in rows:
        pagos = conn.execute(
            "SELECT * FROM convenios_pagos WHERE convenio_id=? ORDER BY numero",
            (r["id"],),
        ).fetchall()
        for p in pagos:
            ws2.append([
                r["folio"] or "",
                r["propietario"] or "",
                p["numero"],
                p["fecha"] or "",
                float(p["importe"] or 0),
                "Sí" if p["efectuado"] else "No",
                p["fecha_pago"] or "",
                p["albaran"] or "",
                p["factura_numero"] or "",
                p["factura_uuid"] or "",
                p["tipo_pago"] or "",
            ])

    for row in ws2.iter_rows(min_row=2, min_col=5, max_col=5):
        for cell in row:
            cell.number_format = '"$"#,##0.00'

    anchos2 = [14, 30, 8, 12, 14, 10, 14, 14, 16, 38, 18]
    for i, w in enumerate(anchos2, 1):
        ws2.column_dimensions[chr(64 + i)].width = w

    ws2.freeze_panes = "A2"

    conn.close()

    # Guardar en memoria
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    filename = f"Convenios_{datetime.now().strftime('%Y-%m-%d_%H%M')}.xlsx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------- Reportes (árbol Año → Mes → Estado) ----------

@router.get("/arbol")
def arbol_convenios():
    """Árbol Año → Mes → Estado con conteos y montos.

    Estructura:
        {
          "2026": {
            "11": {
              "borrador": {"n": 2, "total": 5000.0},
              "pagado":   {"n": 1, "total": 1200.0},
              "_total":   {"n": 3, "total": 6200.0}
            },
            "_total": {"n": 3, "total": 6200.0}
          },
          "_total": {"n": 3, "total": 6200.0}
        }

    El `_total` raíz es obligatorio: sin él, el footer del modal sale en 0
    (regla 21 de CONTEXTO.md).
    """
    conn = get_conn()
    filas = conn.execute("""
        SELECT fecha, estado, monto_total
        FROM convenios
        WHERE fecha IS NOT NULL AND fecha != ''
    """).fetchall()
    conn.close()

    arbol: dict = {}
    for r in filas:
        fecha = (r["fecha"] or "").strip()
        if len(fecha) < 7:
            continue
        a = fecha[:4]          # "2026"
        m = fecha[5:7]         # "11"
        est = (r["estado"] or "borrador").strip().lower()
        t = round(float(r["monto_total"] or 0), 2)

        # Nivel estado
        arbol.setdefault(a, {}) \
             .setdefault(m, {}) \
             .setdefault(est, {"n": 0, "total": 0.0})
        arbol[a][m][est]["n"] += 1
        arbol[a][m][est]["total"] = round(arbol[a][m][est]["total"] + t, 2)

        # _total del mes
        arbol[a][m].setdefault("_total", {"n": 0, "total": 0.0})
        arbol[a][m]["_total"]["n"] += 1
        arbol[a][m]["_total"]["total"] = round(
            arbol[a][m]["_total"]["total"] + t, 2)

        # _total del año
        arbol[a].setdefault("_total", {"n": 0, "total": 0.0})
        arbol[a]["_total"]["n"] += 1
        arbol[a]["_total"]["total"] = round(
            arbol[a]["_total"]["total"] + t, 2)

    # _total raíz
    arbol["_total"] = {
        "n": sum(v["_total"]["n"] for k, v in arbol.items() if k != "_total"),
        "total": round(
            sum(v["_total"]["total"] for k, v in arbol.items() if k != "_total"),
            2,
        ),
    }

    resp = JSONResponse(arbol)
    resp.headers["Cache-Control"] = "no-store"
    return resp


@router.post("/{cid}/alerta-vista")
async def alerta_vista(cid: int):
    marcar_alerta_vista(cid)
    return JSONResponse({"ok": True})


@router.post("/verificar-password")
async def verificar_password_endpoint(request: Request):
    data = await request.json()
    if verificar_password(data.get("password", "")):
        return JSONResponse({"ok": True})
    return JSONResponse({"ok": False, "error": "Contraseña incorrecta."}, status_code=401)