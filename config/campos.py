# -*- coding: utf-8 -*-
"""
config/campos.py
Definición de campos del formulario, reglas de auto-cálculo
y constantes relacionadas.
"""

MESES_ES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]

# ============================================================
# CAMPOS DEL FORMULARIO
# ============================================================
CAMPOS = [
    # GENERAL
    ("no_factura",       "No. DE FACTURA",           "GENERAL",        "text"),
    ("qvet",             "QVET",                     "GENERAL",        "text"),
    ("fecha",            "FECHA DE EMISIÓN",         "GENERAL",        "date"),
    ("nombre",           "NOMBRE",                   "GENERAL",        "text"),
    ("rfc",              "RFC",                      "GENERAL",        "text"),
    ("fecha_impresion",  "FECHA DE TIMBRADO",        "GENERAL",        "date"),
    ("folio_fiscal",     "FOLIO FISCAL",             "GENERAL",        "text"),
    # U
    ("u_importe",        "IMPORTE",                  "U",              "number"),
    ("u_iva",            "IVA (16%)",                "U",              "number"),
    # ACCESORIOS
    ("ac_importe",       "IMPORTE",                  "ACCESORIOS",     "number"),
    ("ac_iva",           "IVA (16%)",                "ACCESORIOS",     "number"),
    # MEDICAMENTOS
    ("med_importe",      "IMPORTE (sin IVA)",        "MEDICAMENTOS",   "number"),
    ("med_sin_iva",      "SIN IVA",                  "MEDICAMENTOS",   "number"),
    ("med_iva",          "IVA (16%)",                "MEDICAMENTOS",   "number"),
    # HIGIENE
    ("hig_importe",      "IMPORTE (sin IVA)",        "HIGIENE",        "number"),
    ("hig_sin_iva",      "SIN IVA",                  "HIGIENE",        "number"),
    ("hig_iva",          "IVA 16%",                  "HIGIENE",        "number"),
    ("hig_sin_ieps_6",   "SIN IEPS 6%",              "HIGIENE",        "number"),
    ("hig_ieps_6",       "IEPS 6%",                  "HIGIENE",        "number"),
    ("hig_sin_ieps_7",   "SIN IEPS 7%",              "HIGIENE",        "number"),
    ("hig_ieps_7",       "IEPS 7%",                  "HIGIENE",        "number"),
    # ESTETICA
    ("est_importe",      "IMPORTE",                  "ESTETICA",       "number"),
    ("est_iva",          "IVA (16%)",                "ESTETICA",       "number"),
    # TRANSPORTE
    ("tra_importe",      "IMPORTE",                  "TRANSPORTE",     "number"),
    ("tra_iva",          "IVA (16%)",                "TRANSPORTE",     "number"),
    # PENSION
    ("pen_importe",      "IMPORTE",                  "PENSION",        "number"),
    ("pen_iva",          "IVA (16%)",                "PENSION",        "number"),
    # VACUNA
    ("vac_importe",      "IMPORTE",                  "VACUNA",         "number"),
    # CLINICA
    ("cli_importe",      "IMPORTE",                  "CLINICA",        "number"),
    # TOTAL
    ("total",            "TOTAL (auto)",             "TOTAL",          "number"),
    # TIPO DE PAGO
    ("efectivo",         "EFECTIVO",                 "TIPO DE PAGO",   "number"),
    ("tc",               "TARJETA CRÉDITO",          "TIPO DE PAGO",   "number"),
    ("td",               "TARJETA DÉBITO",           "TIPO DE PAGO",   "number"),
    ("cheque",           "CHEQUE",                   "TIPO DE PAGO",   "number"),
    ("transfer",         "TRANSFERENCIA",            "TIPO DE PAGO",   "number"),
    ("vale",             "VALE",                     "TIPO DE PAGO",   "number"),
]

CAMPOS_DICT = {c[0]: c for c in CAMPOS}

# Reglas de auto-cálculo de IVA/IEPS
REGLAS_AUTO = {
    "med_iva": ("med_sin_iva", 0.16),
    "hig_iva": ("hig_sin_iva", 0.16),
    "hig_ieps_6": ("hig_sin_ieps_6", 0.06),
    "hig_ieps_7": ("hig_sin_ieps_7", 0.07),
    "u_iva": ("u_importe", 0.16),
    "ac_iva": ("ac_importe", 0.16),
    "est_iva": ("est_importe", 0.16),
    "tra_iva": ("tra_importe", 0.16),
    "pen_iva": ("pen_importe", 0.16),
}

CATEGORIAS_PARA_TOTAL = [
    "u_importe", "ac_importe", "med_importe", "hig_importe",
    "est_importe", "tra_importe", "pen_importe", "vac_importe", "cli_importe",
    "med_sin_iva", "hig_sin_iva",
    "hig_sin_ieps_6", "hig_sin_ieps_7",
    "u_iva", "ac_iva", "med_iva", "hig_iva", "hig_ieps_6", "hig_ieps_7",
    "est_iva", "tra_iva", "pen_iva",
]

CAMPOS_TIPO_PAGO = ["efectivo", "tc", "td", "cheque", "transfer", "vale"]