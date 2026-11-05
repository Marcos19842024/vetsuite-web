"""Generador de Excel del Corte Semanal usando la PLANTILLA original.

Toma `uploads/corte_semanal/plantilla_semanal.xlsx` y solo rellena las celdas
de captura. Conserva todo el estilo, fórmulas, merges, anchos y nombre
de hoja del archivo original.
"""
from io import BytesIO
from datetime import date
from pathlib import Path

from openpyxl import load_workbook

RUTA_PLANTILLA = (
    Path(__file__).resolve().parents[2]
    / "uploads"
    / "corte_semanal"
    / "plantilla_semanal.xlsx"
)

# Fila donde está el TÍTULO de cada sucursal en la plantilla original
TITULO_FILA = {"Baalak": 2, "Prado": 41}

# Filas relativas al TÍTULO (todas son sumas: titulo_fila + R[key])
R = {
    "dias":         1,   # fila 3 Baalak, 42 Prado
    "fechas":       2,   # fila 4 Baalak, 43 Prado
    "efectivo_dep": 3,   # fila 5 Baalak, 44 Prado
    "efectivo_cob": 4,   # fila 6 Baalak, 45 Prado
    "td":           5,
    "tc":           6,
    "transf":       7,
    "total_ing":    8,   # fila 10 Baalak, 49 Prado
    "egreso_cab":  11,   # fila 13 Baalak, 52 Prado
    "nomina":      12,   # fila 14 Baalak, 53 Prado
    "gasolina":    13,
    "hemograma":   14,
    "patologia":   15,
    "varios":      16,
    "servicios":   17,
    "capacitacion":18,
    "total_egr":   19,   # fila 21 Baalak, 60 Prado
    "pc_cab":      22,   # fila 24 Baalak, 63 Prado
    "pc_inicio":   23,   # fila 25 Baalak, 64 Prado
    "pc_fin":      34,   # fila 36 Baalak, 75 Prado
    "total_pc":    35,   # fila 37 Baalak, 76 Prado
    "obs":         37,   # fila 39 Baalak, 78 Prado
}

COL_LUNES   = 3   # C
COL_DOMINGO = 9   # I

POR_COBRAR_KEYS = [
    "colaboradores", "clientes_tienda", "clientes_cirugia",
    "clientes_hospitalizacion", "clientes_estetica", "clientes_farmacia",
    "clientes_consulta", "clientes_laboratorio", "clientes_rayos_x",
    "clientes_pension", "tratamiento", "transporte",
]

MESES_ES = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]


def _fila(sucursal: str, clave: str) -> int:
    """Devuelve la fila absoluta de una clave (dias, fechas, etc.)."""
    return TITULO_FILA[sucursal] + R[clave]


def _escribir_valor(ws, fila, col, valor):
    """Número plano, fórmula '=a+b', o no toca la celda si está vacío."""
    if valor is None or valor == "":
        return
    celda = ws.cell(row=fila, column=col)
    s = str(valor).strip()
    if "+" in s:
        celda.value = "=" + s
    else:
        try:
            celda.value = float(s)
        except ValueError:
            celda.value = s


def _escribir_bloque(ws, sucursal, dias, datos_por_dia):
    for i, fecha in enumerate(dias):
        col = COL_LUNES + i
        d = datos_por_dia.get(fecha, {})

        # Ingresos
        _escribir_valor(ws, _fila(sucursal, "efectivo_dep"), col, d.get("efectivo_depositado"))
        _escribir_valor(ws, _fila(sucursal, "td"),           col, d.get("tarjeta_debito"))
        _escribir_valor(ws, _fila(sucursal, "tc"),           col, d.get("tarjeta_credito"))
        _escribir_valor(ws, _fila(sucursal, "transf"),       col, d.get("transferencia"))

        # Egresos
        _escribir_valor(ws, _fila(sucursal, "nomina"),       col, d.get("nomina_efectivo"))
        _escribir_valor(ws, _fila(sucursal, "gasolina"),     col, d.get("gasolina"))
        _escribir_valor(ws, _fila(sucursal, "hemograma"),    col, d.get("hemograma"))
        _escribir_valor(ws, _fila(sucursal, "patologia"),    col, d.get("patologia"))
        _escribir_valor(ws, _fila(sucursal, "varios"),       col, d.get("varios"))
        _escribir_valor(ws, _fila(sucursal, "servicios"),    col, d.get("servicios"))
        _escribir_valor(ws, _fila(sucursal, "capacitacion"), col, d.get("capacitacion"))

        # Por cobrar
        pc = d.get("por_cobrar", {})
        for idx, key in enumerate(POR_COBRAR_KEYS):
            _escribir_valor(ws, _fila(sucursal, "pc_inicio") + idx, col, pc.get(key))

        # Observaciones
        obs = d.get("observaciones")
        if obs:
            ws.cell(row=_fila(sucursal, "obs"), column=col, value=obs)


def nombre_hoja(dias: list[str]) -> str:
    """'Sem del 26 al 01' (sin mes, como el original)."""
    d1 = date.fromisoformat(dias[0])
    d7 = date.fromisoformat(dias[6])
    return f"Sem del {d1.day:02d} al {d7.day:02d}"


def nombre_archivo(dias: list[str]) -> str:
    """'Semanal Baalak-Prado Octubre.xlsx' (mes del lunes)."""
    d1 = date.fromisoformat(dias[0])
    mes = MESES_ES[d1.month - 1]
    return f"Semanal Baalak-Prado {mes}.xlsx"


def generar_excel(anio: int, semana: int, dias: list[str], datos: dict) -> BytesIO:
    if not RUTA_PLANTILLA.exists():
        raise FileNotFoundError(
            f"Falta la plantilla en {RUTA_PLANTILLA}. "
            f"Copia tu Excel original ahí y renómbralo a 'plantilla_semanal.xlsx'."
        )

    wb = load_workbook(RUTA_PLANTILLA)
    ws = wb.active

    # Nombre de la hoja
    ws.title = nombre_hoja(dias)

    # Actualizar fila de fechas de cada sucursal
    for sucursal in ["Baalak", "Prado"]:
        fila_fechas = _fila(sucursal, "fechas")
        for i, fecha_iso in enumerate(dias):
            col = COL_LUNES + i
            celda = ws.cell(row=fila_fechas, column=col)
            try:
                celda.value = date.fromisoformat(fecha_iso)
            except Exception:
                celda.value = fecha_iso

    # Rellenar datos
    for sucursal in ["Baalak", "Prado"]:
        _escribir_bloque(ws, sucursal, dias, datos.get(sucursal, {}))

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf