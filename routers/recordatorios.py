# routers/recordatorios.py
"""
Módulo de Recordatorios — versión web.

Flujo:
  1. Importar Excel (citas / vacunas / clientes libres) → cache JSON.
  2. Ver tabla con tabs Citas / Vacunas / Convenios / Libres.
  3. Enviar por WhatsApp (wa.me) → copiar mensaje + abrir chat.
  4. Marcar / desmarcar enviado (historial persistente).
  5. Exportar Excel.
  6. Reset total del módulo (NO borra plantillas).
  7. Si cambia la sucursal activa, regenerar mensajes no enviados.
"""

import io
import os
import tempfile
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Request, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from openpyxl import Workbook

from shared.templates_shared import templates
from core.rutas_recordatorios import (
    AGENDA_CACHE, CONVENIOS_CACHE, VACUNAS_CACHE, LIBRES_CLIENTES_CACHE,
    CARPETA_REPORTES, HISTORIAL_FILE,
    cargar_json, guardar_json,
)
from core.recordatorios.sucursales import (
    cargar_sucursales, sucursal_activa, nombre_clinica_activa, guardar_sucursal_activa,
)
from core.recordatorios.procesar_excel import (
    procesar_excel, regenerar_mensajes_cliente,
)
from core.recordatorios.parser_clientes_libres import parsear_excel_clientes
from core.recordatorios.convenios_generator import generar as generar_convenios
from core.recordatorios import historial, envio, convenios_cache
from core.recordatorios import plantillas as plantillas_mod
from core.recordatorios import clientes_libres

router = APIRouter(prefix="/recordatorios", tags=["recordatorios"])


# ============================================================
# Helpers
# ============================================================

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
    """Mensaje para citas/vacunas (lista de strings unidas por \\n\\n)."""
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


def _telefonos_enviados_por_tipo(hist, tipo: str) -> set[str]:
    """
    Set de teléfonos con AL MENOS un envío de ese tipo (sin importar mensaje).
    Usado solo en exportación Excel como resumen histórico.
    Soporta dict indexado, dict con items o list.
    """
    telefonos = set()

    if isinstance(hist, dict) and isinstance(hist.get("items"), list):
        for it in hist["items"]:
            if isinstance(it, dict) and it.get("tipo") == tipo:
                tel = (it.get("telefono") or "").strip()
                if tel:
                    telefonos.add(tel)
        return telefonos

    if isinstance(hist, list):
        for it in hist:
            if isinstance(it, dict) and it.get("tipo") == tipo:
                tel = (it.get("telefono") or "").strip()
                if tel:
                    telefonos.add(tel)
        return telefonos

    if isinstance(hist, dict):
        for clave, valor in hist.items():
            if isinstance(valor, dict) and valor.get("tipo") == tipo:
                tel = (valor.get("telefono") or "").strip()
                if not tel and isinstance(clave, str) and "|" in clave:
                    tel = clave.split("|", 1)[0].strip()
                if tel:
                    telefonos.add(tel)
            elif isinstance(clave, str) and "|" in clave:
                partes = clave.split("|")
                if len(partes) >= 2 and partes[1] == tipo and partes[0].strip():
                    telefonos.add(partes[0].strip())

    return telefonos


def _resolver_plantilla(pid) -> dict | None:
    """Devuelve la plantilla activa por id, o la primera activa como fallback."""
    if pid:
        try:
            p = plantillas_mod.obtener(int(pid))
            if p and p.get("activa"):
                return p
        except Exception:
            pass
    activas = plantillas_mod.listar_activas()
    return activas[0] if activas else None


def _lista_por_tipo(tipo: str) -> list[dict]:
    """Lista cruda según tipo."""
    if tipo == "citas":
        citas, _ = _cargar_caches()
        return citas["clientes"]
    if tipo == "vacunas":
        _, vacunas = _cargar_caches()
        return vacunas["clientes"]
    if tipo == "libres":
        return clientes_libres.cargar()
    raise HTTPException(400, "Tipo inválido")


def _mensaje_para_cliente(tipo: str, c: dict, plantilla: dict | None) -> str:
    """Mensaje final para mostrar/enviar/marcar según tipo."""
    if tipo == "libres":
        if not plantilla:
            return ""
        return plantillas_mod.renderizar(plantilla["cuerpo"], c, nombre_clinica_activa())
    return _mensaje_de(c)


# ============================================================
# Vistas
# ============================================================

@router.get("", response_class=HTMLResponse)
async def index(request: Request):
    citas, vacunas = _cargar_caches()
    if _regenerar_si_cambio_sucursal(citas, vacunas):
        citas, vacunas = _cargar_caches()

    sucursales = cargar_sucursales()
    activa = sucursal_activa()

    # --- Citas / Vacunas ---
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

    # --- Convenios ---
    conv_data = convenios_cache.cargar()
    convenios_rich = []
    for idx, it in enumerate(conv_data.get("items", [])):
        if it.get("descartado"):
            continue
        enviado = historial.ya_fue_enviado(it.get("telefono", ""), "convenios", it.get("mensaje", ""))
        convenios_rich.append({
            **it,
            "idx": idx,
            "enviado": enviado,
            "wa_url": envio.construir_url_whatsapp(it.get("telefono", "")),
        })

    # --- Libres: enviado por mensaje exacto (como citas/vacunas) ---
    libres_lista = clientes_libres.cargar()
    plantilla_activa = _resolver_plantilla(request.query_params.get("plantilla_libres"))
    nombre_clinica = nombre_clinica_activa()

    libres_rich = []
    for idx, c in enumerate(libres_lista):
        tel = (c.get("telefono") or "").strip()
        mensaje = ""
        if plantilla_activa:
            mensaje = plantillas_mod.renderizar(plantilla_activa["cuerpo"], c, nombre_clinica)
        enviado = bool(tel and mensaje and historial.ya_fue_enviado(tel, "libres", mensaje))
        libres_rich.append({
            **c,
            "idx": idx,
            "enviado": enviado,
            "mensaje_completo": mensaje,
            "mascotas_txt": "",
            "wa_url": envio.construir_url_whatsapp(tel) if tel else "",
        })

    stats = {
        "citas_total":        len(citas_rich),
        "citas_enviados":     sum(1 for c in citas_rich if c["enviado"]),
        "vacunas_total":      len(vacunas_rich),
        "vacunas_enviados":   sum(1 for c in vacunas_rich if c["enviado"]),
        "convenios_total":    len(convenios_rich),
        "convenios_enviados": sum(1 for c in convenios_rich if c["enviado"]),
        "libres_total":       len(libres_rich),
        "libres_enviados":    sum(1 for c in libres_rich if c["enviado"]),
    }

    return templates.TemplateResponse("recordatorios.html", {
        "request": request,
        "citas": citas_rich,
        "vacunas": vacunas_rich,
        "convenios": convenios_rich,
        "libres": libres_rich,
        "stats": stats,
        "plantilla_activa": {
            "id": plantilla_activa["id"] if plantilla_activa else None,
            "nombre": plantilla_activa["nombre"] if plantilla_activa else "",
        },
        "sucursales": sucursales.get("sucursales", {}),
        "sucursal_activa_id": activa.get("id", ""),
        "sucursal_activa_nombre": activa.get("nombre", ""),
    })


@router.get("/libres/stats")
async def libres_stats(plantilla_id: int = 0):
    """
    Conteo opcional de enviados con una plantilla específica.
    No lo usa la UI actual (el server ya manda stats), pero se deja por compatibilidad.
    """
    lista = clientes_libres.cargar()
    plantilla = _resolver_plantilla(plantilla_id)
    if not plantilla:
        return JSONResponse({"ok": True, "total": len(lista), "enviados": 0})
    nombre = nombre_clinica_activa()
    enviados = sum(
        1 for c in lista
        if historial.ya_fue_enviado(
            (c.get("telefono") or "").strip(),
            "libres",
            plantillas_mod.renderizar(plantilla["cuerpo"], c, nombre),
        )
    )
    return JSONResponse({"ok": True, "total": len(lista), "enviados": enviados})


# ============================================================
# Importar Excel (unificado)
# ============================================================

@router.post("/importar")
async def importar(files: list[UploadFile] = File(...), destino: str = Form("auto")):
    if not files:
        raise HTTPException(400, "No se enviaron archivos.")

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
                resultado = {"citas": [], "vacunas": [], "libres": []}

                if destino == "libres":
                    resultado["libres"] = parsear_excel_clientes(tmp_path)
                else:
                    res = procesar_excel(tmp_path, nombre_clinica)
                    resultado["citas"]  = res.get("citas", [])
                    resultado["vacunas"] = res.get("vacunas", [])
                    if not resultado["citas"] and not resultado["vacunas"]:
                        resultado["libres"] = parsear_excel_clientes(tmp_path)

                es_libres = destino == "libres" or (
                    not resultado["citas"] and not resultado["vacunas"] and resultado["libres"]
                )
                if es_libres:
                    if not resultado["libres"]:
                        resumen.append(
                            f"❌ {nombre}: no se detectaron clientes. "
                            f"El Excel debe tener columnas de Nombre y Teléfono."
                        )
                        continue
                    nuevos, total = clientes_libres.agregar(resultado["libres"])
                    resumen.append(
                        f"✅ {nombre}: {len(resultado['libres'])} clientes libres "
                        f"({nuevos} nuevos, total {total})"
                    )
                    continue

                if resultado["citas"]:
                    claves = {c["telefono"] for c in citas["clientes"]}
                    nuevas_c = 0
                    for c in resultado["citas"]:
                        if c["telefono"] not in claves:
                            citas["clientes"].append(c)
                            nuevas_c += 1
                            claves.add(c["telefono"])
                    resumen.append(
                        f"✅ {nombre}: {len(resultado['citas'])} clientes de citas "
                        f"({nuevas_c} nuevos)"
                    )

                if resultado["vacunas"]:
                    claves = {v["telefono"] for v in vacunas["clientes"]}
                    nuevas_v = 0
                    for c in resultado["vacunas"]:
                        if c["telefono"] not in claves:
                            vacunas["clientes"].append(c)
                            nuevas_v += 1
                            claves.add(c["telefono"])
                    resumen.append(
                        f"✅ {nombre}: {len(resultado['vacunas'])} clientes de vacunas "
                        f"({nuevas_v} nuevos)"
                    )

                if not any(resultado[k] for k in resultado):
                    resumen.append(
                        f"❌ {nombre}: no se detectaron columnas de citas, "
                        f"vacunas ni clientes libres."
                    )
            finally:
                os.unlink(tmp_path)
        except Exception as e:
            resumen.append(f"❌ {nombre}: {e}")

    _guardar_caches(citas, vacunas)
    return JSONResponse({"ok": True, "resumen": resumen})


# ============================================================
# Marcar / Desmarcar (unificado)
# ============================================================

@router.post("/marcar/{tipo}/{idx}")
async def marcar(tipo: str, idx: int, plantilla_id: int = 0):
    if tipo not in ("citas", "vacunas", "libres"):
        raise HTTPException(400, "Tipo inválido")
    lista = _lista_por_tipo(tipo)
    if not (0 <= idx < len(lista)):
        raise HTTPException(404, "Cliente no encontrado")
    c = lista[idx]

    if tipo == "libres":
        plantilla = _resolver_plantilla(plantilla_id)
        mensaje = plantillas_mod.renderizar(plantilla["cuerpo"], c, nombre_clinica_activa()) if plantilla else ""
    else:
        mensaje = _mensaje_de(c)

    historial.marcar_enviado(c["telefono"], tipo, mensaje, c.get("nombre", ""))
    return JSONResponse({"ok": True})


@router.post("/desmarcar/{tipo}/{idx}")
async def desmarcar(tipo: str, idx: int):
    if tipo not in ("citas", "vacunas", "libres"):
        raise HTTPException(400, "Tipo inválido")
    lista = _lista_por_tipo(tipo)
    if not (0 <= idx < len(lista)):
        raise HTTPException(404, "Cliente no encontrado")
    historial.desmarcar_enviado(lista[idx]["telefono"], tipo)
    return JSONResponse({"ok": True})


# ============================================================
# WhatsApp (unificado)
# ============================================================

@router.get("/whatsapp/{tipo}/{idx}")
async def whatsapp(tipo: str, idx: int, plantilla_id: int = 0):
    if tipo not in ("citas", "vacunas", "libres"):
        raise HTTPException(400, "Tipo inválido")
    lista = _lista_por_tipo(tipo)
    if not (0 <= idx < len(lista)):
        raise HTTPException(404, "Cliente no encontrado")
    c = lista[idx]

    if tipo == "libres":
        plantilla = _resolver_plantilla(plantilla_id)
        if not plantilla:
            raise HTTPException(400, "No hay plantilla activa")
        mensaje = plantillas_mod.renderizar(plantilla["cuerpo"], c, nombre_clinica_activa())
    else:
        mensaje = _mensaje_de(c)

    url = envio.construir_url_whatsapp(c["telefono"], mensaje)
    return JSONResponse({
        "ok": True,
        "url": url,
        "mensaje": mensaje,
        "nombre": c.get("nombre", ""),
    })


# ============================================================
# Exportar Excel
# ============================================================

@router.get("/excel")
async def exportar_excel(plantilla_id: int = 0):
    citas, vacunas = _cargar_caches()
    wb = Workbook()

    # ---------- Hoja Citas ----------
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

    # ---------- Hoja Vacunas ----------
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

    # ---------- Hoja Convenios ----------
    ws3 = wb.create_sheet("Convenios")
    ws3.append([
        "Cliente", "Teléfono", "Mascota", "Folio", "Saldo",
        "Vencimiento", "Días", "Tipo", "Enviado",
    ])
    conv_data = convenios_cache.cargar()
    for it in conv_data.get("items", []):
        if it.get("descartado"):
            continue
        enviado = historial.ya_fue_enviado(
            it.get("telefono", ""), "convenios", it.get("mensaje", "")
        )
        ws3.append([
            it.get("propietario", ""),
            it.get("telefono", ""),
            it.get("mascota", ""),
            it.get("folio", ""),
            float(it.get("pendiente", 0) or 0),
            it.get("fecha_vencimiento", ""),
            int(it.get("dias", 0) or 0),
            it.get("tipo", ""),
            "Sí" if enviado else "No",
        ])

    # ---------- Hoja Libres ----------
    ws4 = wb.create_sheet("Libres")
    ws4.append(["Cliente", "Teléfono", "Enviado (esta plantilla)", "Plantilla"])

    plantilla_activa = _resolver_plantilla(plantilla_id)
    nombre_clinica = nombre_clinica_activa()
    nombre_plantilla = plantilla_activa["nombre"] if plantilla_activa else ""

    for c in clientes_libres.cargar():
        tel = (c.get("telefono") or "").strip()
        enviado = False
        if plantilla_activa and tel:
            mensaje = plantillas_mod.renderizar(plantilla_activa["cuerpo"], c, nombre_clinica)
            enviado = historial.ya_fue_enviado(tel, "libres", mensaje)
        ws4.append([
            c.get("nombre", ""),
            c.get("telefono_display", tel),
            "Sí" if enviado else "No",
            nombre_plantilla,
        ])

    # ---------- Descarga ----------
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    filename = f"Recordatorios_{datetime.now().strftime('%Y-%m-%d_%H%M')}.xlsx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ============================================================
# Reset (NO borra plantillas)
# ============================================================

@router.post("/reset")
async def reset():
    for p in (AGENDA_CACHE, VACUNAS_CACHE, CONVENIOS_CACHE, LIBRES_CLIENTES_CACHE):
        try:
            if p.exists():
                p.unlink()
        except Exception:
            pass
    try:
        if HISTORIAL_FILE.exists():
            HISTORIAL_FILE.unlink()
    except Exception:
        pass
    if CARPETA_REPORTES.exists():
        for f in CARPETA_REPORTES.glob("*"):
            try:
                f.unlink()
            except Exception:
                pass
    return RedirectResponse(url="/recordatorios", status_code=303)


@router.post("/sucursal")
async def cambiar_sucursal(sucursal_id: str = Form(...)):
    guardar_sucursal_activa(sucursal_id)
    return RedirectResponse("/recordatorios", status_code=303)


# ============================================================
# Convenios (propios: JSON distinto + descartar/regenerar)
# ============================================================

@router.post("/convenios/marcar/{idx}")
async def convenios_marcar(idx: int):
    data = convenios_cache.cargar()
    items = data.get("items", [])
    if not (0 <= idx < len(items)):
        raise HTTPException(404, "Mensaje no encontrado")
    it = items[idx]
    historial.marcar_enviado(it.get("telefono", ""), "convenios", it.get("mensaje", ""), it.get("propietario", ""))
    return JSONResponse({"ok": True})


@router.post("/convenios/desmarcar/{idx}")
async def convenios_desmarcar(idx: int):
    data = convenios_cache.cargar()
    items = data.get("items", [])
    if not (0 <= idx < len(items)):
        raise HTTPException(404, "Mensaje no encontrado")
    historial.desmarcar_enviado(items[idx].get("telefono", ""), "convenios")
    return JSONResponse({"ok": True})


@router.get("/convenios/whatsapp/{idx}")
async def convenios_whatsapp(idx: int):
    data = convenios_cache.cargar()
    items = data.get("items", [])
    if not (0 <= idx < len(items)):
        raise HTTPException(404, "Mensaje no encontrado")
    it = items[idx]
    mensaje = it.get("mensaje", "")
    url = envio.construir_url_whatsapp(it.get("telefono", ""), mensaje)
    return JSONResponse({"ok": True, "url": url, "mensaje": mensaje, "nombre": it.get("propietario", "")})


@router.post("/convenios/descartar/{idx}")
async def convenios_descartar(idx: int):
    if not convenios_cache.marcar_descartado(idx):
        raise HTTPException(404, "Mensaje no encontrado")
    return JSONResponse({"ok": True})


@router.post("/convenios/regenerar")
async def convenios_regenerar():
    try:
        resultado = generar_convenios()
        return JSONResponse({"ok": True, **resultado})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


# ============================================================
# Plantillas libres (CRUD)
# ============================================================

@router.get("/plantillas")
async def plantillas_listar():
    return JSONResponse({"ok": True, "items": plantillas_mod.listar_activas()})


@router.post("/plantillas")
async def plantillas_crear(request: Request):
    data = await request.json()
    nombre = (data.get("nombre") or "").strip()
    cuerpo = (data.get("cuerpo") or "").strip()
    if not nombre or not cuerpo:
        raise HTTPException(400, "Nombre y cuerpo son obligatorios")
    pid = plantillas_mod.crear(nombre, cuerpo)
    return JSONResponse({"ok": True, "id": pid})


@router.put("/plantillas/{pid}")
async def plantillas_editar(pid: int, request: Request):
    data = await request.json()
    nombre = (data.get("nombre") or "").strip()
    cuerpo = (data.get("cuerpo") or "").strip()
    if not nombre or not cuerpo:
        raise HTTPException(400, "Nombre y cuerpo son obligatorios")
    if not plantillas_mod.actualizar(pid, nombre, cuerpo):
        raise HTTPException(404, "Plantilla no encontrada")
    return JSONResponse({"ok": True})


@router.delete("/plantillas/{pid}")
async def plantillas_borrar(pid: int):
    if not plantillas_mod.borrar(pid):
        raise HTTPException(404, "Plantilla no encontrada")
    return JSONResponse({"ok": True})