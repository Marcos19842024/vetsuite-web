"""Convierte un monto numérico a letra para el convenio de pagos."""

UNIDADES = [
    "", "UN", "DOS", "TRES", "CUATRO", "CINCO", "SEIS", "SIETE", "OCHO",
    "NUEVE", "DIEZ", "ONCE", "DOCE", "TRECE", "CATORCE", "QUINCE",
    "DIECISEIS", "DIECISIETE", "DIECIOCHO", "DIECINUEVE", "VEINTE",
]
DECENAS = [
    "", "", "VEINTI", "TREINTA", "CUARENTA", "CINCUENTA", "SESENTA",
    "SETENTA", "OCHENTA", "NOVENTA",
]
CENTENAS = [
    "", "CIENTO", "DOSCIENTOS", "TRESCIENTOS", "CUATROCIENTOS",
    "QUINIENTOS", "SEISCIENTOS", "SETECIENTOS", "OCHOCIENTOS",
    "NOVECIENTOS",
]


def _centenas(n: int) -> str:
    if n == 0:
        return ""
    if n == 100:
        return "CIEN"
    c, resto = divmod(n, 100)
    partes = []
    if c:
        partes.append(CENTENAS[c])
    if resto < 21:
        if resto:
            partes.append(UNIDADES[resto])
    else:
        d, u = divmod(resto, 10)
        if d == 2:
            partes.append("VEINTI" + UNIDADES[u])
        else:
            texto = DECENAS[d]
            if u:
                texto += " Y " + UNIDADES[u]
            partes.append(texto)
    return " ".join(partes)


def _miles(n: int) -> str:
    if n == 0:
        return ""
    miles, resto = divmod(n, 1000)
    partes = []
    if miles == 1:
        partes.append("MIL")
    elif miles > 1:
        partes.append(_centenas(miles) + " MIL")
    if resto:
        partes.append(_centenas(resto))
    return " ".join(partes)


def numero_a_letras(monto: float) -> str:
    """Devuelve el monto en letra, ej: 5500 -> 'CINCO MIL QUINIENTOS PESOS 00/100 M.N.'"""
    # Trabajar en centavos enteros para evitar errores de punto flotante.
    centavos_totales = int(round(monto * 100))
    entero, centavos = divmod(centavos_totales, 100)
    if entero == 0:
        letra = "CERO"
    elif entero == 1:
        letra = "UN"
    else:
        millones, resto = divmod(entero, 1_000_000)
        partes = []
        if millones == 1:
            partes.append("UN MILLÓN")
        elif millones > 1:
            partes.append(_miles(millones) + " MILLONES")
        if resto:
            partes.append(_miles(resto))
        letra = " ".join(partes)
    return f"{letra} PESOS {centavos:02d}/100 M.N."