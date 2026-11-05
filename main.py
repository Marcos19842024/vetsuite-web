from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from db import init_db
from core import permisos_ip
from templates_shared import templates
from routers import (
    corte_semanal, ingresos, egresos, recordatorios, config_gmail, uploads, rechazados,
    admin_ips, servicios_externos
)

BASE = Path(__file__).parent

app = FastAPI(title="VetSuite Web")
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")


@app.middleware("http")
async def control_permisos_ip(request: Request, call_next):
    path = request.url.path
    assert request.client is not None
    ip = request.client.host

    if path == "/admin/ips" or path.startswith("/admin/ips/"):
        if not permisos_ip.es_admin(ip):
            return HTMLResponse("No autorizado", status_code=403)
        return await call_next(request)

    modulo = permisos_ip.modulo_de_path(path)
    if modulo:
        permitidos = permisos_ip.modulos_permitidos(ip)
        if modulo not in permitidos:
            return RedirectResponse("/", status_code=303)

    return await call_next(request)


@app.on_event("startup")
def startup():
    init_db()


@app.middleware("http")
async def no_cache_html(request: Request, call_next):
    response = await call_next(request)
    ct = response.headers.get("content-type", "")
    if ct.startswith("text/html"):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

app.include_router(ingresos.router)
app.include_router(egresos.router)
app.include_router(corte_semanal.router)
app.include_router(servicios_externos.router)
app.include_router(recordatorios.router)
app.include_router(config_gmail.router)
app.include_router(rechazados.router)
app.include_router(uploads.router)
app.include_router(admin_ips.router)


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    assert request.client is not None
    ip = request.client.host
    permitidos = permisos_ip.modulos_permitidos(ip)

    if len(permitidos) == 1:
        return RedirectResponse(f"/{permitidos[0]}", status_code=303)

    if len(permitidos) == 0:
        return templates.TemplateResponse(
            "index.html",
            {"request": request, "sin_acceso": True, "ip": ip},
        )

    return templates.TemplateResponse("index.html", {"request": request})