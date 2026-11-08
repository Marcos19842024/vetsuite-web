"""Instancia única de Jinja2Templates para todo el proyecto.

Se importa desde main.py y desde todos los routers, para que
los helpers globales (modulos_ip, es_admin_ip) estén disponibles
en cualquier template que extienda base.html.
"""
from pathlib import Path
from fastapi.templating import Jinja2Templates

from core import permisos_ip
from shared.rutas import ROOT as BASE

templates = Jinja2Templates(directory=BASE / "templates")


def _modulos_ip(request):
    return permisos_ip.modulos_permitidos(request.client.host)


def _es_admin_ip(request):
    return permisos_ip.es_admin(request.client.host)


templates.env.globals["modulos_ip"] = _modulos_ip
templates.env.globals["es_admin_ip"] = _es_admin_ip