"""
Generador de Excel para la web.
Adaptado de excel/constantes.py + escritor.py + estilos.py + generador.py.
Recibe una lista de dicts (los `datos_json` deserializados) y devuelve
el path a un .xlsx temporal.
"""
from datetime import datetime
from pathlib import Path
import tempfile

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter


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
FUENTE_NORMAL = Font()
SIN_RELLENO = PatternFill()
FILL_TOTAL = PatternFill("solid", fgColor="FFD966")
FORMATO_MONEDA = '"$"#,##0.00'
FORMATO_FECHA = "DD/MM/YYYY"


# ============================================================
# COLORES Y COLUMNAS
# ============================================================
COLORES_SECCION = {
    "GENERAL":      "1F4E3D",
    "U":            "2E5A88",
    "ACCESORIOS":   "7B3F00",
    "MEDICAMENTOS": "8B1A1A",
    "HIGIENE":      "4B6B00",
    "ESTETICA":     "6A1B9A",
    "TRANSPORTE":   "0D47A1",
    "PENSION":      "B85C00",
    "VACUNA":       "00695C",
    "CLINICA":      "37474F",
    "TOTAL":        "000000",
    "TIPO DE PAGO": "4A148C",
    "CONTROL":      "455A64",
}

COLUMNAS = {
    "A":  ("No. DE FACTURA",              "GENERAL",       "text"),
    "B":  ("QVET",                        "GENERAL",       "text"),
    "C":  ("FECHA DE EMISIÓN",            "GENERAL",       "date"),
    "D":  ("NOMBRE",                      "GENERAL",       "text"),
    "E":  ("RFC",                         "GENERAL",       "text"),
    "F":  ("IMPORTE",                     "U",             "money"),
    "G":  ("IVA (16%)",                   "U",             "money"),
    "H":  ("IMPORTE",                     "ACCESORIOS",    "money"),
    "I":  ("IVA (16%)",                   "ACCESORIOS",    "money"),
    "J":  ("IMPORTE (sin IVA)",           "MEDICAMENTOS",  "money"),
    "K":  ("SIN IVA",                     "MEDICAMENTOS",  "money"),
    "L":  ("IVA (16%)",                   "MEDICAMENTOS",  "money"),
    "M":  ("IMPORTE (sin IVA)",           "HIGIENE",       "money"),
    "N":  ("SIN IVA",                     "HIGIENE",       "money"),
    "O":  ("IVA (16%)",                   "HIGIENE",       "money"),
    "P":  ("SIN IEPS 6%",                 "HIGIENE",       "money"),
    "Q":  ("IEPS (6%)",                   "HIGIENE",       "money"),
    "R":  ("SIN IEPS 7%",                 "HIGIENE",       "money"),
    "S":  ("IEPS (7%)",                   "HIGIENE",       "money"),
    "T":  ("IMPORTE",                     "ESTETICA",      "money"),
    "U":  ("IVA (16%)",                   "ESTETICA",      "money"),
    "V":  ("IMPORTE",                     "TRANSPORTE",    "money"),
    "W":  ("IVA (16%)",                   "TRANSPORTE",    "money"),
    "X":  ("IMPORTE",                     "PENSION",       "money"),
    "Y":  ("IVA (16%)",                   "PENSION",       "money"),
    "Z":  ("IMPORTE",                     "VACUNA",        "money"),
    "AA": ("IMPORTE",                     "CLINICA",       "money"),
    "AB": ("Total Remisiones",            "TOTAL",         "total_remisiones"),
    "AC": ("Total Factura",               "TOTAL",         "total_factura"),
    "AD": ("EFECTIVO",                    "TIPO DE PAGO",  "money"),
    "AE": ("TARJETA",                     "TIPO DE PAGO",  "money"),
    "AF": ("CHEQUE",                      "TIPO DE PAGO",  "money"),
    "AG": ("TRANSF.",                     "TIPO DE PAGO",  "money"),
    "AH": ("VALE",                        "TIPO DE PAGO",  "money"),
    "AI": ("FECHA DE TIMBRADO",           "CONTROL",       "date"),
    "AJ": ("FECHA FICHA DE DEPÓSITO",     "CONTROL",       "date"),
    "AK": ("MONTO DE FICHA DE DEPOSITO",  "CONTROL",       "money"),
    "AL": ("FECHA SANTANDER TARJETA",     "CONTROL",       "date"),
    "AM": ("EDO. CUENTA SANTANDER DEBITO","CONTROL",       "money"),
    "AN": ("EDO. CUENTA SANTANDER CREDITO","CONTROL",      "money"),
    "AO": ("FECHA SANTANDER TRANSFERENCIA","CONTROL",      "date"),
    "AP": ("TRANSFERENCIA SANTANDER",     "CONTROL",       "money"),
    "AQ": ("FOLIO FISCAL",                "CONTROL",       "text"),
}

MAPA_CLAVES = {
    "A": "no_factura", "B": "qvet", "C": "fecha", "D": "nombre", "E": "rfc",
    "F": "u_importe", "G": "u_iva",
    "H": "ac_importe", "I": "ac_iva",
    "J": "med_importe", "K": "med_sin_iva", "L": "med_iva",
    "M": "hig_importe", "N": "hig_sin_iva", "O": "hig_iva",
    "P": "hig_sin_ieps_6", "Q": "hig_ieps_6",
    "R": "hig_sin_ieps_7", "S": "hig_ieps_7",
    "T": "est_importe", "U": "est_iva",
    "V": "tra_importe", "W": "tra_iva",
    "X": "pen_importe", "Y": "pen_iva",
    "Z": "vac_importe",
    "AA": "cli_importe",
    "AB": "__total_remisiones__", "AC": "__total_factura__",
    "AD": "efectivo", "AE": "__tarjeta__", "AF": "cheque",
    "AG": "transfer", "AH": "vale",
    "AI": "fecha_impresion",
    "AJ": "", "AK": "__efectivo_dup__",
    "AL": "", "AM": "td", "AN": "tc", "AO": "",
    "AP": "__transfer_dup__", "AQ": "folio_fiscal",
}

FORMULAS_AUTO = {
    "G":  "=F{r}*0.16",
    "I":  "=H{r}*0.16",
    "L":  "=K{r}*0.16",
    "O":  "=N{r}*0.16",
    "Q":  "=P{r}*0.06",
    "S":  "=R{r}*0.07",
    "U":  "=T{r}*0.16",
    "W":  "=V{r}*0.16",
    "Y":  "=X{r}*0.16",
    "AB": "=F{r}+G{r}+H{r}+I{r}+J{r}+K{r}+L{r}+M{r}+N{r}+O{r}+P{r}+Q{r}+R{r}+S{r}+T{r}+U{r}+V{r}+W{r}+X{r}+Y{r}+Z{r}+AA{r}",
    "AC": "=AD{r}+AE{r}+AF{r}+AG{r}+AH{r}",
}

GRUPOS = [
    (6,  7,  "U"),
    (8,  9,  "ACCESORIOS"),
    (10, 12, "MEDICAMENTOS"),
    (13, 19, "HIGIENE"),
    (20, 21, "ESTETICA"),
    (22, 23, "TRANSPORTE"),
    (24, 25, "PENSION"),
    (26, 26, "VACUNA"),
    (27, 27, "CLINICA"),
    (28, 29, "TOTAL"),
    (30, 34, "TIPO DE PAGO"),
    (35, 43, "CONTROL"),
]


# ============================================================
# ESCRITURA
# ============================================================
def _escribir_encabezados(ws):
    for ini, fin, texto in GRUPOS:
        c = ws.cell(row=1, column=ini, value=texto)
        c.font = BOLD_DARK
        c.alignment = CENTRO
        for col in range(ini, fin + 1):
            celda = ws.cell(row=1, column=col)
            celda.border = BORDER
            celda.alignment = CENTRO
        if ini != fin:
            ws.merge_cells(start_row=1, start_column=ini,
                           end_row=1, end_column=fin)

    for letra, (titulo, seccion, tipo) in COLUMNAS.items():
        c = ws[f"{letra}2"]
        c.value = titulo
        c.font = BOLD_WHITE
        c.fill = PatternFill("solid", fgColor=COLORES_SECCION[seccion])
        c.alignment = CENTRO
        c.border = BORDER


def _buscar_letra(clave_buscada):
    for letra, clave in MAPA_CLAVES.items():
        if clave == clave_buscada:
            return letra
    return None


def _calcular_total_remisiones(r):
    claves = [
        "u_importe", "u_iva",
        "ac_importe", "ac_iva",
        "est_importe", "est_iva",
        "tra_importe", "tra_iva",
        "pen_importe", "pen_iva",
        "vac_importe",
        "cli_importe",
        "med_importe", "med_sin_iva", "med_iva",
        "hig_importe", "hig_sin_iva", "hig_iva",
        "hig_sin_ieps_6", "hig_ieps_6",
        "hig_sin_ieps_7", "hig_ieps_7",
    ]
    total = 0.0
    for k in claves:
        try:
            total += float(r.get(k, 0) or 0)
        except (ValueError, TypeError):
            pass
    return round(total, 2)


def _calcular_total_factura(r):
    claves = ["efectivo", "tc", "td", "cheque", "transfer", "vale"]
    total = 0.0
    for k in claves:
        try:
            total += float(r.get(k, 0) or 0)
        except (ValueError, TypeError):
            pass
    return round(total, 2)


def _escribir_fila(ws, r, fila):
    valor_tc = float(r.get("tc", 0) or 0)
    valor_td = float(r.get("td", 0) or 0)
    valor_tarjeta = valor_tc + valor_td
    valor_efectivo = float(r.get("efectivo", 0) or 0)
    valor_transfer = float(r.get("transfer", 0) or 0)

    for letra, (titulo, seccion, tipo) in COLUMNAS.items():
        clave = MAPA_CLAVES[letra]
        c = ws[f"{letra}{fila}"]
        c.font = FUENTE_NORMAL
        c.fill = SIN_RELLENO
        c.border = BORDER

        if clave == "__tarjeta__":
            l_tc = _buscar_letra("tc")
            l_td = _buscar_letra("td")
            if l_tc and l_td:
                c.value = f"={l_tc}{fila}+{l_td}{fila}"
                c.number_format = FORMATO_MONEDA
            elif valor_tarjeta > 0:
                c.value = valor_tarjeta
                c.number_format = FORMATO_MONEDA
            c.alignment = DERECHA
            continue

        if clave == "__efectivo_dup__":
            l_ef = _buscar_letra("efectivo")
            if l_ef:
                c.value = f"={l_ef}{fila}"
                c.number_format = FORMATO_MONEDA
            elif valor_efectivo > 0:
                c.value = valor_efectivo
                c.number_format = FORMATO_MONEDA
            c.alignment = DERECHA
            continue

        if clave == "__transfer_dup__":
            l_tr = _buscar_letra("transfer")
            if l_tr:
                c.value = f"={l_tr}{fila}"
                c.number_format = FORMATO_MONEDA
            elif valor_transfer > 0:
                c.value = valor_transfer
                c.number_format = FORMATO_MONEDA
            c.alignment = DERECHA
            continue

        if clave == "__total_remisiones__":
            c.value = FORMULAS_AUTO["AB"].format(r=fila)
            c.number_format = FORMATO_MONEDA
            c.alignment = DERECHA
            tr = _calcular_total_remisiones(r)
            tf = _calcular_total_factura(r)
            if abs(tr - tf) > 0.01:
                c.font = Font(color="FF0000", bold=True)
            continue

        if clave == "__total_factura__":
            c.value = FORMULAS_AUTO["AC"].format(r=fila)
            c.number_format = FORMATO_MONEDA
            c.alignment = DERECHA
            c.font = Font(bold=True)
            continue

        if clave == "":
            c.alignment = CENTRO
            continue

        valor = r.get(clave, 0 if tipo == "money" else "")
        expresion = r.get(f"{clave}__expr", "")

        if tipo == "money":
            if expresion:
                c.value = f"={expresion}"
            elif letra in FORMULAS_AUTO:
                c.value = FORMULAS_AUTO[letra].format(r=fila)
            else:
                c.value = float(valor or 0)
            c.number_format = FORMATO_MONEDA
            c.alignment = DERECHA
        elif tipo == "date":
            if valor:
                try:
                    dt = datetime.strptime(str(valor).strip(), "%d/%m/%Y")
                    c.value = dt
                    c.number_format = FORMATO_FECHA
                except (ValueError, TypeError):
                    c.value = valor
            c.alignment = CENTRO
        else:
            c.value = valor
            c.alignment = IZQUIERDA


def _escribir_totales(ws, fila):
    MI, MF = 1, 5
    c = ws.cell(row=fila, column=MI, value="TOTALES")
    c.font = BOLD_DARK
    c.fill = FILL_TOTAL
    c.alignment = CENTRO
    c.border = BORDER
    for col in range(MI, MF + 1):
        celda = ws.cell(row=fila, column=col)
        celda.fill = FILL_TOTAL
        celda.border = BORDER
        celda.alignment = CENTRO
    ws.merge_cells(start_row=fila, start_column=MI, end_row=fila, end_column=MF)

    for letra, (titulo, seccion, tipo) in COLUMNAS.items():
        col_idx = ws[f"{letra}1"].column
        if MI <= col_idx <= MF:
            continue
        celda = ws.cell(row=fila, column=col_idx)
        if tipo in ("money", "total_remisiones", "total_factura"):
            celda.value = f"=SUM({letra}3:{letra}{fila - 1})"
            celda.number_format = FORMATO_MONEDA
            celda.alignment = DERECHA
        celda.font = BOLD_DARK
        celda.fill = FILL_TOTAL
        celda.border = BORDER


def _ajustar_anchos(ws, fila_total):
    for letra in COLUMNAS.keys():
        largo_max = len(str(COLUMNAS[letra][0]))
        for ini, fin, texto in GRUPOS:
            c_ini = get_column_letter(ini)
            c_fin = get_column_letter(fin)
            if c_ini <= letra <= c_fin:
                n = fin - ini + 1
                largo_max = max(largo_max, len(texto) / n if n else 0)
                break
        for f in range(3, fila_total):
            celda = ws[f"{letra}{f}"]
            if celda.value is None:
                continue
            if isinstance(celda.value, datetime):
                txt = celda.value.strftime("%d/%m/%Y")
            elif isinstance(celda.value, (int, float)):
                txt = f"${celda.value:,.2f}"
            else:
                txt = str(celda.value)
            largo_max = max(largo_max, len(txt))
        ws.column_dimensions[letra].width = min(max(largo_max + 2, 8), 40)
    ws.column_dimensions["AQ"].width = max(ws.column_dimensions["AQ"].width, 38)
    ws.column_dimensions["D"].width = max(ws.column_dimensions["D"].width, 22)


# ============================================================
# API PÚBLICA
# ============================================================
def generar_excel(registros, titulo_hoja="Ingresos"):
    """
    registros: lista de dicts (cada uno con los campos que devuelve
    agrupar_por_categoria + los de cabecera).

    Devuelve el path al .xlsx temporal.
    """
    wb = Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = (titulo_hoja or "Ingresos")[:31]

    _escribir_encabezados(ws)

    fila = 3
    for r in registros:
        _escribir_fila(ws, r, fila)
        fila += 1

    _escribir_totales(ws, fila)
    _ajustar_anchos(ws, fila)

    ws.row_dimensions[1].height = 22
    ws.row_dimensions[2].height = 32
    ws.freeze_panes = "F3"

    tmp = tempfile.NamedTemporaryFile(
        prefix="vetsuite_", suffix=".xlsx", delete=False
    )
    tmp.close()
    wb.save(tmp.name)
    return tmp.name