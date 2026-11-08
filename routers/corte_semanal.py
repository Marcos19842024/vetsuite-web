from datetime import date
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

from pathlib import Path
from shared.db import get_conn
from core.corte_semanal import expr
from core.corte_semanal import semanas
from core.corte_semanal.excel_corte import generar_excel, nombre_archivo
from shared.templates_shared import templates
import json

router = APIRouter(prefix="/corte_semanal", tags=["corte semanal"])

RUTA_CORTES = Path(__file__).resolve().parents[1] / "uploads" / "corte_semanal"

# Columnas capturables (todas menos las calculadas y observaciones)
CAMPOS_CAPTURA = [
    "efectivo_depositado",
    "tarjeta_debito",
    "tarjeta_credito",
    "transferencia",
    "nomina_efectivo",
    "gasolina",
    "hemograma",
    "patologia",
    "varios",
    "servicios",
    "capacitacion",
]

CAMPOS_VALIDOS = set(CAMPOS_CAPTURA) | {"por_cobrar", "observaciones"}
SUCURSALES = ["Baalak", "Prado"]

POR_COBRAR_KEYS = [
    "colaboradores", "clientes_tienda", "clientes_cirugia",
    "clientes_hospitalizacion", "clientes_estetica", "clientes_farmacia",
    "clientes_consulta", "clientes_laboratorio", "clientes_rayos_x",
    "clientes_pension", "tratamiento", "transporte",
]

# Helpers de observaciones generadas
EGRESOS_CAMPOS = {
    "nomina_efectivo", "gasolina", "hemograma", "patologia",
    "varios", "servicios", "capacitacion",
}

def _fmt_monto(v: float) -> str:
    return f"${v:,.2f}"


def _formatear_obs_celda(campo: str, subcampo: str | None,
                         valor_str: str, obs_texto: str) -> str:
    """Genera el texto de observación para una celda editada.
    Formato:
      - Egreso:                      'Gasto de $X: <texto>'
      - Por cobrar / colaboradores:  'Deuda de $X: <texto>'
    Si no hay texto, devuelve '' (no se anexa nada).
    """
    texto = (obs_texto or "").strip()
    if not texto:
        return ""

    monto = expr.evaluar_expr(valor_str or "")
    monto_fmt = _fmt_monto(monto)

    if campo == "por_cobrar" and subcampo == "colaboradores":
        return f"Deuda de {monto_fmt}: {texto}"

    if campo in EGRESOS_CAMPOS:
        return f"Gasto de {monto_fmt}: {texto}"

    return ""


def _regenerar_observaciones(obs_manual: str, obs_celdas: dict,
                             dia: dict) -> str:
    """Combina la observación manual + las generadas por celda."""
    lineas = []
    if (obs_manual or "").strip():
        lineas.append(obs_manual.strip())
    for key, texto in obs_celdas.items():
        if not texto:
            continue
        # key = "campo" o "por_cobrar:colaboradores"
        if ":" in key:
            campo, sub = key.split(":", 1)
        else:
            campo, sub = key, None
        # valor actual de la celda
        if campo == "por_cobrar" and sub:
            valor = (dia.get("por_cobrar") or {}).get(sub, "")
        else:
            valor = dia.get(campo, "")
        generado = _formatear_obs_celda(campo, sub, valor, texto)
        if generado:
            lineas.append(generado)
    return "\n".join(lineas)


def _cargar_obs_celdas(row) -> dict:
    """Lee obs_celdas_json de una fila, tolerante a None/JSON roto."""
    try:
        return json.loads(row["obs_celdas_json"] or "{}")
    except Exception:
        return {}


def _obs_manual_de(obs_celdas: dict) -> str:
    return (obs_celdas.get("__manual__") or "").strip()


def _no_store(payload, status=200):
    return JSONResponse(
        payload,
        status_code=status,
        headers={"Cache-Control": "no-store"},
    )


def _fila_vacia(sucursal: str, fecha: str) -> dict:
    d = {k: "" for k in CAMPOS_CAPTURA}
    d["por_cobrar"] = {k: "" for k in POR_COBRAR_KEYS} # type: ignore
    d["observaciones"] = ""
    d["obs_celdas"] = {} # type: ignore
    d["sucursal"] = sucursal
    d["fecha"] = fecha
    return d


def _cargar_semana(conn, anio: int, semana: int) -> dict:
    """Devuelve {'meta': {...}, 'dias': [...], 'datos': {sucursal: {fecha: {...}}}}"""
    meta = semanas.asegurar_semana(conn, anio, semana)
    dias = semanas.dias_de(anio, semana)

    datos = {s: {f: _fila_vacia(s, f) for f in dias} for s in SUCURSALES}

    filas = conn.execute(
        "SELECT * FROM cortes_diarios WHERE fecha BETWEEN ? AND ?",
        (dias[0], dias[6]),
    ).fetchall()
    for row in filas:
        r = dict(row)
        s = r["sucursal"]
        if s not in datos:
            continue
        f = r["fecha"]
        if f not in datos[s]:
            continue
        for k in CAMPOS_CAPTURA:
            datos[s][f][k] = r.get(k) or ""
        datos[s][f]["observaciones"] = r.get("observaciones") or ""
        datos[s][f]["obs_celdas"] = _cargar_obs_celdas(r)
        try:
            import json as _json
            datos[s][f]["por_cobrar"] = _json.loads(r.get("por_cobrar_json") or "{}")
        except Exception:
            datos[s][f]["por_cobrar"] = {k: "" for k in POR_COBRAR_KEYS}
        # rellenar claves faltantes
        for k in POR_COBRAR_KEYS:
            datos[s][f]["por_cobrar"].setdefault(k, "")

    return {"meta": meta, "dias": dias, "datos": datos}


def _calcular_totales(meta: dict, dias: list[str], datos: dict) -> dict:
    """Totales por día/sucursal, por concepto y globales."""
    totales = {
        "por_sucursal": {},
        "por_dia": {},         # {fecha: {ingreso, egreso, por_cobrar}}
        "por_concepto": {},    # {campo: {Baalak, Prado, total}}
        "global": {"ingreso": 0.0, "egreso": 0.0, "por_cobrar": 0.0, "utilidad": 0.0},
    }

    for s in SUCURSALES:
        tot_s = {
            "ingreso": 0.0, "egreso": 0.0, "por_cobrar": 0.0, "utilidad": 0.0,
            "conceptos": {k: 0.0 for k in CAMPOS_CAPTURA + POR_COBRAR_KEYS},
        }
        for f in dias:
            d = datos[s][f]

            dep = expr.evaluar_expr(d.get("efectivo_depositado"))
            td = expr.evaluar_expr(d.get("tarjeta_debito"))
            tc = expr.evaluar_expr(d.get("tarjeta_credito"))
            tr = expr.evaluar_expr(d.get("transferencia"))

            egr = sum(expr.evaluar_expr(d.get(k)) for k in [
                "nomina_efectivo", "gasolina", "hemograma", "patologia",
                "varios", "servicios", "capacitacion",
            ])
            # Efectivo cobrado = depositado + egresos (como =C5+C21)
            cob = round(dep + egr, 2)

            # Por cobrar
            pc_dia = sum(expr.evaluar_expr(v) for v in d.get("por_cobrar", {}).values())

            ingreso_dia = round(cob + td + tc + tr, 2)

            tot_s["ingreso"] += ingreso_dia
            tot_s["egreso"] += egr
            tot_s["por_cobrar"] += pc_dia

            tot_s["conceptos"]["efectivo_depositado"] += dep
            tot_s["conceptos"]["efectivo_cobrado"] = (
                tot_s["conceptos"].get("efectivo_cobrado", 0.0) + cob
            )
            tot_s["conceptos"]["tarjeta_debito"] += td
            tot_s["conceptos"]["tarjeta_credito"] += tc
            tot_s["conceptos"]["transferencia"] += tr
            for k in ["nomina_efectivo", "gasolina", "hemograma", "patologia",
                      "varios", "servicios", "capacitacion"]:
                tot_s["conceptos"][k] += expr.evaluar_expr(d.get(k))
            for k in POR_COBRAR_KEYS:
                tot_s["conceptos"][k] += expr.evaluar_expr(d["por_cobrar"].get(k))

            if f not in totales["por_dia"]:
                totales["por_dia"][f] = {"ingreso": 0.0, "egreso": 0.0, "por_cobrar": 0.0}
            totales["por_dia"][f]["ingreso"] += ingreso_dia
            totales["por_dia"][f]["egreso"] += egr
            totales["por_dia"][f]["por_cobrar"] += pc_dia

        tot_s["utilidad"] = round(tot_s["ingreso"] - tot_s["egreso"], 2)
        totales["por_sucursal"][s] = tot_s
        totales["global"]["ingreso"] += tot_s["ingreso"]
        totales["global"]["egreso"] += tot_s["egreso"]
        totales["global"]["por_cobrar"] += tot_s["por_cobrar"]

    totales["global"]["utilidad"] = round(
        totales["global"]["ingreso"] - totales["global"]["egreso"], 2
    )
    return totales


# ------------------------- RUTAS -------------------------

@router.get("", response_class=HTMLResponse)
def home(request: Request, anio: int | None = None, semana: int | None = None):
    if anio is None or semana is None:
        anio, semana = semanas.semana_actual()

    conn = get_conn()
    try:
        data = _cargar_semana(conn, anio, semana)
    finally:
        conn.close()

    return templates.TemplateResponse(
        "corte_semanal.html",
        {
            "request": request,
            "anio": anio,
            "semana": semana,
            "dias": data["dias"],
            "meta": data["meta"],
            "rango_legible": semanas.rango_legible(anio, semana),
            "sucursales": SUCURSALES,
            "por_cobrar_keys": POR_COBRAR_KEYS,
            "campos_captura": CAMPOS_CAPTURA,
        },
    )


@router.get("/datos")
def datos(anio: int, semana: int):
    conn = get_conn()
    try:
        data = _cargar_semana(conn, anio, semana)
    finally:
        conn.close()

    totales = _calcular_totales(data["meta"], data["dias"], data["datos"])

    # Enriquecer datos con "valor_fmt" y "total_fmt" por celda
    out_datos = {}
    for s in SUCURSALES:
        out_datos[s] = {}
        for f in data["dias"]:
            d = data["datos"][s][f]
            row = dict(d)
            row["obs_celdas"] = d.get("obs_celdas", {})   # ===== NUEVO =====
            row["_totales"] = {}
            for k in CAMPOS_CAPTURA:
                row["_totales"][k] = expr.fmt_monto(expr.evaluar_expr(d.get(k)))
            # efectivo_cobrado calculado
            dep = expr.evaluar_expr(d.get("efectivo_depositado"))
            egr = sum(expr.evaluar_expr(d.get(k)) for k in [
                "nomina_efectivo", "gasolina", "hemograma", "patologia",
                "varios", "servicios", "capacitacion",
            ])
            row["_totales"]["efectivo_cobrado"] = expr.fmt_monto(dep + egr)
            for k in POR_COBRAR_KEYS:
                row["_totales"][k] = expr.fmt_monto(
                    expr.evaluar_expr(d["por_cobrar"].get(k))
                )
            out_datos[s][f] = row

    return _no_store({
        "meta": data["meta"],
        "dias": data["dias"],
        "datos": out_datos,
        "totales": totales,
    })


@router.post("/actualizar")
async def actualizar(request: Request):
    body = await request.json()
    fecha = body.get("fecha")
    sucursal = body.get("sucursal")
    campo = body.get("campo")
    valor = body.get("valor", "")
    subcampo = body.get("subcampo")
    obs_texto = (body.get("obs") or "").strip()

    if sucursal not in SUCURSALES:
        raise HTTPException(400, "sucursal inválida")
    if campo not in CAMPOS_VALIDOS:
        raise HTTPException(400, "campo inválido")
    if not fecha:
        raise HTTPException(400, "fecha requerida")

    try:
        date.fromisoformat(fecha)
    except ValueError:
        raise HTTPException(400, "fecha inválida")

    f = date.fromisoformat(fecha)
    anio, semana = semanas.semana_de_fecha(f)

    conn = get_conn()
    try:
        meta = semanas.asegurar_semana(conn, anio, semana)
        if meta["estado"] == "cerrada":
            raise HTTPException(409, "semana cerrada")

        conn.execute(
            "INSERT OR IGNORE INTO cortes_diarios (fecha, sucursal) VALUES (?, ?)",
            (fecha, sucursal),
        )
        row = conn.execute(
            "SELECT * FROM cortes_diarios WHERE fecha=? AND sucursal=?",
            (fecha, sucursal),
        ).fetchone()
        obs_celdas = _cargar_obs_celdas(row)      # ===== NUEVO =====

        # ---------- Caso 1: observación manual del día ----------
        if campo == "observaciones":
            obs_celdas["__manual__"] = str(valor or "")
            # Necesitamos el día completo para regenerar (con los valores actuales)
            dia_tmp = _fila_vacia(sucursal, fecha)
            for k in CAMPOS_CAPTURA:
                dia_tmp[k] = row[k] or ""
            try:
                dia_tmp["por_cobrar"] = json.loads(row["por_cobrar_json"] or "{}")
            except Exception:
                dia_tmp["por_cobrar"] = {}
            nuevas_obs = _regenerar_observaciones(
                _obs_manual_de(obs_celdas), obs_celdas, dia_tmp
            )
            conn.execute(
                "UPDATE cortes_diarios SET obs_celdas_json=?, observaciones=?, "
                "actualizado_en=CURRENT_TIMESTAMP WHERE fecha=? AND sucursal=?",
                (json.dumps(obs_celdas, ensure_ascii=False), nuevas_obs,
                 fecha, sucursal),
            )
            conn.commit()
            return _respuesta_actualizar(conn, anio, semana, campo, valor)

        # ---------- Caso 2: por_cobrar ----------
        if campo == "por_cobrar":
            if subcampo not in POR_COBRAR_KEYS:
                raise HTTPException(400, "subcampo inválido")
            try:
                pc = json.loads(row["por_cobrar_json"] or "{}")
            except Exception:
                pc = {}
            pc[subcampo] = str(valor)
            conn.execute(
                "UPDATE cortes_diarios SET por_cobrar_json=?, "
                "actualizado_en=CURRENT_TIMESTAMP WHERE fecha=? AND sucursal=?",
                (json.dumps(pc, ensure_ascii=False), fecha, sucursal),
            )

        # ---------- Caso 3: campo normal de captura ----------
        else:
            conn.execute(
                f"UPDATE cortes_diarios SET {campo}=?, "
                f"actualizado_en=CURRENT_TIMESTAMP WHERE fecha=? AND sucursal=?",
                (str(valor), fecha, sucursal),
            )

        # ---------- NUEVO: persistir obs de la celda (si aplica) ----------
        aplica_obs = (campo in EGRESOS_CAMPOS) or \
                     (campo == "por_cobrar" and subcampo == "colaboradores")
        if aplica_obs:
            key = f"{campo}:{subcampo}" if subcampo else campo
            if obs_texto:
                obs_celdas[key] = obs_texto
            else:
                obs_celdas.pop(key, None)

        # Regenerar observaciones del día con los valores YA actualizados
        # Releer la fila para tener los valores frescos
        row2 = conn.execute(
            "SELECT * FROM cortes_diarios WHERE fecha=? AND sucursal=?",
            (fecha, sucursal),
        ).fetchone()
        dia_actual = _fila_vacia(sucursal, fecha)
        for k in CAMPOS_CAPTURA:
            dia_actual[k] = row2[k] or ""
        try:
            dia_actual["por_cobrar"] = json.loads(row2["por_cobrar_json"] or "{}")
        except Exception:
            dia_actual["por_cobrar"] = {}

        nuevas_obs = _regenerar_observaciones(
            _obs_manual_de(obs_celdas), obs_celdas, dia_actual
        )
        conn.execute(
            "UPDATE cortes_diarios SET obs_celdas_json=?, observaciones=?, "
            "actualizado_en=CURRENT_TIMESTAMP WHERE fecha=? AND sucursal=?",
            (json.dumps(obs_celdas, ensure_ascii=False), nuevas_obs,
             fecha, sucursal),
        )
        conn.commit()

        return _respuesta_actualizar(conn, anio, semana, campo, valor)

    finally:
        conn.close()


def _respuesta_actualizar(conn, anio: int, semana: int, campo: str, valor: str):
    """Construye la respuesta de /actualizar (mismo formato que antes)."""
    data = _cargar_semana(conn, anio, semana)
    totales = _calcular_totales(data["meta"], data["dias"], data["datos"])

    out_datos = {}
    for s in SUCURSALES:
        out_datos[s] = {}
        for f in data["dias"]:
            d = data["datos"][s][f]
            row = dict(d)
            row["obs_celdas"] = d.get("obs_celdas", {})   # ===== NUEVO =====
            row["_totales"] = {}
            for k in CAMPOS_CAPTURA:
                row["_totales"][k] = expr.fmt_monto(expr.evaluar_expr(d.get(k)))
            dep = expr.evaluar_expr(d.get("efectivo_depositado"))
            egr = sum(expr.evaluar_expr(d.get(k)) for k in [
                "nomina_efectivo", "gasolina", "hemograma", "patologia",
                "varios", "servicios", "capacitacion",
            ])
            row["_totales"]["efectivo_cobrado"] = expr.fmt_monto(dep + egr)
            for k in POR_COBRAR_KEYS:
                row["_totales"][k] = expr.fmt_monto(
                    expr.evaluar_expr(d["por_cobrar"].get(k))
                )
            out_datos[s][f] = row

    if campo in CAMPOS_CAPTURA or campo == "por_cobrar":
        total_celda = expr.fmt_monto(expr.evaluar_expr(valor))
    else:
        total_celda = ""

    return _no_store({
        "ok": True,
        "total_celda": total_celda,
        "totales": totales,
        "datos": out_datos,
        "dias": data["dias"],
    })


@router.get("/excel")
def excel(anio: int, semana: int):
    """
    Genera el Excel del Corte Semanal usando la plantilla original.

    - Si la semana está CERRADA y ya existe el archivo guardado → lo sirve tal cual.
    - Si está ABIERTA (o no hay archivo) → lo genera al vuelo.
    """
    conn = get_conn()
    try:
        meta = semanas.asegurar_semana(conn, anio, semana)

        # Semana cerrada → servir el archivo guardado (si existe)
        if meta.get("estado") == "cerrada" and meta.get("excel_path"):
            p = Path(meta["excel_path"])
            if p.exists():
                return StreamingResponse(
                    open(p, "rb"),
                    media_type=(
                        "application/vnd.openxmlformats-officedocument"
                        ".spreadsheetml.sheet"
                    ),
                    headers={
                        "Content-Disposition": f'attachment; filename="{p.name}"',
                        "Cache-Control": "no-store",
                    },
                )

        # Semana abierta (o cerrada sin archivo) → generar al vuelo
        data = _cargar_semana(conn, anio, semana)
    finally:
        conn.close()

    try:
        buf = generar_excel(
            anio=anio,
            semana=semana,
            dias=data["dias"],
            datos=data["datos"],
        )
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )

    nombre = nombre_archivo(data["dias"])
    return StreamingResponse(
        buf,
        media_type=(
            "application/vnd.openxmlformats-officedocument"
            ".spreadsheetml.sheet"
        ),
        headers={
            "Content-Disposition": f'attachment; filename="{nombre}"',
            "Cache-Control": "no-store",
        },
    )


@router.post("/cerrar")
async def cerrar(request: Request):
    """
    Genera el Excel, lo guarda en uploads/corte_semanal/<año>-W<semana> - Semanal...xlsx
    y marca la semana como cerrada.
    """
    body = await request.json()
    anio = int(body.get("anio"))
    semana = int(body.get("semana"))

    conn = get_conn()
    try:
        meta = semanas.asegurar_semana(conn, anio, semana)
        if meta["estado"] == "cerrada":
            raise HTTPException(409, "La semana ya está cerrada")

        # Validar que haya al menos un día con datos en alguna sucursal
        data = _cargar_semana(conn, anio, semana)
        hay_datos = any(
            any(v for k, v in fila.items() if k in CAMPOS_CAPTURA)
            or any((fila.get("por_cobrar") or {}).values())
            or fila.get("observaciones")
            for suc in SUCURSALES
            for fila in data["datos"][suc].values()
        )
        if not hay_datos:
            raise HTTPException(400, "La semana no tiene datos capturados")

        # Generar Excel
        from core.corte_semanal.excel_corte import generar_excel, nombre_archivo
        try:
            buf = generar_excel(
                anio=anio,
                semana=semana,
                dias=data["dias"],
                datos=data["datos"],
            )
        except FileNotFoundError as e:
            raise HTTPException(500, str(e))

        # Guardar archivo
        RUTA_CORTES.mkdir(parents=True, exist_ok=True)
        nombre_base = nombre_archivo(data["dias"])   # "Semanal Baalak-Prado Octubre.xlsx"
        nombre_final = f"{anio}-W{semana:02d} - {nombre_base}"
        ruta_final = RUTA_CORTES / nombre_final
        with open(ruta_final, "wb") as fh:
            fh.write(buf.getvalue())

        # Actualizar estado
        conn.execute(
            "UPDATE cortes_semanas SET estado='cerrada', excel_path=?, cerrado_en=CURRENT_TIMESTAMP "
            "WHERE anio=? AND semana=?",
            (str(ruta_final), anio, semana),
        )
        conn.execute(
            "UPDATE cortes_diarios SET actualizado_en=CURRENT_TIMESTAMP "
            "WHERE fecha BETWEEN ? AND ?",
            (data["dias"][0], data["dias"][6]),
        )
        conn.commit()

        return _no_store({
            "ok": True,
            "estado": "cerrada",
            "archivo": nombre_final,
            "ruta": str(ruta_final),
        })
    finally:
        conn.close()


@router.post("/reabrir")
async def reabrir(request: Request):
    """
    Reabre una semana cerrada. Borra el Excel guardado.
    """
    body = await request.json()
    anio = int(body.get("anio"))
    semana = int(body.get("semana"))

    conn = get_conn()
    try:
        meta = semanas.asegurar_semana(conn, anio, semana)
        if meta["estado"] != "cerrada":
            raise HTTPException(400, "La semana no está cerrada")

        # Borrar archivo guardado si existe
        ruta = meta.get("excel_path")
        if ruta:
            p = Path(ruta)
            try:
                if p.exists():
                    p.unlink()
            except Exception as e:
                # No es crítico: si falla, igual reabrimos
                print(f"[corte] no se pudo borrar {p}: {e}")

        # Actualizar estado
        conn.execute(
            "UPDATE cortes_semanas SET estado='abierta', excel_path=NULL, cerrado_en=NULL "
            "WHERE anio=? AND semana=?",
            (anio, semana),
        )
        conn.commit()

        return _no_store({"ok": True, "estado": "abierta"})
    finally:
        conn.close()


@router.get("/arbol")
def arbol():
    """Árbol Año → Semana → Sucursal con totales de ingresos y egresos."""
    with get_conn() as conn:
        filas = conn.execute("""
            SELECT
                fecha,
                sucursal,
                efectivo_depositado, efectivo_cobrado,
                tarjeta_debito, tarjeta_credito, transferencia,
                nomina_efectivo, gasolina, hemograma, patologia,
                varios, servicios, capacitacion
            FROM cortes_diarios
            WHERE fecha IS NOT NULL AND fecha != ''
        """).fetchall()

    # Agrupar por (anio ISO, semana ISO, sucursal)
    arbol = {}
    for r in filas:
        try:
            y, m, d = map(int, r["fecha"].split("-"))
        except (ValueError, AttributeError):
            continue
        anio_iso, sem_iso = semanas.semana_de_fecha(date(y, m, d))

        # Evaluar cada campo (puede venir como "2345+679")
        def _eval(txt):
            if not txt:
                return 0.0
            s = str(txt).replace("$", "").replace(",", ".").replace(" ", "")
            total = 0.0
            signo = 1
            num = ""
            for c in s:
                if c == "+":
                    if num:
                        total += signo * float(num)
                    num = ""
                    signo = 1
                elif c == "-":
                    if num:
                        total += signo * float(num)
                    num = ""
                    signo = -1
                elif c.isdigit() or c == ".":
                    num += c
                else:
                    if num:
                        total += signo * float(num)
                    num = ""
                    signo = 1
            if num:
                total += signo * float(num)
            return total

        ingreso = (
            _eval(r["efectivo_depositado"]) + _eval(r["efectivo_cobrado"])
            + _eval(r["tarjeta_debito"]) + _eval(r["tarjeta_credito"])
            + _eval(r["transferencia"])
        )
        egreso = (
            _eval(r["nomina_efectivo"]) + _eval(r["gasolina"])
            + _eval(r["hemograma"]) + _eval(r["patologia"])
            + _eval(r["varios"]) + _eval(r["servicios"])
            + _eval(r["capacitacion"])
        )

        a = f"{anio_iso:04d}"
        s = f"{sem_iso:02d}"
        suc = r["sucursal"] or "Sin sucursal"

        arbol.setdefault(a, {}).setdefault(s, {}).setdefault(suc, {
            "n": 0, "ingreso": 0.0, "egreso": 0.0, "utilidad": 0.0
        })
        arbol[a][s][suc]["n"] += 1
        arbol[a][s][suc]["ingreso"] = round(arbol[a][s][suc]["ingreso"] + ingreso, 2)
        arbol[a][s][suc]["egreso"] = round(arbol[a][s][suc]["egreso"] + egreso, 2)
        arbol[a][s][suc]["utilidad"] = round(
            arbol[a][s][suc]["ingreso"] - arbol[a][s][suc]["egreso"], 2
        )

        # _total de la sucursal (ya está)
        # _total de la semana
        arbol[a][s].setdefault("_total", {"n": 0, "ingreso": 0.0, "egreso": 0.0, "utilidad": 0.0})
        arbol[a][s]["_total"]["n"] += 1
        arbol[a][s]["_total"]["ingreso"] = round(arbol[a][s]["_total"]["ingreso"] + ingreso, 2)
        arbol[a][s]["_total"]["egreso"] = round(arbol[a][s]["_total"]["egreso"] + egreso, 2)
        arbol[a][s]["_total"]["utilidad"] = round(
            arbol[a][s]["_total"]["ingreso"] - arbol[a][s]["_total"]["egreso"], 2
        )

        # _total del año
        arbol[a].setdefault("_total", {"n": 0, "ingreso": 0.0, "egreso": 0.0, "utilidad": 0.0})
        arbol[a]["_total"]["n"] += 1
        arbol[a]["_total"]["ingreso"] = round(arbol[a]["_total"]["ingreso"] + ingreso, 2)
        arbol[a]["_total"]["egreso"] = round(arbol[a]["_total"]["egreso"] + egreso, 2)
        arbol[a]["_total"]["utilidad"] = round(
            arbol[a]["_total"]["ingreso"] - arbol[a]["_total"]["egreso"], 2
        )

    # _total raíz
    arbol["_total"] = {
        "n": sum(v["_total"]["n"] for k, v in arbol.items() if k != "_total"),
        "ingreso": round(sum(v["_total"]["ingreso"] for k, v in arbol.items() if k != "_total"), 2),
        "egreso": round(sum(v["_total"]["egreso"] for k, v in arbol.items() if k != "_total"), 2),
        "utilidad": round(sum(v["_total"]["utilidad"] for k, v in arbol.items() if k != "_total"), 2),
    }

    resp = JSONResponse(arbol)
    resp.headers["Cache-Control"] = "no-store"
    return resp