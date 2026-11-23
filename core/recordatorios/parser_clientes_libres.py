# core/recordatorios/parser_clientes_libres.py
"""
Parser para Excel de clientes libres de Recordatorios.

Soporta:
- Columna de nombre: CLIENTE, Nombre, Propietario, etc.
- Múltiples columnas de teléfono: TELÉFONO1, TELÉFONO2, TELEFONO3,
  TELÉFONO SMS, Teléfono, Celular, etc.
- Toma el primer teléfono válido que encuentre por fila
  (mínimo 7 dígitos, máximo 15).
- Limpia caracteres basura: guiones, espacios, paréntesis, letras.
"""

from openpyxl import load_workbook


# Aliases para nombre (normalizado: sin acentos, minúsculas)
_ALIAS_NOMBRE = {"cliente", "nombre", "propietario", "dueno", "dueno(a)", "tutor", "paciente"}

# Aliases que se consideran "columna de teléfono" (cualquier coincidencia por prefijo)
_PREFIJOS_TELEFONO = ("telefono", "tel", "celular", "movil", "whatsapp", "phone", "sms", "contacto")


def _normalizar(s: str) -> str:
    if s is None:
        return ""
    s = str(s).strip().lower()
    reemplazos = {"á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u", "ñ": "n"}
    for a, b in reemplazos.items():
        s = s.replace(a, b)
    return s


def _es_columna_telefono(encabezado: str) -> bool:
    n = _normalizar(encabezado)
    if not n:
        return False
    for prefijo in _PREFIJOS_TELEFONO:
        if n.startswith(prefijo):
            return True
    return False


def _detectar_columnas(encabezados: list[str]) -> dict:
    """Devuelve {nombre: idx, telefonos: [idx, idx, ...]}."""
    mapa = {"nombre": None, "telefonos": []}
    for i, h in enumerate(encabezados):
        n = _normalizar(h)
        if not n:
            continue
        if n in _ALIAS_NOMBRE and mapa["nombre"] is None:
            mapa["nombre"] = i
        elif _es_columna_telefono(h):
            mapa["telefonos"].append(i)
    return mapa


def _limpiar_telefono(valor) -> str:
    """
    Devuelve solo dígitos. Acepta:
      9811360489       -> 9811360489
      981 158 87 85    -> 9811588785
      81-3-18-92       -> 8131892
      (001) 4847441121 -> 0014847441121  (se recorta a 10-15)
      xcvbnbvc         -> ""  (sin dígitos válidos)
      sin numero       -> ""
      .                -> ""
    """
    if valor is None:
        return ""
    s = "".join(c for c in str(valor) if c.isdigit())
    if not s:
        return ""
    # Normalizar: quitar prefijo 52 (México) si tiene 12 dígitos y empieza con 52
    if len(s) == 12 and s.startswith("52"):
        s = s[2:]
    # Quitar prefijo internacional con 00
    if s.startswith("00") and len(s) >= 12:
        s = s[-10:]
    # Validar longitud razonable (7 a 15 dígitos)
    if len(s) < 7 or len(s) > 15:
        return ""
    return s


def _formato_display(tel: str) -> str:
    if len(tel) == 10:
        return f"{tel[:3]} {tel[3:6]} {tel[6:]}"
    if len(tel) == 12 and tel.startswith("52"):
        return f"+52 {tel[2:5]} {tel[5:8]} {tel[8:]}"
    return tel


def _primer_telefono_valido(fila, cols_telefono: list[int]) -> str:
    """Recorre las columnas de teléfono y regresa el primer válido."""
    for idx in cols_telefono:
        if idx < len(fila):
            tel = _limpiar_telefono(fila[idx])
            if tel:
                return tel
    return ""


def parsear_excel_clientes(ruta: str) -> list[dict]:
    """
    Devuelve [{nombre, telefono, telefono_display, mascotas_txt}]
    Solo procesa filas con nombre + al menos un teléfono válido.
    """
    wb = load_workbook(ruta, data_only=True, read_only=True)
    clientes = []
    vistos = set()  # evitar duplicados por teléfono

    for ws in wb.worksheets:
        filas = list(ws.iter_rows(values_only=True))
        if not filas:
            continue

        # Buscar la fila de encabezados (primeras 10 filas)
        idx_encabezado = None
        for i, fila in enumerate(filas[:10]):
            vals = [_normalizar(v) for v in fila if v is not None]
            if any(v in _ALIAS_NOMBRE for v in vals) or any(
                _es_columna_telefono(v) for v in vals
            ):
                idx_encabezado = i
                break

        if idx_encabezado is None:
            continue

        encabezados = filas[idx_encabezado]
        mapa = _detectar_columnas(encabezados)
        if mapa["nombre"] is None or not mapa["telefonos"]:
            continue  # hoja no compatible

        for fila in filas[idx_encabezado + 1:]:
            if not fila:
                continue

            nombre = fila[mapa["nombre"]] if mapa["nombre"] < len(fila) else None
            nombre = (str(nombre).strip() if nombre else "")
            if not nombre:
                continue

            telefono = _primer_telefono_valido(fila, mapa["telefonos"])
            if not telefono:
                continue

            if telefono in vistos:
                continue
            vistos.add(telefono)

            clientes.append({
                "nombre": nombre,
                "telefono": telefono,
                "telefono_display": _formato_display(telefono),
                "mascotas": [],
                "mascotas_txt": "",
            })

    wb.close()
    return clientes