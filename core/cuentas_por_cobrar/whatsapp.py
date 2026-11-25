# core/cuentas_por_cobrar/whatsapp.py
"""
Renderizado de plantillas de WhatsApp y construcción de URLs wa.me.
"""

from __future__ import annotations
from urllib.parse import quote

from core.cuentas_por_cobrar.calculos import normalizar_telefono


PLACEHOLDERS_REQUERIDOS = {
    "promesa_seguimiento": ["promesa_fecha", "promesa_monto"],
}


def renderizar(plantilla: str, contexto: dict) -> str:
    """Sustituye los placeholders {clave} en la plantilla."""
    if not plantilla:
        return ""
    resultado = plantilla
    for clave, valor in contexto.items():
        resultado = resultado.replace("{" + clave + "}", str(valor or ""))
    return resultado


def construir_url(telefono: str, mensaje: str) -> str:
    """Construye la URL de WhatsApp Web/App con el teléfono normalizado."""
    tel = normalizar_telefono(telefono)
    if not tel:
        return ""
    if len(tel) == 10 and not tel.startswith("52"):
        tel = "52" + tel
    return f"https://wa.me/{tel}?text={quote(mensaje, safe='')}"


def construir_contexto(cliente: dict, albaranes: list[dict], extra: dict | None = None) -> dict:
    """Construye el dict de contexto para renderizar la plantilla."""
    mascotas = []
    for a in albaranes:
        m = (a.get("paciente") or "").strip()
        if m and m not in mascotas:
            mascotas.append(m)

    if len(mascotas) > 3:
        mascotas_txt = ", ".join(mascotas[:3]) + f" y {len(mascotas) - 3} más"
    elif mascotas:
        mascotas_txt = ", ".join(mascotas)
    else:
        mascotas_txt = "sus mascotas"

    ctx = {
        "cliente": cliente.get("nombre", ""),
        "saldo": f"{float(cliente.get('saldo') or 0):,.2f}",
        "mascota": mascotas_txt,
        "dias": cliente.get("dias_antiguedad", 0),
        "n_albaranes": cliente.get("n_albaranes", 0),
    }
    if extra:
        ctx.update(extra)
    return ctx


def validar_placeholders(clave: str, contexto: dict) -> tuple[bool, list[str]]:
    """Devuelve (ok, faltantes)."""
    requeridos = PLACEHOLDERS_REQUERIDOS.get(clave, [])
    faltantes = []
    for req in requeridos:
        val = contexto.get(req)
        if val is None or str(val).strip() in ("", "0", "0.00"):
            faltantes.append(req)
    return (len(faltantes) == 0, faltantes)