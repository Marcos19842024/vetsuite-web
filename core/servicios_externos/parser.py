import re
from datetime import datetime

RE_METODO = re.compile(
    r"^(efectivo|transferencia|tarjeta|tc|td|deposito|depósito)\b", re.I
)
RE_FECHA = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{2,4})")


def parsear_pagado(texto: str) -> dict:
    """'Transferencia 12/9/26' -> {'metodo':'Transferencia','fecha':'2026-09-12','pendiente':False}"""
    texto = (texto or "").strip()
    if not texto:
        return {"metodo": "", "fecha": "", "pendiente": True}

    m = RE_METODO.search(texto)
    metodo = m.group(1).title() if m else ""
    if metodo in ("Tc", "Td"):
        metodo = "Tarjeta"

    fecha = ""
    f = RE_FECHA.search(texto)
    if f:
        d, mo, y = int(f.group(1)), int(f.group(2)), int(f.group(3))
        if y < 100:
            y += 2000
        try:
            fecha = datetime(y, mo, d).strftime("%Y-%m-%d")
        except ValueError:
            fecha = ""

    return {"metodo": metodo, "fecha": fecha, "pendiente": False}