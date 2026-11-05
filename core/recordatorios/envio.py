# core/recordatorios/envio.py
"""
Envío vía wa.me: devuelve la URL y el mensaje para que el frontend
lo copie al portapapeles y abra el chat.
"""
from urllib.parse import quote


def construir_url_whatsapp(telefono: str, mensaje: str = "") -> str:
    """
    telefono debe venir con código de país (ej. 529811333080).
    Devuelve https://wa.me/<telefono>?text=<mensaje_urlencoded>
    """
    tel = "".join(ch for ch in str(telefono) if ch.isdigit())
    if not tel:
        return ""
    base = f"https://wa.me/{tel}"
    if mensaje:
        return f"{base}?text={quote(mensaje)}"
    return base