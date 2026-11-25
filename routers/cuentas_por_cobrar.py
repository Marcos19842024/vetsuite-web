# routers/cuentas_por_cobrar.py
from __future__ import annotations
from datetime import date, datetime
from pathlib import Path

from fastapi import APIRouter, Request, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates

from shared.db import get_conn
from shared.rutas import CPC_DIR
from shared.templates_shared import templates
from core.cuentas_por_cobrar.parser_qvet import parsear_excel_qvet
from core.cuentas_por_cobrar import calculos, bitacora, config, cruce_convenios
from core.cuentas_por_cobrar import config as cpc_config
from core.cuentas_por_cobrar import whatsapp as cpc_whatsapp

router = APIRouter(prefix="/cuentas_por_cobrar", tags=["cuentas por cobrar"])

CPC_DIR.mkdir(parents=True, exist_ok=True)


# ---------- Helpers ----------

def _fila_cliente_a_dict(r) -> dict:
    d = dict(r)
    d["dias_antiguedad"] = calculos.dias_antiguedad(d.get("fecha_mas_antigua", ""))
    d["semaforo"] = calculos.semaforo(d["dias_antiguedad"])
    return d


def _decidir_campo(nuevo: str, actual: str, origen: str) -> tuple[str, str]:
    if origen == "manual":
        return actual, "manual"
    if nuevo:
        return nuevo, "qvet"
    return actual, origen


def _upsert_cliente(conn, cli: dict) -> tuple[int, bool]:
    idq = (cli.get("idcliente_qvet") or "").strip()
    if not idq or idq.lower() in ("none", "null"):
        raise ValueError(f"idcliente_qvet inválido: {idq!r}")

    row = conn.execute(
        """SELECT id, telefono, telefono_origen, email, email_origen
           FROM cpc_clientes WHERE idcliente_qvet = ?""",
        (idq,),
    ).fetchone()

    hoy = date.today().isoformat()
    dias = calculos.dias_antiguedad(cli["fecha_mas_antigua"])
    sem = calculos.semaforo(dias)

    if row:
        cid = row["id"]
        tel_final,   tel_origen   = _decidir_campo(cli.get("telefono",""), row["telefono"], row["telefono_origen"])
        email_final, email_origen = _decidir_campo(cli.get("email",""),    row["email"],    row["email_origen"])

        conn.execute(
            """UPDATE cpc_clientes SET
                 nombre = ?, sucursal = ?,
                 telefono = ?, telefono_origen = ?,
                 email = ?, email_origen = ?,
                 monto_total = ?, monto_cobrado = ?, saldo = ?,
                 n_albaranes = ?, fecha_mas_antigua = ?,
                 dias_antiguedad = ?, semaforo = ?,
                 actualizado_en = ?
               WHERE id = ?""",
            (cli["nombre"], cli.get("sucursal",""),
             tel_final, tel_origen,
             email_final, email_origen,
             cli["monto_total"], cli["monto_cobrado"], cli["saldo"],
             cli["n_albaranes"], cli["fecha_mas_antigua"],
             dias, sem, hoy, cid),
        )
        es_nuevo = False
    else:
        cur = conn.execute(
            """INSERT INTO cpc_clientes
               (idcliente_qvet, nombre, es_institucional, sucursal,
                telefono, telefono_origen, email, email_origen,
                monto_total, monto_cobrado, saldo, n_albaranes,
                fecha_mas_antigua, dias_antiguedad, semaforo,
                estado, prioridad)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (idq, cli["nombre"], 1 if cli["es_institucional"] else 0, cli.get("sucursal",""),
             cli.get("telefono",""), "qvet" if cli.get("telefono") else "",
             cli.get("email",""),    "qvet" if cli.get("email") else "",
             cli["monto_total"], cli["monto_cobrado"], cli["saldo"],
             cli["n_albaranes"], cli["fecha_mas_antigua"], dias, sem,
             "institucional" if cli["es_institucional"] else "pendiente",
             "normal"),
        )
        cid = cur.lastrowid
        es_nuevo = True

    for alb in cli["albaranes"]:
        conn.execute(
            """INSERT INTO cpc_albaranes
               (cpc_cliente_id, codigo_albaran, num_albaran, idmascota_qvet,
                paciente, nhc, fecha_albaran, fecha_factura, numero_factura,
                observaciones_factura, total_importe, cobrado_linea,
                a_cuenta, vales, deuda)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(codigo_albaran) DO UPDATE SET
                 cpc_cliente_id=excluded.cpc_cliente_id,
                 num_albaran=excluded.num_albaran,
                 idmascota_qvet=excluded.idmascota_qvet,
                 paciente=excluded.paciente,
                 nhc=excluded.nhc,
                 fecha_albaran=excluded.fecha_albaran,
                 fecha_factura=excluded.fecha_factura,
                 numero_factura=excluded.numero_factura,
                 observaciones_factura=excluded.observaciones_factura,
                 total_importe=excluded.total_importe,
                 cobrado_linea=excluded.cobrado_linea,
                 a_cuenta=excluded.a_cuenta,
                 vales=excluded.vales,
                 deuda=excluded.deuda""",
            (cid, alb["codigo_albaran"], alb["num_albaran"], alb["idmascota_qvet"],
             alb["paciente"], alb["nhc"], alb["fecha_albaran"], alb["fecha_factura"],
             alb["numero_factura"], alb["observaciones_factura"],
             alb["total_importe"], alb["cobrado_linea"],
             alb["a_cuenta"], alb["vales"], alb["deuda"]),
        )

    if cli["saldo"] <= 0:
        conn.execute(
            """UPDATE cpc_clientes
               SET estado = 'pagado'
               WHERE id = ? AND es_institucional = 0
                 AND estado NOT IN ('pagado', 'cancelado', 'convenio', 'disputa', 'institucional')""",
            (cid,),
        )

    return cid, es_nuevo


def _buscar_promesa_vigente(conn, cid: int) -> dict | None:
    """Devuelve la última promesa de pago vigente del cliente o None."""
    return conn.execute(
        """SELECT promesa_fecha, promesa_monto
           FROM cpc_bitacora
           WHERE cpc_cliente_id = ?
             AND resultado = 'promesa_pago'
             AND promesa_fecha != ''
             AND promesa_fecha >= ?
           ORDER BY fecha DESC, hora DESC, id DESC
           LIMIT 1""",
        (cid, date.today().isoformat()),
    ).fetchone()


# ---------- Página ----------

@router.get("", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(
        "cuentas_por_cobrar.html",
        {"request": request},
    )


# ---------- Datos ----------

@router.get("/datos")
def datos(
    estado: str = "",
    semaforo: str = "",
    prioridad: str = "",
    desde: str = "",
    hasta: str = "",
    q: str = "",
    solo_vencidas: int = 0,
    incluir_institucionales: int = 0,
    incluir_convenios: int = 0,
):
    conn = get_conn()
    try:
        where = ["1=1"]
        params: list = []

        if estado:
            where.append("estado = ?")
            params.append(estado)
        if semaforo:
            where.append("semaforo = ?")
            params.append(semaforo)
        if prioridad:
            where.append("prioridad = ?")
            params.append(prioridad)
        if desde:
            where.append("fecha_mas_antigua >= ?")
            params.append(desde)
        if hasta:
            where.append("fecha_mas_antigua <= ?")
            params.append(hasta)
        if solo_vencidas:
            where.append("saldo > 0")

        sql = f"SELECT * FROM cpc_clientes WHERE {' AND '.join(where)} ORDER BY dias_antiguedad DESC, nombre ASC"
        rows = conn.execute(sql, params).fetchall()
        filas = [_fila_cliente_a_dict(r) for r in rows]

        totales = {
            "n": len(filas),
            "monto_total": round(sum(f["monto_total"] for f in filas), 2),
            "monto_cobrado": round(sum(f["monto_cobrado"] for f in filas), 2),
            "saldo": round(sum(f["saldo"] for f in filas), 2),
        }

        return JSONResponse(
            {"filas": filas, "totales": totales},
            headers={"Cache-Control": "no-store"},
        )
    finally:
        conn.close()


# ---------- Plantillas WhatsApp ----------

@router.get("/plantillas")
def listar_plantillas():
    """Lista las plantillas de WhatsApp disponibles y la activa."""
    cfg = cpc_config.cargar_config()
    plantillas = cfg.get("plantillas_whatsapp", {})
    activa = cfg.get("plantilla_activa", "recordatorio_amable")
    return JSONResponse(
        {
            "ok": True,
            "plantillas": [
                {"clave": k, "texto": v} for k, v in plantillas.items()
            ],
            "activa": activa,
        },
        headers={"Cache-Control": "no-store"},
    )


@router.post("/plantilla-activa")
async def guardar_plantilla_activa(request: Request):
    """Guarda la plantilla activa en el config (server-side)."""
    data = await request.json()
    clave = (data.get("plantilla") or "").strip()
    if not clave:
        return JSONResponse({"ok": False, "error": "Falta el campo 'plantilla'."}, status_code=400)

    cfg = cpc_config.cargar_config()
    plantillas = cfg.get("plantillas_whatsapp", {})
    if clave not in plantillas:
        return JSONResponse({"ok": False, "error": f"Plantilla '{clave}' no existe."}, status_code=400)

    cfg["plantilla_activa"] = clave
    cpc_config.guardar_config(cfg)
    return JSONResponse({"ok": True, "activa": clave})


# ---------- Detalle ----------

@router.get("/{cid}")
def detalle(cid: int):
    conn = get_conn()
    try:
        row = conn.execute("SELECT * FROM cpc_clientes WHERE id = ?", (cid,)).fetchone()
        if not row:
            raise HTTPException(404, "Cliente no encontrado")
        cliente = _fila_cliente_a_dict(row)
        albaranes = [dict(a) for a in conn.execute(
            "SELECT * FROM cpc_albaranes WHERE cpc_cliente_id = ? ORDER BY fecha_albaran ASC",
            (cid,),
        ).fetchall()]
        entradas = bitacora.listar_entradas(conn, cid)
        verificado = bitacora.verificado_en_qvet(conn, cid)

        promesa = _buscar_promesa_vigente(conn, cid)

        return JSONResponse(
            {
                "cliente": cliente,
                "albaranes": albaranes,
                "bitacora": entradas,
                "verificado_en_qvet": verificado,
                "tiene_promesa_vigente": promesa is not None,
                "promesa_fecha": promesa["promesa_fecha"] if promesa else "",
                "promesa_monto": float(promesa["promesa_monto"]) if promesa else 0,
            },
            headers={"Cache-Control": "no-store"},
        )
    finally:
        conn.close()


# ---------- Importar ----------

@router.post("/importar")
async def importar(archivo: UploadFile = File(...)):
    assert archivo.filename is not None
    if not archivo.filename.lower().endswith(".xlsx"):
        raise HTTPException(400, "El archivo debe ser .xlsx")

    contenido = await archivo.read()
    destino = CPC_DIR / f"_import_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.xlsx"
    destino.write_bytes(contenido)

    try:
        parsed = parsear_excel_qvet(destino)
    except ValueError as e:
        raise HTTPException(400, str(e))
    finally:
        try:
            destino.unlink()
        except OSError:
            pass

    conn = get_conn()
    try:
        nuevos = 0
        actualizados = 0
        alb_nuevos = 0
        alb_actualizados = 0

        codigos_vistos: set[str] = set()

        for cli in parsed["clientes"]:
            antes = conn.execute(
                "SELECT id FROM cpc_clientes WHERE idcliente_qvet = ?",
                (cli["idcliente_qvet"],),
            ).fetchone()
            if antes:
                prev = conn.execute(
                    "SELECT codigo_albaran FROM cpc_albaranes WHERE cpc_cliente_id = ?",
                    (antes["id"],),
                ).fetchall()
                prev_set = {r["codigo_albaran"] for r in prev}
            else:
                prev_set = set()

            cid, es_nuevo = _upsert_cliente(conn, cli)
            if es_nuevo:
                nuevos += 1
            else:
                actualizados += 1

            for alb in cli["albaranes"]:
                if alb["codigo_albaran"] in prev_set:
                    alb_actualizados += 1
                else:
                    alb_nuevos += 1
                codigos_vistos.add(alb["codigo_albaran"])

        all_alb = conn.execute(
            "SELECT id, codigo_albaran FROM cpc_albaranes WHERE deuda > 0"
        ).fetchall()
        for r in all_alb:
            if r["codigo_albaran"] not in codigos_vistos:
                conn.execute(
                    "UPDATE cpc_albaranes SET deuda = 0, cobrado_linea = total_importe WHERE id = ?",
                    (r["id"],),
                )

        conn.execute("""
            UPDATE cpc_clientes
            SET monto_total = COALESCE((SELECT SUM(total_importe) FROM cpc_albaranes WHERE cpc_cliente_id = cpc_clientes.id), 0),
                monto_cobrado = COALESCE((SELECT SUM(cobrado_linea) FROM cpc_albaranes WHERE cpc_cliente_id = cpc_clientes.id), 0),
                saldo = COALESCE((SELECT SUM(deuda) FROM cpc_albaranes WHERE cpc_cliente_id = cpc_clientes.id), 0)
        """)

        # Cruce con Convenios PRIMERO (para que los convenios no se pisen a pagado)
        cruce = cruce_convenios.cruzar_todos(conn)

        # Clientes con saldo 0 → pagado (excluye convenio e institucional)
        conn.execute("""
            UPDATE cpc_clientes SET estado = 'pagado'
            WHERE saldo <= 0 AND es_institucional = 0
              AND estado NOT IN ('pagado','institucional','convenio','cancelado','disputa')
        """)

        conn.commit()

        conn.execute(
            """INSERT INTO cpc_importaciones
               (archivo, fecha, filas_leidas, clientes_nuevos,
                clientes_actualizados, albaranes_nuevos,
                albaranes_actualizados, omitidos)
               VALUES (?,?,?,?,?,?,?,?)""",
            (archivo.filename, datetime.utcnow().isoformat(timespec="seconds"),
             parsed["filas_leidas"], nuevos, actualizados,
             alb_nuevos, alb_actualizados, parsed["omitidos"]),
        )
        conn.commit()

        return JSONResponse({
            "ok": True,
            "filas_leidas": parsed["filas_leidas"],
            "clientes_nuevos": nuevos,
            "clientes_actualizados": actualizados,
            "albaranes_nuevos": alb_nuevos,
            "albaranes_actualizados": alb_actualizados,
            "omitidos": parsed["omitidos"],
            "convenios_marcados": cruce["marcados"],
            "convenios_desmarcados": cruce["desmarcados"],
            "totales_excel": {
                "total_importe": parsed["total_importe"],
                "total_cobrado": parsed["total_cobrado"],
                "total_deuda": parsed["total_deuda"],
            },
        })
    finally:
        conn.close()


@router.post("/reverificar-convenios")
def reverificar_convenios():
    """Cruza todos los clientes contra convenios y devuelve el resumen."""
    conn = get_conn()
    try:
        resumen = cruce_convenios.cruzar_todos(conn)
        return JSONResponse({"ok": True, **resumen})
    finally:
        conn.close()


@router.post("/{cid}/reverificar-convenio")
def reverificar_convenio(cid: int):
    """Vuelve a cruzar un cliente contra convenios."""
    conn = get_conn()
    try:
        conv = cruce_convenios.cruzar_cliente(conn, cid)
        conn.commit()
        if conv:
            return JSONResponse({
                "ok": True,
                "tiene_convenio": True,
                "folio": conv["folio"],
                "estado_convenio": conv["estado"],
            })
        return JSONResponse({"ok": True, "tiene_convenio": False})
    finally:
        conn.close()


# ---------- Estado ----------

@router.post("/{cid}/estado")
async def cambiar_estado(cid: int, request: Request):
    payload = await request.json()
    nuevo_estado = payload.get("estado", "")
    prioridad = payload.get("prioridad", "")
    proximo = payload.get("proximo_contacto", "")
    notas = payload.get("notas_internas", "")

    conn = get_conn()
    try:
        cli = conn.execute(
            "SELECT es_institucional FROM cpc_clientes WHERE id = ?",
            (cid,),
        ).fetchone()
        if not cli:
            return JSONResponse({"ok": False, "error": "Cliente no encontrado."}, status_code=404)

        if cli["es_institucional"] and nuevo_estado and nuevo_estado != "institucional":
            return JSONResponse(
                {"ok": False, "error": "Este cliente es institucional. Desmárcalo primero para cambiar su estado."},
                status_code=409,
            )

        if nuevo_estado == "institucional":
            return JSONResponse(
                {"ok": False, "error": "Para marcar un cliente como institucional usa el botón 'Marcar como institucional'."},
                status_code=400,
            )

        if nuevo_estado:
            ok, msg = bitacora.puede_cambiar_a(conn, cid, nuevo_estado)
            if not ok:
                return JSONResponse({"ok": False, "error": msg}, status_code=409)
            conn.execute("UPDATE cpc_clientes SET estado = ? WHERE id = ?",
                         (nuevo_estado, cid))
        if prioridad:
            conn.execute("UPDATE cpc_clientes SET prioridad = ? WHERE id = ?",
                         (prioridad, cid))
        if proximo:
            conn.execute("UPDATE cpc_clientes SET proximo_contacto = ? WHERE id = ?",
                         (proximo, cid))
        if notas is not None:
            conn.execute("UPDATE cpc_clientes SET notas_internas = ? WHERE id = ?",
                         (notas, cid))

        if "telefono" in payload:
            conn.execute(
                "UPDATE cpc_clientes SET telefono = ?, telefono_origen = 'manual' WHERE id = ?",
                (payload["telefono"], cid),
            )
        if "email" in payload:
            conn.execute(
                "UPDATE cpc_clientes SET email = ?, email_origen = 'manual' WHERE id = ?",
                (payload["email"], cid),
            )
        if "rfc" in payload:
            conn.execute("UPDATE cpc_clientes SET rfc = ? WHERE id = ?",
                        ((payload["rfc"] or "").strip(), cid))
        conn.execute(
            "UPDATE cpc_clientes SET actualizado_en = ? WHERE id = ?",
            (datetime.utcnow().isoformat(timespec="seconds"), cid),
        )
        conn.commit()
        return JSONResponse({"ok": True})
    finally:
        conn.close()


# ---------- Bitácora ----------

@router.post("/{cid}/bitacora")
async def agregar_bitacora(cid: int, request: Request):
    payload = await request.json()
    conn = get_conn()
    try:
        try:
            bid = bitacora.agregar_entrada(
                conn, cid,
                fecha=payload.get("fecha") or date.today().isoformat(),
                hora=payload.get("hora", ""),
                tipo_contacto=payload.get("tipo_contacto", "llamada"),
                resultado=payload.get("resultado", ""),
                promesa_fecha=payload.get("promesa_fecha", ""),
                promesa_monto=float(payload.get("promesa_monto", 0) or 0),
                observaciones=payload.get("observaciones", ""),
                usuario=payload.get("usuario", ""),
            )
        except ValueError as e:
            raise HTTPException(400, str(e))

        bitacora.actualizar_contacto_cliente(conn, cid)

        sugerencia = None
        if payload.get("resultado") == "pago_realizado":
            sugerencia = "¿Marcar al cliente como pagado? El saldo se actualizará en la próxima importación."

        return JSONResponse({"ok": True, "id": bid, "sugerencia": sugerencia})
    finally:
        conn.close()


@router.post("/{cid}/verificar-qvet")
async def verificar_qvet(cid: int, request: Request):
    payload = await request.json() if request.headers.get("content-type", "").startswith("application/json") else {}
    usuario = payload.get("usuario", "")
    conn = get_conn()
    try:
        bitacora.agregar_entrada(
            conn, cid,
            fecha=date.today().isoformat(),
            hora=datetime.now().strftime("%H:%M"),
            tipo_contacto="otro",
            resultado="verificado_en_qvet",
            observaciones="Cuenta verificada en QVET antes de contactar.",
            usuario=usuario,
        )
        bitacora.actualizar_contacto_cliente(conn, cid)
        return JSONResponse({"ok": True})
    finally:
        conn.close()


# ---------- Limpiar basura ----------

@router.post("/limpiar-basura")
def limpiar_basura():
    """Elimina clientes basura (ID inválido o sin albaranes). No toca clientes con bitácora."""
    conn = get_conn()
    try:
        rows = conn.execute("""
            SELECT c.id, c.idcliente_qvet, c.nombre
            FROM cpc_clientes c
            WHERE (
                c.idcliente_qvet IN ('None', '', 'none', 'NULL', 'null')
                OR c.n_albaranes = 0
            )
            AND NOT EXISTS (
                SELECT 1 FROM cpc_bitacora b
                WHERE b.cpc_cliente_id = c.id
            )
        """).fetchall()

        eliminados = []
        for r in rows:
            conn.execute("DELETE FROM cpc_albaranes WHERE cpc_cliente_id = ?", (r["id"],))
            conn.execute("DELETE FROM cpc_bitacora WHERE cpc_cliente_id = ?", (r["id"],))
            conn.execute("DELETE FROM cpc_clientes WHERE id = ?", (r["id"],))
            eliminados.append({"id": r["id"], "idcliente_qvet": r["idcliente_qvet"], "nombre": r["nombre"]})

        conn.commit()
        return JSONResponse({"ok": True, "eliminados": eliminados, "total": len(eliminados)})
    finally:
        conn.close()


# ---------- Institucional ----------

@router.post("/{cid}/institucional")
async def marcar_institucional(cid: int, request: Request):
    """Marca/desmarca un cliente como institucional."""
    data = await request.json()
    institucional = 1 if data.get("institucional") else 0
    usuario = (data.get("usuario") or "").strip() or "admin"

    conn = get_conn()
    try:
        cli = conn.execute(
            "SELECT es_institucional, nombre, es_convenio FROM cpc_clientes WHERE id = ?",
            (cid,),
        ).fetchone()
        if not cli:
            return JSONResponse(
                {"ok": False, "error": "Cliente no encontrado."},
                status_code=404,
            )

        if institucional:
            conn.execute(
                """UPDATE cpc_clientes
                   SET es_institucional = 1,
                       es_convenio = 0,
                       convenio_folio = '',
                       estado = 'institucional',
                       actualizado_en = ?
                   WHERE id = ?""",
                (datetime.utcnow().isoformat(timespec="seconds"), cid),
            )
            accion = "marcado"
        else:
            conn.execute(
                """UPDATE cpc_clientes
                   SET es_institucional = 0,
                       estado = 'pendiente',
                       actualizado_en = ?
                   WHERE id = ?""",
                (datetime.utcnow().isoformat(timespec="seconds"), cid),
            )
            accion = "desmarcado"

        bitacora.agregar_entrada(
            conn, cid,
            fecha=date.today().isoformat(),
            hora=datetime.now().strftime("%H:%M"),
            tipo_contacto="otro",
            resultado="institucional",
            observaciones=f"Cliente {accion} como institucional por {usuario}.",
            usuario=usuario,
        )
        bitacora.actualizar_contacto_cliente(conn, cid)

        conn.commit()

        if not institucional:
            try:
                cruce_convenios.cruzar_cliente(conn, cid)
                conn.commit()
            except Exception:
                pass

        return JSONResponse({
            "ok": True,
            "es_institucional": institucional,
            "accion": accion,
        })
    finally:
        conn.close()


# ---------- WhatsApp ----------

@router.get("/{cid}/whatsapp")
def whatsapp_cliente(cid: int, plantilla: str = ""):
    """
    Devuelve el mensaje renderizado y la URL de wa.me para un cliente.
    Si no se especifica plantilla, usa la activa del config.
    Para la plantilla 'promesa_seguimiento', busca la última promesa
    de pago vigente en la bitácora del cliente.
    """
    conn = get_conn()
    try:
        cli = conn.execute("SELECT * FROM cpc_clientes WHERE id = ?", (cid,)).fetchone()
        if not cli:
            return JSONResponse(
                {"ok": False, "error": "Cliente no encontrado."},
                status_code=404,
            )
        cliente = _fila_cliente_a_dict(cli)

        if cliente["es_institucional"]:
            return JSONResponse(
                {"ok": False, "error": "Cliente institucional. No aplica cobranza por recepción."},
                status_code=409,
            )
        if cliente["es_convenio"]:
            return JSONResponse(
                {"ok": False, "error": "Cliente con convenio activo. Se gestiona desde Convenios."},
                status_code=409,
            )
        if not (cliente.get("telefono") or "").strip():
            return JSONResponse(
                {"ok": False, "error": "El cliente no tiene teléfono registrado."},
                status_code=400,
            )

        albaranes = [
            dict(a) for a in conn.execute(
                "SELECT * FROM cpc_albaranes WHERE cpc_cliente_id = ? ORDER BY fecha_albaran",
                (cid,),
            ).fetchall()
        ]

        cfg = cpc_config.cargar_config()
        plantillas = cfg.get("plantillas_whatsapp", {})
        clave = plantilla or cfg.get("plantilla_activa", "recordatorio_amable")

        if clave not in plantillas:
            return JSONResponse(
                {"ok": False, "error": f"Plantilla '{clave}' no encontrada."},
                status_code=400,
            )

        # Construir contexto base
        contexto = cpc_whatsapp.construir_contexto(cliente, albaranes)

        # Si la plantilla es de promesa, buscar la promesa vigente
        if clave == "promesa_seguimiento":
            promesa = _buscar_promesa_vigente(conn, cid)
            contexto["promesa_fecha"] = promesa["promesa_fecha"] if promesa else ""
            contexto["promesa_monto"] = (
                f"{float(promesa['promesa_monto']):,.2f}" if promesa and promesa["promesa_monto"] else ""
            )

        # Validar placeholders requeridos
        ok, faltantes = cpc_whatsapp.validar_placeholders(clave, contexto)
        if not ok:
            return JSONResponse(
                {
                    "ok": False,
                    "error": (
                        f"La plantilla '{clave}' requiere los datos: "
                        f"{', '.join(faltantes)}. Captúralos primero "
                        f"(por ejemplo, registrando una promesa de pago en la bitácora)."
                    ),
                    "faltantes": faltantes,
                },
                status_code=400,
            )

        mensaje = cpc_whatsapp.renderizar(plantillas[clave], contexto)
        url = cpc_whatsapp.construir_url(cliente["telefono"], mensaje)

        if not url:
            return JSONResponse(
                {"ok": False, "error": "No se pudo construir la URL (teléfono inválido)."},
                status_code=400,
            )

        return JSONResponse({
            "ok": True,
            "url": url,
            "mensaje": mensaje,
            "telefono": cliente["telefono"],
            "plantilla": clave,
        })
    finally:
        conn.close()


@router.post("/{cid}/whatsapp-enviado")
async def whatsapp_enviado(cid: int, request: Request):
    """
    Registra en bitácora que se envió un mensaje por WhatsApp.
    El resultado queda vacío para que el usuario lo complete después.
    """
    data = await request.json() if request.headers.get("content-type", "").startswith("application/json") else {}
    plantilla = (data.get("plantilla") or "").strip()
    usuario = (data.get("usuario") or "").strip() or "recepción"

    conn = get_conn()
    try:
        bitacora.agregar_entrada(
            conn, cid,
            fecha=date.today().isoformat(),
            hora=datetime.now().strftime("%H:%M"),
            tipo_contacto="whatsapp",
            resultado="",
            observaciones=f"Mensaje de WhatsApp enviado (plantilla: {plantilla or 'activa'}).",
            usuario=usuario,
        )
        bitacora.actualizar_contacto_cliente(conn, cid)
        return JSONResponse({"ok": True})
    finally:
        conn.close()