# routers/recordatorios.py
"""
Módulo de Recordatorios — versión web.

Flujo:
  1. Importar Excel (citas o vacunas) → cache JSON.
  2. Ver tabla con tabs Citas / Vacunas.
  3. Enviar por WhatsApp (wa.me) → copiar mensaje + abrir chat → confirmar.
  4. Marcar / desmarcar enviado (historial persistente).
  5. Exportar Excel.
  6. Reset total del módulo.
  7. Si cambia la sucursal activa, regenerar mensajes no enviados.
"""

import io
import os
import tempfile
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Request, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from openpyxl import Workbook, load_workbook

from templates_shared import templates

from core.rutas_recordatorios import (
    AGENDA_CACHE, VACUNAS_CACHE, CARPETA_REPORTES,
    cargar_json, guardar_json,
)
from core.recordatorios.sucursales import (
    cargar_sucursales, sucursal_activa, nombre_clinica_activa, guardar_sucursal_activa,
)
from core.recordatorios.procesar_excel import (
    procesar_excel, detectar_tipo_excel, regenerar_mensajes_cliente,
)
from core.recordatorios import historial, envio

router = APIRouter(prefix="/recordatorios", tags=["recordatorios"])

# ------------------------------------------------------------
# Helpers de caché
# ------------------------------------------------------------

def _normalizar_cache(data) -> dict:
    if data is None:
        return {"sucursal": "", "clientes": []}
    if isinstance(data, list):
        return {"sucursal": "", "clientes": data}
    if isinstance(data, dict):
        return {
            "sucursal": data.get("sucursal", ""),
            "clientes": data.get("clientes", []) or [],
        }
    return {"sucursal": "", "clientes": []}


def _cargar_caches() -> tuple[dict, dict]:
    citas = _normalizar_cache(cargar_json(AGENDA_CACHE, None))
    vacunas = _normalizar_cache(cargar_json(VACUNAS_CACHE, None))
    return citas, vacunas


def _guardar_caches(citas: dict, vacunas: dict) -> None:
    activa = sucursal_activa().get("id", "")
    guardar_json(AGENDA_CACHE, {"sucursal": activa, "clientes": citas["clientes"]})
    guardar_json(VACUNAS_CACHE, {"sucursal": activa, "clientes": vacunas["clientes"]})


def _mensaje_de(cliente: dict) -> str:
    return "\n\n".join(cliente.get("mensajes", []))


def _nombres_mascotas(cliente: dict) -> str:
    mascotas = cliente.get("mascotas", [])
    nombres = []
    for m in mascotas:
        if isinstance(m, str):
            nombres.append(m)
        elif isinstance(m, dict):
            nombres.append(m.get("nombre", ""))
    return ", ".join(n for n in nombres if n)


def _regenerar_si_cambio_sucursal(citas: dict, vacunas: dict) -> bool:
    """Regenera mensajes de clientes no enviados si cambió la sucursal."""
    activa_actual = sucursal_activa().get("id", "")
    guardada = citas.get("sucursal") or vacunas.get("sucursal") or ""
    if not guardada or guardada == activa_actual:
        return False

    nombre_clinica = nombre_clinica_activa()
    for lista, tipo in ((citas["clientes"], "citas"), (vacunas["clientes"], "vacunas")):
        for c in lista:
            if historial.ya_fue_enviado(c["telefono"], tipo, _mensaje_de(c)):
                continue
            regenerar_mensajes_cliente(c, nombre_clinica)

    _guardar_caches(citas, vacunas)
    return True


# ------------------------------------------------------------
# Vistas
# ------------------------------------------------------------

@router.get("", response_class=HTMLResponse)
async def index(request: Request):
    citas, vacunas = _cargar_caches()
    if _regenerar_si_cambio_sucursal(citas, vacunas):
        # recargar tras regenerar
        citas, vacunas = _cargar_caches()

    sucursales = cargar_sucursales()
    activa = sucursal_activa()

    # Enriquecer con estado "enviado"
    def _enriquecer(lista, tipo):
        out = []
        for c in lista:
            enviado = historial.ya_fue_enviado(c["telefono"], tipo, _mensaje_de(c))
            out.append({
                **c,
                "enviado": enviado,
                "mensaje_completo": _mensaje_de(c),
                "mascotas_txt": _nombres_mascotas(c),
                "wa_url": envio.construir_url_whatsapp(c["telefono"]),
            })
        return out

    citas_rich = _enriquecer(citas["clientes"], "citas")
    vacunas_rich = _enriquecer(vacunas["clientes"], "vacunas")

    stats = {
        "citas_total": len(citas_rich),
        "citas_enviados": sum(1 for c in citas_rich if c["enviado"]),
        "vacunas_total": len(vacunas_rich),
        "vacunas_enviados": sum(1 for c in vacunas_rich if c["enviado"]),
    }

    return templates.TemplateResponse("recordatorios.html", {
        "request": request,
        "citas": citas_rich,
        "vacunas": vacunas_rich,
        "stats": stats,
        "sucursales": sucursales.get("sucursales", {}),
        "sucursal_activa_id": activa.get("id", ""),
        "sucursal_activa_nombre": activa.get("nombre", ""),
    })


# ------------------------------------------------------------
# Importar Excel
# ------------------------------------------------------------

@router.post("/importar")
async def importar(files: list[UploadFile] = File(...)):
    if not files:
        raise HTTPException(status_code=400, detail="No se enviaron archivos.")

    citas, vacunas = _cargar_caches()
    nombre_clinica = nombre_clinica_activa()
    resumen = []

    for f in files:
        nombre = f.filename or "archivo.xlsx"
        try:
            contenido = await f.read()
            with tempfile.NamedTemporaryFile(delete=False, suffix=Path(nombre).suffix) as tmp:
                tmp.write(contenido)
                tmp_path = tmp.name

            try:
                resultado = procesar_excel(tmp_path, nombre_clinica)
                nuevas_c = 0
                nuevas_v = 0

                if resultado.get("citas"):
                    claves = {c["telefono"] for c in citas["clientes"]}
                    for c in resultado["citas"]:
                        if c["telefono"] not in claves:
                            citas["clientes"].append(c)
                            nuevas_c += 1
                            claves.add(c["telefono"])
                    resumen.append(f"✅ {nombre}: {len(resultado['citas'])} clientes de citas ({nuevas_c} nuevos)")

                if resultado.get("vacunas"):
                    claves = {c["telefono"] for c in vacunas["clientes"]}
                    for c in resultado["vacunas"]:
                        if c["telefono"] not in claves:
                            vacunas["clientes"].append(c)
                            nuevas_v += 1
                            claves.add(c["telefono"])
                    resumen.append(f"✅ {nombre}: {len(resultado['vacunas'])} clientes de vacunas ({nuevas_v} nuevos)")

                if not resultado.get("citas") and not resultado.get("vacunas"):
                    resumen.append(f"❌ {nombre}: no se detectaron columnas de citas ni vacunas")
            finally:
                os.unlink(tmp_path)
        except Exception as e:
            resumen.append(f"❌ {nombre}: {e}")

    _guardar_caches(citas, vacunas)
    return JSONResponse({"ok": True, "resumen": resumen})


# ------------------------------------------------------------
# Marcar / Desmarcar
# ------------------------------------------------------------

@router.post("/marcar/{tipo}/{idx}")
async def marcar(tipo: str, idx: int):
    if tipo not in ("citas", "vacunas"):
        raise HTTPException(400, "Tipo inválido")
    citas, vacunas = _cargar_caches()
    lista = citas["clientes"] if tipo == "citas" else vacunas["clientes"]
    if not (0 <= idx < len(lista)):
        raise HTTPException(404, "Cliente no encontrado")
    c = lista[idx]
    historial.marcar_enviado(c["telefono"], tipo, _mensaje_de(c), c["nombre"])
    return JSONResponse({"ok": True})


@router.post("/desmarcar/{tipo}/{idx}")
async def desmarcar(tipo: str, idx: int):
    if tipo not in ("citas", "vacunas"):
        raise HTTPException(400, "Tipo inválido")
    citas, vacunas = _cargar_caches()
    lista = citas["clientes"] if tipo == "citas" else vacunas["clientes"]
    if not (0 <= idx < len(lista)):
        raise HTTPException(404, "Cliente no encontrado")
    c = lista[idx]
    historial.desmarcar_enviado(c["telefono"], tipo)
    return JSONResponse({"ok": True})


# ------------------------------------------------------------
# WhatsApp: devuelve URL y mensaje para que el frontend haga wa.me
# ------------------------------------------------------------

@router.get("/whatsapp/{tipo}/{idx}")
async def whatsapp(tipo: str, idx: int):
    if tipo not in ("citas", "vacunas"):
        raise HTTPException(400, "Tipo inválido")
    citas, vacunas = _cargar_caches()
    lista = citas["clientes"] if tipo == "citas" else vacunas["clientes"]
    if not (0 <= idx < len(lista)):
        raise HTTPException(404, "Cliente no encontrado")
    c = lista[idx]
    mensaje = _mensaje_de(c)
    url = envio.construir_url_whatsapp(c["telefono"], mensaje)
    return JSONResponse({
        "ok": True,
        "url": url,
        "mensaje": mensaje,
        "nombre": c["nombre"],
    })


# ------------------------------------------------------------
# Exportar Excel
# ------------------------------------------------------------

@router.get("/excel")
async def exportar_excel():
    citas, vacunas = _cargar_caches()
    wb = Workbook()

    # Hoja Citas
    ws = wb.active
    assert ws is not None
    ws.title = "Citas"
    ws.append(["Cliente", "Teléfono", "Mascotas", "Fecha", "Hora", "Asunto", "Agenda", "Estado", "Enviado"])
    for c in citas["clientes"]:
        enviado = historial.ya_fue_enviado(c["telefono"], "citas", _mensaje_de(c))
        for cita in c.get("citas", []):
            ws.append([
                c["nombre"], c["telefono_display"], _nombres_mascotas(c),
                cita.get("fecha", ""), cita.get("hora", ""),
                cita.get("asunto", ""), cita.get("agenda", ""), cita.get("estado", ""),
                "Sí" if enviado else "No",
            ])

    # Hoja Vacunas
    ws2 = wb.create_sheet("Vacunas")
    ws2.append(["Cliente", "Teléfono", "Mascotas", "Tipo recordatorio", "Vacuna", "Próxima fecha", "Enviado"])
    for c in vacunas["clientes"]:
        enviado = historial.ya_fue_enviado(c["telefono"], "vacunas", _mensaje_de(c))
        for m in c.get("mascotas", []):
            if not isinstance(m, dict):
                continue
            for r in m.get("recordatorios", []):
                for t in r.get("tipos", []):
                    ws2.append([
                        c["nombre"], c["telefono_display"], m.get("nombre", ""),
                        r.get("nombre", ""), t.get("nombre", ""), t.get("fecha", ""),
                        "Sí" if enviado else "No",
                    ])

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    filename = f"Recordatorios_{datetime.now().strftime('%Y-%m-%d_%H%M')}.xlsx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ------------------------------------------------------------
# Reset
# ------------------------------------------------------------

@router.post("/reset")
async def reset():
    """Borra TODO lo del módulo: cachés, historial, reportes. NO toca Ingresos/Egresos."""
    for p in (AGENDA_CACHE, VACUNAS_CACHE):
        try:
            if p.exists():
                p.unlink()
        except Exception:
            pass
    # Historial
    from core.rutas_recordatorios import HISTORIAL_FILE
    try:
        if HISTORIAL_FILE.exists():
            HISTORIAL_FILE.unlink()
    except Exception:
        pass
    # Reportes
    if CARPETA_REPORTES.exists():
        for f in CARPETA_REPORTES.glob("*"):
            try:
                f.unlink()
            except Exception:
                pass
    return JSONResponse({"ok": True})


# ------------------------------------------------------------
# Cambiar sucursal activa (afecta a todos los módulos que la usen)
# ------------------------------------------------------------

@router.post("/sucursal")
async def cambiar_sucursal(sucursal_id: str = Form(...)):
    guardar_sucursal_activa(sucursal_id)
    return RedirectResponse("/recordatorios", status_code=303)