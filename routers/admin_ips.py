from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse

from core import permisos_ip
from templates_shared import templates

router = APIRouter(prefix="/admin_ips", tags=["admin ips"])


@router.get("", response_class=HTMLResponse)
async def panel(request: Request):
    assert request.client is not None
    if not permisos_ip.es_admin(request.client.host):
        return HTMLResponse("No autorizado", status_code=403)
    cfg = permisos_ip.cargar()
    return templates.TemplateResponse(
        "admin_ips.html",
        {"request": request, "cfg": cfg, "ip_actual": request.client.host},
    )


@router.post("/guardar")
async def guardar(
    request: Request,
    ip: str = Form(...),
    nombre: str = Form(""),
    modulos: list[str] = Form(default=[]),
):
    assert request.client is not None
    if not permisos_ip.es_admin(request.client.host):
        return HTMLResponse("No autorizado", status_code=403)
    ip = ip.strip()
    nombre = nombre.strip()
    cfg = permisos_ip.cargar()
    if not modulos:
        cfg["ips"].pop(ip, None)
    else:
        cfg["ips"][ip] = {"nombre": nombre, "modulos": list(modulos)}
    permisos_ip.guardar(cfg)
    return RedirectResponse("/admin_ips", status_code=303)


@router.post("/eliminar")
async def eliminar(request: Request, ip: str = Form(...)):
    assert request.client is not None
    if not permisos_ip.es_admin(request.client.host):
        return HTMLResponse("No autorizado", status_code=403)
    cfg = permisos_ip.cargar()
    cfg["ips"].pop(ip, None)
    permisos_ip.guardar(cfg)
    return RedirectResponse("/admin_ips", status_code=303)