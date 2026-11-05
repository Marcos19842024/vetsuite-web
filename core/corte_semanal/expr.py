"""Parser seguro de expresiones tipo '2345+679'. Sin eval()."""
import re

_TOKEN_NUM = re.compile(r"\d+(?:[.,]\d+)?")
_TOKEN_SUMA = re.compile(r"[+\-]")


def _a_float(tok: str) -> float:
    return float(tok.replace(",", "."))


def evaluar_expr(texto) -> float:
    """
    Suma/resta segura.
      '2345+679'    -> 3024.0
      '500'         -> 500.0
      ''  / None    -> 0.0
      '230+830+5719'-> 6779.0
      '100-20'      -> 80.0
    Ignora cualquier otro carácter.
    """
    if texto is None:
        return 0.0
    if isinstance(texto, (int, float)):
        return round(float(texto), 2)

    s = str(texto).strip()
    if not s:
        return 0.0

    # Normaliza: quita $, espacios, comas de miles tipo '1,234' -> '1234'
    # pero conserva comas decimales '1234,5'. Heurística simple:
    # si hay una sola coma y 2 dígitos después, es decimal; si hay
    # varias comas, son de miles.
    s = s.replace("$", "").replace(" ", "")
    if s.count(",") > 1:
        s = s.replace(",", "")
    elif s.count(",") == 1 and re.search(r",\d{1,2}$", s):
        s = s.replace(",", ".")

    total = 0.0
    signo = 1
    i = 0
    n = len(s)
    while i < n:
        ch = s[i]
        if ch == "+":
            signo = 1
            i += 1
            continue
        if ch == "-":
            signo = -1
            i += 1
            continue
        m = _TOKEN_NUM.match(s, i)
        if not m:
            i += 1
            continue
        total += signo * _a_float(m.group(0))
        signo = 1
        i = m.end()

    return round(total, 2)


def es_expresion(texto) -> bool:
    """True si el texto contiene un '+' o '-' entre números (para exportar como fórmula)."""
    if not isinstance(texto, str):
        return False
    s = texto.strip()
    if not s:
        return False
    # Solo considera expresión si hay + o - entre dígitos
    return bool(re.search(r"\d\s*[+\-]\s*\d", s))


def fmt_monto(v: float) -> str:
    """'3024.5' -> '$3,024.50'"""
    return f"${v:,.2f}"