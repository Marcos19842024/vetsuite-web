from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse

import uploads_manager as um
import egresos.manager as em

router = APIRouter(prefix="/uploads", tags=["uploads"])

# Ruta para Egresos (debe ir ANTES de la ruta genérica)
@router.get("/egresos/{ruta:path}")
def servir_egreso(ruta: str):
    archivo = em.resolver_path_upload(ruta)
    if archivo is None:
        raise HTTPException(status_code=404, detail="Archivo no encontrado")

    ext = archivo.suffix.lower()
    if ext in (".xml", ".txt"):
        return PlainTextResponse(archivo.read_text(encoding="utf-8", errors="ignore"))
    if ext == ".xlsx":
        return FileResponse(
            archivo,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    return FileResponse(archivo)

# Ruta genérica (Ingresos y fallback)
@router.get("/{ruta:path}")
def servir_archivo(ruta: str):
    archivo = um.resolver_path_upload(ruta)
    if archivo is None:
        raise HTTPException(status_code=404, detail="Archivo no encontrado")

    ext = archivo.suffix.lower()
    if ext == ".pdf":
        return FileResponse(archivo, media_type="application/pdf")
    if ext in (".xml", ".txt"):
        return PlainTextResponse(archivo.read_text(encoding="utf-8", errors="ignore"))
    if ext == ".xlsx":
        return FileResponse(
            archivo,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    return FileResponse(archivo)