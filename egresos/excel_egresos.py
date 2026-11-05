"""
Generador de Excel para Egresos (versión web).
Adaptado de excel/egresos.py. La diferencia es que el enlace al PDF
apunta a `/uploads/egresos/xml/...` para que el usuario lo abra
en el navegador.
"""
from datetime import datetime
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side


# ============================================================
# ESTILOS
# ============================================================
THIN = Side(border_style="thin", color="808080")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
CENTRO = Alignment(horizontal="center", vertical="center", wrap_text=True)
DERECHA = Alignment(horizontal="right", vertical="center")
IZQUIERDA = Alignment(horizontal="left", vertical="center")
BOLD_WHITE = Font(bold=True, color="FFFFFF", size=11)
BOLD_DARK = Font(bold=True, color="000000", size=10)
FUENTE_LINK = Font(color="0563C1", underline="single")
FORMATO_MONEDA = '"$"#,##0.00'

COLOR_PUE = "1F4E3D"
COLOR_PPD = "2E5A88"


def _clave_orden(f):
    """Ordena por fecha ascendente y luego por folio."""
    fecha_str = f.get("fecha", "")
    try:
        partes = fecha_str.split("-") if "-" in fecha_str else fecha_str.split("/")
        if len(partes) == 3:
            if "-" in fecha_str:
                fecha = (int(partes[0]), int(partes[1]), int(partes[2]))
            else:
                fecha = (int(partes[2]), int(partes[1]), int(partes[0]))
        else:
            fecha = (0, 0, 0)
    except Exception:
        fecha = (0, 0, 0)
    return (fecha, str(f.get("folio", "")))


def _fecha_a_ddmmyyyy(fecha_str):
    """'2026-10-15' -> '15/10/2026'. Si ya está, la deja."""
    if not fecha_str:
        return ""
    s = str(fecha_str).strip()
    if "/" in s:
        return s
    try:
        dt = datetime.strptime(s[:10], "%Y-%m-%d")
        return dt.strftime("%d/%m/%Y")
    except ValueError:
        return s


def _obtener_link_xml(f):
    """
    Devuelve la ruta relativa al XML (para el enlace en el Excel).
    En web, el link apunta a /uploads/egresos/xml/... para abrir en navegador.
    """
    fecha = f.get("fecha", "")
    anio, mes_idx = _anio_mes_de_fecha(fecha)
    if not anio:
        return None

    mes_nombre = _MESES[mes_idx - 1] # type: ignore
    sucursal = f.get("sucursal", "Baalak")
    metodo = f.get("metodo_pago", "PUE")
    forma = "PPD" if metodo == "PPD" else f.get("forma_pago", "Efectivo")
    folio = f.get("folio", "")
    serie = str(f.get("serie", "")).strip()

    if not folio:
        return None

    nombre = f"{serie}-{folio}.xml" if serie else f"{folio}.xml"
    return (
        f"/uploads/egresos/xml/{anio}/{mes_nombre}/"
        f"{sucursal}/{metodo}/{forma}/{nombre}"
    )


_MESES = [
    "01_enero", "02_febrero", "03_marzo", "04_abril",
    "05_mayo", "06_junio", "07_julio", "08_agosto",
    "09_septiembre", "10_octubre", "11_noviembre", "12_diciembre",
]

_MESES_ES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


def _anio_mes_de_fecha(fecha_str):
    """'2026-10-15' o '15/10/2026' -> (2026, 10) o (None, None)."""
    if not fecha_str:
        return None, None
    s = str(fecha_str).strip()
    if "-" in s:
        try:
            dt = datetime.strptime(s[:10], "%Y-%m-%d")
            return dt.year, dt.month
        except ValueError:
            return None, None
    if "/" in s:
        try:
            dt = datetime.strptime(s, "%d/%m/%Y")
            return dt.year, dt.month
        except ValueError:
            return None, None
    return None, None


# ============================================================
# GENERAR EXCEL PUE
# ============================================================
def generar_excel_pue(facturas, ruta_xlsx, mes_nombre, anio):
    """Genera el Excel de facturas PUE."""
    facturas = sorted(facturas, key=_clave_orden)
    wb = Workbook()
    ws = wb.active
    assert ws is not None, "El workbook no tiene hoja activa"
    ws.title = f"PUE {mes_nombre.capitalize()} {anio}"[:31]

    encabezados = [
        ("A", "#", 6),
        ("B", "No. FACTURA", 20),
        ("C", "UUID", 38),
        ("D", "RFC EMISOR", 16),
        ("E", "NOMBRE O RAZÓN SOCIAL DEL EMISOR", 50),
        ("F", "FECHA", 12),
        ("G", "TOTAL", 14),
        ("H", "METODO DE PAGO", 16),
        ("I", "OBSERVACIONES", 30),
    ]
    for letra, titulo, ancho in encabezados:
        c = ws[f"{letra}1"]
        c.value = titulo
        c.font = BOLD_WHITE
        c.fill = PatternFill("solid", fgColor=COLOR_PUE)
        c.alignment = CENTRO
        c.border = BORDER
        ws.column_dimensions[letra].width = ancho

    fila = 2
    for idx, f in enumerate(facturas, 1):
        ws[f"A{fila}"] = idx
        ws[f"A{fila}"].alignment = CENTRO
        ws[f"A{fila}"].border = BORDER

        c = ws[f"B{fila}"]
        c.value = f.get("folio", "")
        c.alignment = IZQUIERDA
        c.border = BORDER
        link = _obtener_link_xml(f)
        if link:
            c.hyperlink = link
            c.font = FUENTE_LINK

        ws[f"C{fila}"] = f.get("uuid", "")
        ws[f"C{fila}"].alignment = IZQUIERDA
        ws[f"C{fila}"].border = BORDER

        ws[f"D{fila}"] = f.get("rfc_emisor", "")
        ws[f"D{fila}"].alignment = CENTRO
        ws[f"D{fila}"].border = BORDER

        ws[f"E{fila}"] = f.get("nombre_emisor", "")
        ws[f"E{fila}"].alignment = IZQUIERDA
        ws[f"E{fila}"].border = BORDER

        ws[f"F{fila}"] = _fecha_a_ddmmyyyy(f.get("fecha", ""))
        ws[f"F{fila}"].alignment = CENTRO
        ws[f"F{fila}"].border = BORDER

        ws[f"G{fila}"] = float(f.get("total", 0) or 0)
        ws[f"G{fila}"].number_format = FORMATO_MONEDA
        ws[f"G{fila}"].alignment = DERECHA
        ws[f"G{fila}"].border = BORDER

        ws[f"H{fila}"] = f.get("forma_pago", "")
        ws[f"H{fila}"].alignment = CENTRO
        ws[f"H{fila}"].border = BORDER

        ws[f"I{fila}"] = f.get("notas", "")
        ws[f"I{fila}"].alignment = IZQUIERDA
        ws[f"I{fila}"].border = BORDER

        fila += 1

    ws[f"F{fila}"] = "TOTAL:"
    ws[f"F{fila}"].font = BOLD_DARK
    ws[f"F{fila}"].alignment = DERECHA
    ws[f"G{fila}"] = f"=SUM(G2:G{fila-1})"
    ws[f"G{fila}"].font = BOLD_DARK
    ws[f"G{fila}"].number_format = FORMATO_MONEDA
    ws[f"G{fila}"].alignment = DERECHA

    wb.save(ruta_xlsx)
    return ruta_xlsx


# ============================================================
# GENERAR EXCEL PPD
# ============================================================
def generar_excel_ppd(facturas, ruta_xlsx, mes_nombre, anio):
    """Genera el Excel de facturas PPD."""
    facturas = sorted(facturas, key=_clave_orden)
    wb = Workbook()
    ws = wb.active
    assert ws is not None, "El workbook no tiene hoja activa"
    ws.title = f"PPD {mes_nombre.capitalize()} {anio}"[:31]

    encabezados = [
        ("A", "#", 6),
        ("B", "FECHA", 12),
        ("C", "FACTURA", 20),
        ("D", "QVET", 12),
        ("E", "PROVEEDOR", 50),
        ("F", "UUID", 38),
        ("G", "METODO", 10),
        ("H", "SUBTOTAL", 14),
        ("I", "IVA", 12),
        ("J", "IEPS", 12),
        ("K", "TOTAL", 14),
        ("L", "REFERENCIA", 20),
    ]
    for letra, titulo, ancho in encabezados:
        c = ws[f"{letra}1"]
        c.value = titulo
        c.font = BOLD_WHITE
        c.fill = PatternFill("solid", fgColor=COLOR_PPD)
        c.alignment = CENTRO
        c.border = BORDER
        ws.column_dimensions[letra].width = ancho

    fila = 2
    for idx, f in enumerate(facturas, 1):
        ws[f"A{fila}"] = idx
        ws[f"A{fila}"].alignment = CENTRO
        ws[f"A{fila}"].border = BORDER

        ws[f"B{fila}"] = _fecha_a_ddmmyyyy(f.get("fecha", ""))
        ws[f"B{fila}"].alignment = CENTRO
        ws[f"B{fila}"].border = BORDER

        c = ws[f"C{fila}"]
        c.value = f.get("folio", "")
        c.alignment = IZQUIERDA
        c.border = BORDER
        link = _obtener_link_xml(f)
        if link:
            c.hyperlink = link
            c.font = FUENTE_LINK

        ws[f"D{fila}"] = ""
        ws[f"D{fila}"].alignment = CENTRO
        ws[f"D{fila}"].border = BORDER

        ws[f"E{fila}"] = f.get("nombre_emisor", "")
        ws[f"E{fila}"].alignment = IZQUIERDA
        ws[f"E{fila}"].border = BORDER

        ws[f"F{fila}"] = f.get("uuid", "")
        ws[f"F{fila}"].alignment = IZQUIERDA
        ws[f"F{fila}"].border = BORDER

        ws[f"G{fila}"] = "PPD"
        ws[f"G{fila}"].alignment = CENTRO
        ws[f"G{fila}"].border = BORDER

        ws[f"H{fila}"] = float(f.get("subtotal", 0) or 0)
        ws[f"H{fila}"].number_format = FORMATO_MONEDA
        ws[f"H{fila}"].alignment = DERECHA
        ws[f"H{fila}"].border = BORDER

        ws[f"I{fila}"] = float(f.get("iva", 0) or 0)
        ws[f"I{fila}"].number_format = FORMATO_MONEDA
        ws[f"I{fila}"].alignment = DERECHA
        ws[f"I{fila}"].border = BORDER

        ws[f"J{fila}"] = float(f.get("ieps", 0) or 0)
        ws[f"J{fila}"].number_format = FORMATO_MONEDA
        ws[f"J{fila}"].alignment = DERECHA
        ws[f"J{fila}"].border = BORDER

        ws[f"K{fila}"] = float(f.get("total", 0) or 0)
        ws[f"K{fila}"].number_format = FORMATO_MONEDA
        ws[f"K{fila}"].alignment = DERECHA
        ws[f"K{fila}"].border = BORDER

        ws[f"L{fila}"] = ""
        ws[f"L{fila}"].alignment = CENTRO
        ws[f"L{fila}"].border = BORDER

        fila += 1

    ws[f"E{fila}"] = "TOTAL:"
    ws[f"E{fila}"].font = BOLD_DARK
    ws[f"E{fila}"].alignment = DERECHA
    for letra in ["H", "I", "J", "K"]:
        c = ws[f"{letra}{fila}"]
        c.value = f"=SUM({letra}2:{letra}{fila-1})"
        c.font = BOLD_DARK
        c.number_format = FORMATO_MONEDA
        c.alignment = DERECHA

    wb.save(ruta_xlsx)
    return ruta_xlsx


# ============================================================
# ANEXAR A EXCEL EXISTENTE
# ============================================================
def anexar_facturas_al_excel(ruta_xlsx, facturas, tipo):
    """
    Anexa facturas nuevas a un Excel existente (PUE o PPD).
    Detecta duplicados por UUID.
    Devuelve (nuevos, omitidos).
    """
    if tipo not in ("PUE", "PPD"):
        raise ValueError(f"Tipo inválido: {tipo}")

    if tipo == "PUE":
        COL_UUID = 3
    else:
        COL_UUID = 6

    wb = load_workbook(ruta_xlsx)
    ws = wb.active

    uuids_existentes = set()
    fila_totales_original = None

    fila = 2
    assert ws is not None
    max_fila = ws.max_row + 10
    while fila <= max_fila:
        for col in range(1, ws.max_column + 1):
            val = ws.cell(row=fila, column=col).value
            if val and str(val).strip().upper() == "TOTAL:":
                fila_totales_original = fila
                break
        if fila_totales_original:
            break

        val_uuid = ws.cell(row=fila, column=COL_UUID).value
        if val_uuid:
            uuids_existentes.add(str(val_uuid).strip().upper())

        fila_vacia = all(
            ws.cell(row=fila, column=c).value in (None, "")
            for c in range(1, ws.max_column + 1)
        )
        if fila_vacia:
            break
        fila += 1

    if fila_totales_original is None:
        fila_totales_original = fila

    nuevas = []
    omitidas = 0
    for f in facturas:
        uuid = str(f.get("uuid", "")).strip().upper()
        if uuid and uuid in uuids_existentes:
            omitidas += 1
            continue
        nuevas.append(f)

    if not nuevas:
        return 0, omitidas

    nuevas = sorted(nuevas, key=_clave_orden)

    for rango in list(ws.merged_cells.ranges):
        if rango.min_row == fila_totales_original:
            try:
                ws.unmerge_cells(str(rango))
            except Exception:
                pass

    for col in range(1, ws.max_column + 1):
        celda = ws.cell(row=fila_totales_original, column=col)
        celda.value = None
        celda.font = Font()
        celda.fill = PatternFill()
        celda.border = Border()
        celda.alignment = Alignment()

    fila_insercion = fila_totales_original
    for f in nuevas:
        _escribir_fila_egreso(ws, f, fila_insercion, tipo)
        fila_insercion += 1

    for i, fila_num in enumerate(range(2, fila_insercion)):
        ws[f"A{fila_num}"] = i + 1

    _escribir_totales_egreso(ws, fila_insercion, tipo)

    wb.save(ruta_xlsx)
    return len(nuevas), omitidas


def _escribir_fila_egreso(ws, f, fila, tipo):
    ws[f"A{fila}"] = fila - 1
    ws[f"A{fila}"].alignment = CENTRO
    ws[f"A{fila}"].border = BORDER

    if tipo == "PUE":
        c = ws[f"B{fila}"]
        c.value = f.get("folio", "")
        c.alignment = IZQUIERDA
        c.border = BORDER
        link = _obtener_link_xml(f)
        if link:
            c.hyperlink = link
            c.font = FUENTE_LINK

        ws[f"C{fila}"] = f.get("uuid", "")
        ws[f"C{fila}"].alignment = IZQUIERDA
        ws[f"C{fila}"].border = BORDER

        ws[f"D{fila}"] = f.get("rfc_emisor", "")
        ws[f"D{fila}"].alignment = CENTRO
        ws[f"D{fila}"].border = BORDER

        ws[f"E{fila}"] = f.get("nombre_emisor", "")
        ws[f"E{fila}"].alignment = IZQUIERDA
        ws[f"E{fila}"].border = BORDER

        ws[f"F{fila}"] = _fecha_a_ddmmyyyy(f.get("fecha", ""))
        ws[f"F{fila}"].alignment = CENTRO
        ws[f"F{fila}"].border = BORDER

        ws[f"G{fila}"] = float(f.get("total", 0) or 0)
        ws[f"G{fila}"].number_format = FORMATO_MONEDA
        ws[f"G{fila}"].alignment = DERECHA
        ws[f"G{fila}"].border = BORDER

        ws[f"H{fila}"] = f.get("forma_pago", "")
        ws[f"H{fila}"].alignment = CENTRO
        ws[f"H{fila}"].border = BORDER

        ws[f"I{fila}"] = f.get("notas", "")
        ws[f"I{fila}"].alignment = IZQUIERDA
        ws[f"I{fila}"].border = BORDER

    else:  # PPD
        ws[f"B{fila}"] = _fecha_a_ddmmyyyy(f.get("fecha", ""))
        ws[f"B{fila}"].alignment = CENTRO
        ws[f"B{fila}"].border = BORDER

        c = ws[f"C{fila}"]
        c.value = f.get("folio", "")
        c.alignment = IZQUIERDA
        c.border = BORDER
        link = _obtener_link_xml(f)
        if link:
            c.hyperlink = link
            c.font = FUENTE_LINK

        ws[f"D{fila}"] = ""
        ws[f"D{fila}"].alignment = CENTRO
        ws[f"D{fila}"].border = BORDER

        ws[f"E{fila}"] = f.get("nombre_emisor", "")
        ws[f"E{fila}"].alignment = IZQUIERDA
        ws[f"E{fila}"].border = BORDER

        ws[f"F{fila}"] = f.get("uuid", "")
        ws[f"F{fila}"].alignment = IZQUIERDA
        ws[f"F{fila}"].border = BORDER

        ws[f"G{fila}"] = "PPD"
        ws[f"G{fila}"].alignment = CENTRO
        ws[f"G{fila}"].border = BORDER

        ws[f"H{fila}"] = float(f.get("subtotal", 0) or 0)
        ws[f"H{fila}"].number_format = FORMATO_MONEDA
        ws[f"H{fila}"].alignment = DERECHA
        ws[f"H{fila}"].border = BORDER

        ws[f"I{fila}"] = float(f.get("iva", 0) or 0)
        ws[f"I{fila}"].number_format = FORMATO_MONEDA
        ws[f"I{fila}"].alignment = DERECHA
        ws[f"I{fila}"].border = BORDER

        ws[f"J{fila}"] = float(f.get("ieps", 0) or 0)
        ws[f"J{fila}"].number_format = FORMATO_MONEDA
        ws[f"J{fila}"].alignment = DERECHA
        ws[f"J{fila}"].border = BORDER

        ws[f"K{fila}"] = float(f.get("total", 0) or 0)
        ws[f"K{fila}"].number_format = FORMATO_MONEDA
        ws[f"K{fila}"].alignment = DERECHA
        ws[f"K{fila}"].border = BORDER

        ws[f"L{fila}"] = ""
        ws[f"L{fila}"].alignment = CENTRO
        ws[f"L{fila}"].border = BORDER


def _escribir_totales_egreso(ws, fila, tipo):
    if tipo == "PUE":
        ws[f"F{fila}"] = "TOTAL:"
        ws[f"F{fila}"].font = BOLD_DARK
        ws[f"F{fila}"].alignment = DERECHA
        ws[f"G{fila}"] = f"=SUM(G2:G{fila-1})"
        ws[f"G{fila}"].font = BOLD_DARK
        ws[f"G{fila}"].number_format = FORMATO_MONEDA
        ws[f"G{fila}"].alignment = DERECHA
    else:
        ws[f"E{fila}"] = "TOTAL:"
        ws[f"E{fila}"].font = BOLD_DARK
        ws[f"E{fila}"].alignment = DERECHA
        for letra in ["H", "I", "J", "K"]:
            c = ws[f"{letra}{fila}"]
            c.value = f"=SUM({letra}2:{letra}{fila-1})"
            c.font = BOLD_DARK
            c.number_format = FORMATO_MONEDA
            c.alignment = DERECHA