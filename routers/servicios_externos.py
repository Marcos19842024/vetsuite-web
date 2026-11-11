from datetime import date

from fastapi import APIRouter, Request, Form
from fastapi.responses import JSONResponse

from shared.templates_shared import templates
from shared.db import get_conn
from core.servicios_externos import config as cfg_mod
from core.servicios_externos.semanas import asegurar_semana, semana_actual
from core.corte_semanal.semanas import semana_de_fecha

router = APIRouter(prefix="/servicios_externos", tags=["servicios externos"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _semana_de_fecha(conn, fecha_iso: str) -> dict:
    """Devuelve la fila de servicios_semanas para la semana ISO de `fecha_iso`."""
    y, m, d = map(int, fecha_iso.split("-"))
    anio, semana = semana_de_fecha(date(y, m, d))
    return asegurar_semana(conn, anio, semana)


def _conflicto(msg: str) -> JSONResponse:
    return JSONResponse({"ok": False, "error": msg}, status_code=409)


# ---------------------------------------------------------------------------
# Página
# ---------------------------------------------------------------------------
@router.get("")
def pagina(request: Request):
    cfg = cfg_mod.cargar()
    return templates.TemplateResponse(
        "servicios_externos.html",
        {"request": request, "cfg": cfg},
    )


# ---------------------------------------------------------------------------
# Datos (filtrado por semana ISO)
# ---------------------------------------------------------------------------
@router.get("/datos")
def datos(anio: int | None = None, semana: int | None = None):
    if not anio or not semana:
        anio, semana = semana_actual()

    with get_conn() as conn:
        sem = asegurar_semana(conn, anio, semana)

        filas = [dict(r) for r in conn.execute("""
            SELECT * FROM servicios_externos
            WHERE fecha BETWEEN ? AND ?
            ORDER BY fecha ASC, id ASC
        """, (sem["desde"], sem["hasta"])).fetchall()]

        if sem["estado"] == "cerrada" and sem["cerrado_en"]:
            totales = {
                "pendiente": round(sem["total_pendiente"], 2),
                "pagado": round(sem["total_pagado"], 2),
                "total": round(sem["total_pagado"] + sem["total_pendiente"], 2),
                "n": sem["n_registros"],
            }
        else:
            pendiente = sum(
                f["total"] for f in filas if not (f["fecha_pago"] or "").strip()
            )
            pagado = sum(
                f["total"] for f in filas if (f["fecha_pago"] or "").strip()
            )
            totales = {
                "pendiente": round(pendiente, 2),
                "pagado": round(pagado, 2),
                "total": round(pendiente + pagado, 2),
                "n": len(filas),
            }

    resp = JSONResponse({
        "filas": filas,
        "totales": totales,
        "semana": {
            "anio": anio,
            "semana": semana,
            "desde": sem["desde"],
            "hasta": sem["hasta"],
            "estado": sem["estado"],
            "rango_legible": f"{sem['desde']} al {sem['hasta']}",
            "cerrado_en": sem["cerrado_en"],
        },
    })
    resp.headers["Cache-Control"] = "no-store"
    return resp


# ---------------------------------------------------------------------------
# Actualizar (crear / editar)
# ---------------------------------------------------------------------------
@router.post("/actualizar")
def actualizar(
    id: int = Form(0),
    concepto: str = Form(...),
    fecha: str = Form(...),
    cliente: str = Form(...),
    mascota: str = Form(""),
    recuperacion: str = Form(""),
    fecha_entrega: str = Form(""),
    total: float = Form(0),
    fecha_pago: str = Form(""),
    tipo_pago: str = Form(""),
    notas: str = Form(""),
):
    fecha_pago = (fecha_pago or "").strip()
    if not fecha_pago:
        tipo_pago = ""

    with get_conn() as conn:
        sem = _semana_de_fecha(conn, fecha)
        if sem["estado"] == "cerrada":
            return _conflicto(
                f"La semana {sem['anio']}-W{sem['semana']} está cerrada. "
                f"Reábrela para editar."
            )

        if id:
            # Verificar también que la semana del registro original no esté cerrada
            original = conn.execute(
                "SELECT fecha FROM servicios_externos WHERE id=?", (id,)
            ).fetchone()
            if original:
                sem_orig = _semana_de_fecha(conn, original["fecha"])
                if sem_orig["estado"] == "cerrada":
                    return _conflicto(
                        f"El registro pertenece a la semana "
                        f"{sem_orig['anio']}-W{sem_orig['semana']} (cerrada)."
                    )
            conn.execute("""
                UPDATE servicios_externos
                SET concepto=?, fecha=?, cliente=?, mascota=?,
                    recuperacion=?, fecha_entrega=?, total=?,
                    fecha_pago=?, tipo_pago=?, notas=?,
                    actualizado_en=CURRENT_TIMESTAMP
                WHERE id=?
            """, (concepto, fecha, cliente, mascota, recuperacion,
                  fecha_entrega, total, fecha_pago, tipo_pago, notas, id))
        else:
            cur = conn.execute("""
                INSERT INTO servicios_externos
                    (concepto, fecha, cliente, mascota, recuperacion,
                     fecha_entrega, total, fecha_pago, tipo_pago, notas)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (concepto, fecha, cliente, mascota, recuperacion,
                  fecha_entrega, total, fecha_pago, tipo_pago, notas))
            id = cur.lastrowid  # type: ignore
        conn.commit()

    return {"ok": True, "id": id}


# ---------------------------------------------------------------------------
# Marcar pagado
# ---------------------------------------------------------------------------
@router.post("/marcar-pagado")
def marcar_pagado(
    id: int = Form(...),
    fecha_pago: str = Form(...),
    tipo_pago: str = Form(...),
):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT fecha FROM servicios_externos WHERE id=?", (id,)
        ).fetchone()
        if not row:
            return JSONResponse(
                {"ok": False, "error": "Registro no encontrado"},
                status_code=404,
            )
        sem = _semana_de_fecha(conn, row["fecha"])
        if sem["estado"] == "cerrada":
            return _conflicto(
                f"La semana {sem['anio']}-W{sem['semana']} está cerrada."
            )
        conn.execute("""
            UPDATE servicios_externos
            SET fecha_pago=?, tipo_pago=?, actualizado_en=CURRENT_TIMESTAMP
            WHERE id=?
        """, (fecha_pago, tipo_pago, id))
        conn.commit()
    return {"ok": True}


# ---------------------------------------------------------------------------
# Eliminar
# ---------------------------------------------------------------------------
@router.post("/eliminar")
def eliminar(id: int = Form(...)):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT fecha FROM servicios_externos WHERE id=?", (id,)
        ).fetchone()
        if not row:
            return JSONResponse(
                {"ok": False, "error": "Registro no encontrado"},
                status_code=404,
            )
        sem = _semana_de_fecha(conn, row["fecha"])
        if sem["estado"] == "cerrada":
            return _conflicto(
                f"La semana {sem['anio']}-W{sem['semana']} está cerrada."
            )
        conn.execute("DELETE FROM servicios_externos WHERE id=?", (id,))
        conn.commit()
    return {"ok": True}


# ---------------------------------------------------------------------------
# Cerrar / reabrir semana
# ---------------------------------------------------------------------------
@router.post("/cerrar")
def cerrar(anio: int = Form(...), semana: int = Form(...)):
    with get_conn() as conn:
        sem = asegurar_semana(conn, anio, semana)
        if sem["estado"] == "cerrada":
            return _conflicto("La semana ya está cerrada")

        filas = conn.execute("""
            SELECT total, fecha_pago FROM servicios_externos
            WHERE fecha BETWEEN ? AND ?
        """, (sem["desde"], sem["hasta"])).fetchall()
        pendiente = sum(
            f["total"] for f in filas if not (f["fecha_pago"] or "").strip()
        )
        pagado = sum(
            f["total"] for f in filas if (f["fecha_pago"] or "").strip()
        )
        conn.execute("""
            UPDATE servicios_semanas
            SET estado='cerrada',
                cerrado_en=CURRENT_TIMESTAMP,
                total_pendiente=?, total_pagado=?, n_registros=?
            WHERE anio=? AND semana=?
        """, (round(pendiente, 2), round(pagado, 2), len(filas), anio, semana))
        conn.commit()

    return {
        "ok": True,
        "totales": {
            "pendiente": round(pendiente, 2),
            "pagado": round(pagado, 2),
            "total": round(pendiente + pagado, 2),
            "n": len(filas),
        },
    }


@router.post("/reabrir")
def reabrir(anio: int = Form(...), semana: int = Form(...)):
    with get_conn() as conn:
        asegurar_semana(conn, anio, semana)
        conn.execute("""
            UPDATE servicios_semanas
            SET estado='abierta',
                cerrado_en=NULL,
                total_pendiente=0, total_pagado=0, n_registros=0
            WHERE anio=? AND semana=?
        """, (anio, semana))
        conn.commit()
    return {"ok": True}


# ---------------------------------------------------------------------------
# Listado de semanas (para el selector)
# ---------------------------------------------------------------------------
@router.get("/semanas")
def listar_semanas(anio: int | None = None):
    if not anio:
        anio = date.today().year
    with get_conn() as conn:
        filas = [dict(r) for r in conn.execute("""
            SELECT anio, semana, desde, hasta, estado, cerrado_en
            FROM servicios_semanas
            WHERE anio=?
            ORDER BY semana ASC
        """, (anio,)).fetchall()]
    resp = JSONResponse({"anio": anio, "semanas": filas})
    resp.headers["Cache-Control"] = "no-store"
    return resp


@router.get("/arbol")
def arbol():
    """Árbol Año → Mes → Semana ISO → Concepto → Estado.

    La semana se calcula en Python con `semana_de_fecha` (ISO 8601), NO con
    `strftime('%W')` de SQLite, porque esa directiva no es ISO y desfasa
    una semana respecto al resto del módulo.
    """
    with get_conn() as conn:
        filas = conn.execute("""
            SELECT
                fecha,
                concepto,
                CASE WHEN TRIM(COALESCE(fecha_pago,'')) = '' THEN 'pendiente' ELSE 'pagado' END AS estado,
                COUNT(*) AS n,
                SUM(total) AS total
            FROM servicios_externos
            WHERE fecha IS NOT NULL AND fecha != ''
            GROUP BY fecha, concepto, estado
            ORDER BY fecha ASC, concepto ASC, estado ASC
        """).fetchall()

    arbol = {}
    for r in filas:
        try:
            y, m, d = map(int, r["fecha"].split("-"))
        except (ValueError, AttributeError):
            continue
        anio_iso, sem_iso = semana_de_fecha(date(y, m, d))

        a = f"{anio_iso:04d}"
        m = f"{m:02d}"
        s = f"{sem_iso:02d}"
        c = r["concepto"] or "Sin concepto"
        est = r["estado"]
        n = r["n"]
        t = round(r["total"] or 0, 2)

        # Nivel estado
        arbol.setdefault(a, {}) \
             .setdefault(m, {}) \
             .setdefault(s, {}) \
             .setdefault(c, {}) \
             .setdefault(est, {"n": 0, "total": 0.0})
        arbol[a][m][s][c][est]["n"] += n
        arbol[a][m][s][c][est]["total"] = round(
            arbol[a][m][s][c][est]["total"] + t, 2)

        # _total del concepto
        arbol[a][m][s][c].setdefault("_total", {"n": 0, "total": 0.0})
        arbol[a][m][s][c]["_total"]["n"] += n
        arbol[a][m][s][c]["_total"]["total"] = round(
            arbol[a][m][s][c]["_total"]["total"] + t, 2)

        # _total de la semana
        arbol[a][m][s].setdefault("_total", {"n": 0, "total": 0.0})
        arbol[a][m][s]["_total"]["n"] += n
        arbol[a][m][s]["_total"]["total"] = round(
            arbol[a][m][s]["_total"]["total"] + t, 2)

        # _total del mes
        arbol[a][m].setdefault("_total", {"n": 0, "total": 0.0})
        arbol[a][m]["_total"]["n"] += n
        arbol[a][m]["_total"]["total"] = round(
            arbol[a][m]["_total"]["total"] + t, 2)

        # _total del año
        arbol[a].setdefault("_total", {"n": 0, "total": 0.0})
        arbol[a]["_total"]["n"] += n
        arbol[a]["_total"]["total"] = round(
            arbol[a]["_total"]["total"] + t, 2)

    # _total raíz
    arbol["_total"] = {
        "n": sum(v["_total"]["n"] for k, v in arbol.items() if k != "_total"),
        "total": round(sum(v["_total"]["total"] for k, v in arbol.items() if k != "_total"), 2),
    }

    resp = JSONResponse(arbol)
    resp.headers["Cache-Control"] = "no-store"
    return resp


# ---------------------------------------------------------------------------
# Configuración (conceptos)
# ---------------------------------------------------------------------------
@router.get("/config")
def get_config():
    return cfg_mod.cargar()


@router.post("/config/concepto")
def add_concepto(valor: str = Form(...)):
    return cfg_mod.agregar_concepto(valor)