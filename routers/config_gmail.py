import json
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse

from shared.templates_shared import templates
from shared.rutas import GMAIL_CONFIG

router = APIRouter(prefix="/config_gmail", tags=["config gmail"])


def _leer():
    if not GMAIL_CONFIG.exists():
        return {}
    try:
        return json.loads(GMAIL_CONFIG.read_text(encoding="utf-8"))
    except Exception:
        return {}


@router.get("", response_class=HTMLResponse)
def config_gmail_form(request: Request):
    cfg = _leer()
    return templates.TemplateResponse(
        "config_gmail.html",
        {"request": request, "cfg": cfg, "mensaje": ""},
    )


@router.post("")
def config_gmail_guardar(
    usuario: str = Form(""),
    password_app: str = Form(""),
    etiqueta: str = Form(""),
    filtro_remitente: str = Form(""),
):
    cfg = {
        "usuario": usuario.strip(),
        "password_app": password_app.strip(),
        "etiqueta": etiqueta.strip(),
        "filtro_remitente": filtro_remitente.strip(),
        "dias_atras": 10,
    }
    GMAIL_CONFIG.write_text(
        json.dumps(cfg, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return JSONResponse({"status": "ok"})