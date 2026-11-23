# core/cuentas_por_cobrar/calculos.py
from __future__ import annotations
from datetime import date, datetime
from typing import Any

from core.cuentas_por_cobrar.config import cargar_config


def normalizar_nombre(s: str) -> str:
    """Colapsa espacios, mayúsculas, quita puntos y acentos. Para cruces."""
    if not s:
        return ""
    s = str(s).strip().upper()
    for a, b in (("Á","A"),("É","E"),("Í","I"),("Ó","O"),("Ú","U"),("Ñ","N")):
        s = s.replace(a, b)
    s = s.replace(".", "")
    return " ".join(s.split())


def es_institucional(nombre: str) -> bool:
    cfg = cargar_config()
    lista = {normalizar_nombre(x) for x in cfg.get("institucionales", [])}
    return normalizar_nombre(nombre) in lista


def normalizar_fecha(v: Any) -> str:
    """
    Acepta datetime, date, 'YYYY-MM-DD HH:MM:SS.ffffff', 'YYYY-MM-DD'.
    Devuelve 'YYYY-MM-DD' o ''.
    """
    if v is None or v == "":
        return ""
    if isinstance(v, datetime):
        return v.date().isoformat()
    if isinstance(v, date):
        return v.isoformat()
    s = str(v).strip()
    if not s:
        return ""
    # Quita hora si viene con ' '
    s = s.split(" ")[0]
    try:
        return datetime.strptime(s, "%Y-%m-%d").date().isoformat()
    except ValueError:
        # Intento con barras
        try:
            return datetime.strptime(s, "%d/%m/%Y").date().isoformat()
        except ValueError:
            return ""


def dias_antiguedad(fecha_iso: str, hoy: date | None = None) -> int:
    if not fecha_iso:
        return 0
    hoy = hoy or date.today()
    try:
        f = datetime.strptime(fecha_iso, "%Y-%m-%d").date()
    except ValueError:
        return 0
    return max(0, (hoy - f).days)


def semaforo(dias: int, cfg: dict | None = None) -> str:
    cfg = cfg or cargar_config().get("semaforo", {})
    verde = cfg.get("verde_max", 30)
    amarillo = cfg.get("amarillo_max", 60)
    naranja = cfg.get("naranja_max", 90)
    if dias <= verde:
        return "verde"
    if dias <= amarillo:
        return "amarillo"
    if dias <= naranja:
        return "naranja"
    return "rojo"


def normalizar_telefono(v: str) -> str:
    """
    Limpia teléfonos sucios del Excel de QVET.
    - Quita todo lo que no sea dígito.
    - Si quedan 10 dígitos → los deja (México).
    - Si quedan 12-13 y empieza con 52 → los deja (ya trae lada).
    - Si quedan menos de 10 → los deja tal cual (dato sucio).
    - Si queda vacío → devuelve "".
    """
    if not v:
        return ""
    digitos = "".join(c for c in str(v) if c.isdigit())
    if not digitos:
        return ""
    # Si trae 52 al principio y son 12-13 dígitos, ya está con lada
    if digitos.startswith("52") and len(digitos) in (12, 13):
        return digitos
    # 10 dígitos: teléfono MX estándar
    if len(digitos) == 10:
        return digitos
    # Menos o más: devolver tal cual (recepción lo corrige)
    return digitos