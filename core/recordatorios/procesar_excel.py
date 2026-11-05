# core/recordatorios/procesar_excel.py
"""
Parser de Excel de Recordatorios (citas + vacunas).

Detecta el tipo por las COLUMNAS del encabezado, no por el nombre del
archivo ni de la hoja. Soporta múltiples hojas por archivo.

Columnas de CITAS (exportación VetSuite):
  FECHA, INICIO, TIPO VISITA, PROPIETARIO, MASCOTA, TELÉFONO,
  ASUNTO, AGENDA, ESTADO, COMUNICACION_IDCLIENTE, COMUNICACION_IDANIMAL

Columnas de VACUNAS / RECORDATORIOS (exportación VetSuite):
  CLIENTE, TELÉFONO 1, RAZA, TELÉFONO 2, MASCOTA, FECHA NACIMIENTO,
  ÚLTIMA VISITA, TIPO DE RECORDATORIO, VACUNA, PRÓXIMA FECHA, NHC,
  FECHA_APLICACION_MES, COMUNICACION_IDCLIENTE, COMUNICACION_IDANIMAL

Salida (compatible con el resto del módulo):
  {
    "citas":   [cliente, ...],
    "vacunas": [cliente, ...],
  }
"""

import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from openpyxl import load_workbook

from core.recordatorios.sucursales import nombre_clinica_activa

MESES_ES = {
    1: "enero", 2: "febrero", 3: "marzo", 4: "abril",
    5: "mayo", 6: "junio", 7: "julio", 8: "agosto",
    9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre",
}


# ============================================================
# Diccionario de abreviaturas
# ============================================================

ABREVIATURAS = {
    "segui": "seguimiento",
    "trat": "tratamiento",
    "mp": "medicina preventiva",
    "c": "consulta",
    "con": "consulta",
    "consulta": "consulta",
    "ciru": "cirugía",
    "b": "baño",
    "cp": "corte",
    "b y t": "baño y transporte",
    "byt": "baño y transporte",
    "b y cp": "baño y corte",
    "cp y b": "baño y corte",
    "b y c": "baño y corte",
    "c y b": "baño y corte",
    "baño medicado": "baño medicado",
    "rx": "radiografía / ultrasonido",
    "radiografia": "radiografía / ultrasonido",
}


def _expandir(texto: str) -> str:
    """Expande abreviaturas conocidas. Devuelve el texto tal cual si no matchea."""
    if not texto:
        return ""
    t = texto.strip().lower()
    if t in ABREVIATURAS:
        return ABREVIATURAS[t]
    palabras = t.split()
    if len(palabras) > 1:
        expandidas = [ABREVIATURAS.get(p, p) for p in palabras]
        return " ".join(expandidas)
    return texto


# ============================================================
# Detección de tipo por columnas
# ============================================================

def _leer_encabezado(ws) -> list[str]:
    """Devuelve la primera fila no vacía como lista de strings normalizados."""
    for row in ws.iter_rows(min_row=1, max_row=5, values_only=True):
        if row and any(c is not None for c in row):
            return [str(c).strip().upper() if c is not None else "" for c in row]
    return []


def _detectar_tipo_hoja(headers: list[str]) -> Optional[str]:
    """
    Devuelve 'citas', 'vacunas' o None según las columnas presentes.
    """
    h = set(headers)

    # Citas: PROPIETARIO + (INICIO o TIPO VISITA o ASUNTO)
    if "PROPIETARIO" in h and ("INICIO" in h or "TIPO VISITA" in h or "ASUNTO" in h):
        return "citas"

    # Vacunas: TIPO DE RECORDATORIO + VACUNA (o PRÓXIMA FECHA)
    if "TIPO DE RECORDATORIO" in h and ("VACUNA" in h or "PRÓXIMA FECHA" in h or "PROXIMA FECHA" in h):
        return "vacunas"

    # Alias por si el cliente exporta con otros nombres
    if "CLIENTE" in h and ("MASCOTA" in h) and ("VACUNA" in h or "PRÓXIMA FECHA" in h or "PROXIMA FECHA" in h):
        return "vacunas"

    return None


def detectar_tipo_excel(ruta: str) -> Optional[str]:
    """
    Compatibilidad con el router: devuelve 'citas', 'vacunas', 'mixto' o None.
    'mixto' = el archivo tiene hojas de ambos tipos.
    """
    tipos = detectar_tipos_excel(ruta)
    if not tipos:
        return None
    if len(tipos) == 1:
        return tipos[0]
    return "mixto"


def detectar_tipos_excel(ruta: str) -> list[str]:
    """Devuelve la lista de tipos detectados en todas las hojas."""
    try:
        wb = load_workbook(ruta, read_only=True, data_only=True)
    except Exception:
        return []
    tipos = set()
    try:
        for nombre in wb.sheetnames:
            ws = wb[nombre]
            headers = _leer_encabezado(ws)
            tipo = _detectar_tipo_hoja(headers)
            if tipo:
                tipos.add(tipo)
    finally:
        wb.close()
    return sorted(tipos)


# ============================================================
# Utilidades de normalización
# ============================================================

def _limpiar_telefono(raw) -> tuple[str, str]:
    """
    Devuelve (telefono_whatsapp, telefono_display).
    - Quita todo lo que no sea dígito.
    - Si son 10 dígitos, agrega 52 (México).
    - Si ya trae código de país (>10 dígitos), lo respeta.
    """
    if raw is None:
        return "", ""
    s = str(raw).strip()
    if not s:
        return "", ""
    digitos = re.sub(r"\D", "", s)
    if not digitos:
        return "", s
    if len(digitos) == 10:
        digitos = "52" + digitos
    elif not digitos.startswith("52") and len(digitos) < 10:
        digitos = "52" + digitos
    return digitos, s


def _fecha_a_datetime(raw) -> Optional[datetime]:
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw
    s = str(raw).strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d", "%d/%m/%y"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def _fecha_larga(raw) -> str:
    d = _fecha_a_datetime(raw)
    if d is None:
        return str(raw).strip() if raw is not None else ""
    return f"{d.day} de {MESES_ES[d.month]} de {d.year}"


def _fecha_corta(raw) -> str:
    d = _fecha_a_datetime(raw)
    if d is None:
        return str(raw).strip() if raw is not None else ""
    return d.strftime("%d/%m/%Y")


def _hora_str(raw) -> str:
    """Normaliza la hora a 'HH:MM'."""
    if raw is None:
        return ""
    if isinstance(raw, datetime):
        return raw.strftime("%H:%M")
    s = str(raw).strip()
    m = re.match(r"^(\d{1,2}):(\d{2})", s)
    if m:
        return f"{int(m.group(1)):02d}:{m.group(2)}"
    return s


def _col_index(headers: list[str], *nombres: str) -> Optional[int]:
    for n in nombres:
        n = n.upper()
        for i, h in enumerate(headers):
            if h == n or n in h:
                return i
    return None


# ============================================================
# Filtro de clientes referidos
# ============================================================

def _es_cliente_referido(nombre: str, telefono_raw=None) -> bool:
    """
    Los clientes referidos son citas temporales de clientes nuevos que
    aún no se registran. Suelen venir como 'CLIENTE REFERIDO X ESTUDIOS',
    'REFERIDO 1'. Se omiten del módulo de Recordatorios.
    """
    n = (nombre or "").strip().upper()
    if not n:
        return False
    if n.startswith("CLIENTE REFERIDO"):
        return True
    if n.startswith("REFERIDO"):
        return True
    if "REFERIDO" in n and ("ESTUDIOS" in n or "CLIENTE" in n):
        return True
    return False


# ============================================================
# Servicio legible (con expansión de abreviaturas)
# ============================================================

def _servicio_legible(asunto: str, estado: str, tipo_visita: str = "") -> str:
    """
    Mapea asuntos/estados a texto legible. Expande abreviaturas.

    Prioridades:
      1. TIPO VISITA "TRANSPORTE" → "transporte de clínica"
         (y si el asunto aporta, se agrega entre paréntesis).
      2. Combinaciones explícitas (baño y corte, baño medicado, etc.).
      3. Casos simples.
      4. Fallback: asunto / estado / tipo_visita / "su cita".
    """
    a = _expandir(asunto).lower()
    e = _expandir(estado).lower()
    t = _expandir(tipo_visita).lower()

    # 1. Transporte de clínica: manda el TIPO VISITA
    if "transporte" in t:
        base = "transporte de clínica"
        extra = _asunto_extra(a, e)
        return f"{base} ({extra})" if extra else base

    # 2. Combinaciones explícitas
    if "baño y corte" in a or "corte y baño" in a:
        return "baño y corte"
    if "baño medicado" in a or "medicado" in a or "medicado" in e:
        return "baño medicado"
    if "baño y transporte" in a or ("transporte" in e and "baño" in e):
        return "baño y transporte"
    if "corte y transporte" in a or ("transporte" in e and "corte" in e):
        return "corte y transporte"

    # 3. Casos simples
    if "corte" in e or a == "corte":
        return "corte"
    if "baño" in e or a == "baño":
        return "baño"
    if "medicina" in e or "medicina preventiva" in a or "medicina" in t:
        return "medicina preventiva"
    if "consulta" in e or "consulta" in t:
        return "consulta"
    if "cirug" in e or "cirugía" in a or "cirug" in t:
        return "cirugía"
    if "seguimiento" in e or "seguimiento" in a:
        return "seguimiento"
    if "radiografia" in e or "radiografía" in e or "radiografía" in a:
        return "radiografía / ultrasonido"
    if "tratamiento" in e or "tratamiento" in t:
        return "tratamiento"

    # 4. Fallback
    return _expandir(asunto) or _expandir(estado) or _expandir(tipo_visita) or "su cita"


def _asunto_extra(a: str, e: str) -> str:
    """Texto corto del asunto si aporta info distinta al estado."""
    if not a:
        return ""
    if a in ("seguimiento",) and "seguimiento" in e:
        return ""
    if a in ("medicina preventiva",) and "medicina" in e:
        return ""
    if a in ("consulta",) and "consulta" in e:
        return ""
    if a in ("cirugía",) and "cirug" in e:
        return ""
    if a in ("baño",) and "baño" in e:
        return ""
    if a in ("corte",) and "corte" in e:
        return ""
    return a


# ============================================================
# Procesar CITAS
# ============================================================

def _procesar_hoja_citas(ws, nombre_clinica: str) -> list[dict]:
    headers = _leer_encabezado(ws)
    if not headers:
        return []

    idx_fecha   = _col_index(headers, "FECHA")
    idx_inicio  = _col_index(headers, "INICIO", "HORA")
    idx_tipo    = _col_index(headers, "TIPO VISITA")
    idx_prop    = _col_index(headers, "PROPIETARIO", "CLIENTE")
    idx_mascota = _col_index(headers, "MASCOTA")
    idx_tel     = _col_index(headers, "TELÉFONO", "TELEFONO")
    idx_asunto  = _col_index(headers, "ASUNTO")
    idx_agenda  = _col_index(headers, "AGENDA")
    idx_estado  = _col_index(headers, "ESTADO")

    if idx_prop is None or idx_tel is None:
        return []

    clientes_map: dict[str, dict] = {}

    for row in ws.iter_rows(min_row=2, values_only=True):
        if not row or all(c is None for c in row):
            continue
        prop = str(row[idx_prop] or "").strip() if idx_prop is not None else ""
        if not prop:
            continue
        if _es_cliente_referido(prop, row[idx_tel] if idx_tel is not None else None):
            continue

        tel_wa, tel_disp = _limpiar_telefono(row[idx_tel] if idx_tel is not None else None)
        if not tel_wa:
            continue

        cita = {
            "fecha": _fecha_larga(row[idx_fecha] if idx_fecha is not None else None),
            "hora": _hora_str(row[idx_inicio] if idx_inicio is not None else None),
            "tipo_visita": str(row[idx_tipo] or "").strip() if idx_tipo is not None else "",
            "tipo_visita_raw": str(row[idx_tipo] or "").strip() if idx_tipo is not None else "",
            "mascota": str(row[idx_mascota] or "").strip() if idx_mascota is not None else "",
            "asunto": str(row[idx_asunto] or "").strip() if idx_asunto is not None else "",
            "agenda": str(row[idx_agenda] or "").strip() if idx_agenda is not None else "",
            "estado": str(row[idx_estado] or "").strip() if idx_estado is not None else "",
        }
        cita["servicio"] = _servicio_legible(cita["asunto"], cita["estado"], cita["tipo_visita"])

        key = tel_wa
        if key not in clientes_map:
            clientes_map[key] = {
                "nombre": prop,
                "telefono": tel_wa,
                "telefono_display": tel_disp,
                "citas": [],
                "mascotas": [],
                "mensajes": [],
                "tipo": "citas",
            }
        c = clientes_map[key]
        dup = any(
            x["mascota"] == cita["mascota"] and x["hora"] == cita["hora"] and x["fecha"] == cita["fecha"]
            for x in c["citas"]
        )
        if not dup:
            c["citas"].append(cita)
        if cita["mascota"] and cita["mascota"] not in c["mascotas"]:
            c["mascotas"].append(cita["mascota"])

    clientes = list(clientes_map.values())
    for c in clientes:
        c["citas"].sort(key=lambda x: x.get("hora", ""))
        c["mensajes"] = _generar_mensaje_citas(c, nombre_clinica)
    return clientes


def _generar_mensaje_citas(c: dict, nombre_clinica: str) -> list[str]:
    citas = c.get("citas", [])
    if not citas:
        return []

    saludo = f"Hola {c['nombre']}."
    mascotas = c.get("mascotas", [])
    n_mascotas = len(mascotas)
    n_citas = len(citas)
    fecha = citas[0].get("fecha", "")

    citas_ord = sorted(citas, key=lambda x: (x.get("hora", ""), x.get("mascota", "")))
    por_hora: dict[str, list[str]] = {}
    for cita in citas_ord:
        hora = cita.get("hora", "")
        servicio = cita.get("servicio", "")
        if servicio and servicio not in por_hora.setdefault(hora, []):
            por_hora[hora].append(servicio)

    horas = sorted(por_hora.keys())
    horas_txt = f"⏰ Hora: {horas[0]}" if len(horas) == 1 else f"⏰ Horas: {', '.join(horas)}"

    cierre = "\n\nPor favor confirme su asistencia y el servicio con anticipación."
    if n_mascotas > 1 or len(horas) > 1:
        cierre += "\n\nPara cualquier duda sobre el detalle de las citas, por favor comuníquese con nosotros."
    cierre += "\n\n¡Gracias! 🐾"

    # Caso 1: una sola cita
    if n_citas == 1:
        cita = citas_ord[0]
        cuerpo = (
            f"{nombre_clinica} le recuerda la cita de su mascota "
            f"'{cita.get('mascota', '')}' para {cita.get('servicio', '')} "
            f"a las {cita.get('hora', '')} el día {fecha}."
        )
        return [saludo, cuerpo + f"\n\n{horas_txt}" + cierre]

    # Caso 2: una sola mascota
    if n_mascotas == 1:
        mascota = mascotas[0]
        partes = []
        for hora in horas:
            servicios = por_hora[hora]
            if len(servicios) == 1:
                partes.append(f"{servicios[0]} a las {hora}")
            else:
                partes.append(f"{' / '.join(servicios)} a las {hora}")
        cuerpo = (
            f"{nombre_clinica} le recuerda la cita de su mascota '{mascota}' "
            f"tiene {n_citas} citas programadas: {' y '.join(partes)} el día {fecha}."
        )
        return [saludo, cuerpo + f"\n\n{horas_txt}" + cierre]

    # Caso 3: varias mascotas
    partes_por_mascota: dict[str, list[str]] = {}
    for cita in citas_ord:
        m = cita.get("mascota", "")
        h = cita.get("hora", "")
        s = cita.get("servicio", "")
        partes_por_mascota.setdefault(m, []).append(f"{s} a las {h}")

    for m in partes_por_mascota:
        vistas = []
        for p in partes_por_mascota[m]:
            if p not in vistas:
                vistas.append(p)
        partes_por_mascota[m] = vistas

    partes = [
        f"'{m}' para {' y '.join(ps)}"
        for m, ps in partes_por_mascota.items()
    ]
    cuerpo = (
        f"{nombre_clinica} le recuerda las citas de sus mascotas: "
        f"{', '.join(partes)} el día {fecha}."
    )
    return [saludo, cuerpo + f"\n\n{horas_txt}" + cierre]


# ============================================================
# Procesar VACUNAS
# ============================================================

def _procesar_hoja_vacunas(ws, nombre_clinica: str) -> list[dict]:
    headers = _leer_encabezado(ws)
    if not headers:
        return []

    idx_cliente = _col_index(headers, "CLIENTE", "PROPIETARIO")
    idx_tel1    = _col_index(headers, "TELÉFONO 1", "TELEFONO 1", "TELÉFONO", "TELEFONO")
    idx_tel2    = _col_index(headers, "TELÉFONO 2", "TELEFONO 2")
    idx_mascota = _col_index(headers, "MASCOTA")
    idx_tipo    = _col_index(headers, "TIPO DE RECORDATORIO", "TIPO RECORDATORIO")
    idx_vacuna  = _col_index(headers, "VACUNA", "PRODUCTO")
    idx_fecha   = _col_index(headers, "PRÓXIMA FECHA", "PROXIMA FECHA")

    if idx_cliente is None or idx_tel1 is None or idx_mascota is None:
        return []

    clientes_map: dict[str, dict] = {}

    for row in ws.iter_rows(min_row=2, values_only=True):
        if not row or all(c is None for c in row):
            continue
        cliente = str(row[idx_cliente] or "").strip() if idx_cliente is not None else ""
        if not cliente:
            continue
        if _es_cliente_referido(cliente, row[idx_tel1] if idx_tel1 is not None else None):
            continue

        tel_wa, tel_disp = _limpiar_telefono(row[idx_tel1] if idx_tel1 is not None else None)
        if not tel_wa and idx_tel2 is not None:
            tel_wa, tel_disp = _limpiar_telefono(row[idx_tel2])
        if not tel_wa:
            continue

        mascota = str(row[idx_mascota] or "").strip() if idx_mascota is not None else ""
        tipo_rec = str(row[idx_tipo] or "Vacunas").strip() if idx_tipo is not None else "Vacunas"
        vacuna = str(row[idx_vacuna] or "").strip() if idx_vacuna is not None else ""
        fecha_iso = _fecha_corta(row[idx_fecha] if idx_fecha is not None else None)

        key = tel_wa
        if key not in clientes_map:
            clientes_map[key] = {
                "nombre": cliente,
                "telefono": tel_wa,
                "telefono_display": tel_disp,
                "mascotas": [],
                "mensajes": [],
                "tipo": "vacunas",
            }
        c = clientes_map[key]

        m_obj = next((m for m in c["mascotas"] if m["nombre"] == mascota), None)
        if m_obj is None:
            m_obj = {"nombre": mascota, "recordatorios": []}
            c["mascotas"].append(m_obj)

        r_obj = next((r for r in m_obj["recordatorios"] if r["nombre"] == tipo_rec), None)
        if r_obj is None:
            r_obj = {"nombre": tipo_rec, "tipos": []}
            m_obj["recordatorios"].append(r_obj)

        if not any(t["nombre"] == vacuna and t["fecha"] == fecha_iso for t in r_obj["tipos"]):
            r_obj["tipos"].append({"nombre": vacuna, "fecha": fecha_iso})

    clientes = list(clientes_map.values())
    for c in clientes:
        c["mensajes"] = _generar_mensaje_vacunas(c, nombre_clinica)
    return clientes


def _fecha_larga_desde_corta(fecha_corta: str) -> str:
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            d = datetime.strptime(fecha_corta, fmt)
            return f"{d.day} de {MESES_ES[d.month]} de {d.year}"
        except ValueError:
            continue
    return fecha_corta


def _fechas_largas(fechas_cortas: list[str]) -> str:
    """
    ['15/10/2026', '16/10/2026'] → '15 y 16 de octubre de 2026'
    Si son meses distintos → '15 de octubre y 2 de noviembre de 2026'
    Si son años distintos → lista completa.
    """
    dts = []
    for f in fechas_cortas:
        for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
            try:
                dts.append(datetime.strptime(f, fmt))
                break
            except ValueError:
                continue
    if not dts:
        return ", ".join(fechas_cortas)

    dts = sorted(dts)
    if len(dts) == 1:
        d = dts[0]
        return f"{d.day} de {MESES_ES[d.month]} de {d.year}"

    if len({(d.year, d.month) for d in dts}) == 1:
        dias = ", ".join(str(d.day) for d in dts[:-1]) + f" y {dts[-1].day}"
        d = dts[0]
        return f"{dias} de {MESES_ES[d.month]} de {d.year}"

    if len({d.year for d in dts}) == 1:
        partes = [f"{d.day} de {MESES_ES[d.month]}" for d in dts]
        return ", ".join(partes[:-1]) + f" y {partes[-1]} de {dts[-1].year}"

    return ", ".join(f"{d.day} de {MESES_ES[d.month]} de {d.year}" for d in dts)


def _normalizar_vacuna(v: str) -> str:
    """
    Normaliza el nombre de la vacuna para comparar:
    - Colapsa espacios múltiples.
    - Quita espacios antes/después.
    - Mantiene mayúsculas originales (para el mensaje), pero la comparación
      se hace con .upper() y espacios simples.
    """
    if not v:
        return ""
    return re.sub(r"\s+", " ", v.strip())


def _generar_mensaje_vacunas(c: dict, nombre_clinica: str) -> list[str]:
    """
    Reglas:
      1. >3 mascotas y TODAS comparten exactamente el mismo conjunto
         (tipo, vacuna, fecha) → agrupar todo en una frase.
      2. >3 mascotas y comparten el mismo TIPO (aunque difieran fechas o
         vacunas) → agrupar por (tipo, fecha): "las mascotas X, Y tienen
         pendiente TIPO (VAC1 / VAC2) el día F; y las mascotas Z tienen..."
      3. Si hay diferencias de tipo → listar por mascota (sin omitir).
      4. Aviso de dudas cuando hay >1 vacuna, >1 fecha o >1 tipo.
    """
    saludo = f"Hola {c['nombre']}."

    # mascota -> { (tipo, vacuna_norm) : set(fechas) }
    mascotas_info: dict[str, dict[tuple[str, str], set[str]]] = {}
    vacunas_display: dict[tuple[str, str], str] = {}

    for m in c.get("mascotas", []):
        nombre_m = m.get("nombre", "")
        if not nombre_m:
            continue
        info = mascotas_info.setdefault(nombre_m, {})
        for r in m.get("recordatorios", []):
            tipo = r.get("nombre", "")
            for t in r.get("tipos", []):
                vacuna_raw = t.get("nombre", "")
                fecha = t.get("fecha", "")
                if not vacuna_raw:
                    continue
                vacuna_norm = _normalizar_vacuna(vacuna_raw)
                clave = (tipo, vacuna_norm)
                info.setdefault(clave, set()).add(fecha)
                if clave not in vacunas_display:
                    vacunas_display[clave] = vacuna_norm

    if not mascotas_info:
        return []

    def _canon(info: dict) -> tuple:
        tuplas = []
        for (tipo, vacuna_norm), fechas in info.items():
            for f in sorted(fechas):
                tuplas.append((tipo, vacuna_norm, f))
        return tuple(sorted(tuplas))

    canons = {nombre: _canon(info) for nombre, info in mascotas_info.items()}
    conjunto_unico = len(set(canons.values())) == 1

    # ¿Todas comparten el mismo TIPO? (aunque difieran fechas o vacunas)
    tipos_por_m = {n: set(t for (t, _) in info.keys()) for n, info in mascotas_info.items()}
    tipos_unicos = set(tuple(sorted(s)) for s in tipos_por_m.values())
    mismo_tipo = len(tipos_unicos) == 1

    # --- Caso 1: agrupar todo (conjunto exacto único) ---
    if len(mascotas_info) > 3 and conjunto_unico:
        nombres = sorted(mascotas_info.keys())
        nombres_txt = ", ".join(nombres[:-1]) + f" y {nombres[-1]}"

        todos_tipos = set()
        todas_vacunas = set()
        todas_fechas = set()
        for info in mascotas_info.values():
            for (tipo, vacuna_norm), fechas in info.items():
                todos_tipos.add(tipo)
                todas_vacunas.add(vacunas_display[(tipo, vacuna_norm)])
                todas_fechas.update(fechas)

        tipos_txt = " y ".join(sorted(todos_tipos))
        vacunas_txt = " / ".join(sorted(todas_vacunas))
        fechas_txt = _fechas_largas(sorted(todas_fechas))
        cuerpo = (
            f"{nombre_clinica} le informa que sus mascotas {nombres_txt} "
            f"tienen pendiente {tipos_txt} ({vacunas_txt}) "
            f"el día {fechas_txt}."
        )
        aviso = ""
        if len(todas_vacunas) > 1 or len(todas_fechas) > 1:
            aviso = "\n\nPara cualquier duda sobre el detalle de las vacunas, por favor comuníquese con nosotros."
        return [saludo, cuerpo + aviso, "\n🐾 ¿Quiere agendar su cita?"]

    # --- Caso 2: mismo TIPO, pero difieren fechas/vacunas → agrupar por (tipo, fecha) ---
    if len(mascotas_info) > 3 and mismo_tipo:
        # grupos: (tipo, fecha) -> { vacunas: set, mascotas: set }
        grupos: dict[tuple[str, str], dict] = {}
        for nombre_m, info in mascotas_info.items():
            for (tipo, vacuna_norm), fechas in info.items():
                for f in fechas:
                    g = grupos.setdefault((tipo, f), {"vacunas": set(), "mascotas": set()})
                    g["vacunas"].add(vacunas_display[(tipo, vacuna_norm)])
                    g["mascotas"].add(nombre_m)

        # Construir frases por grupo, ordenadas por fecha
        frases = []
        todas_fechas = set()
        todas_vacunas = set()
        todos_tipos = set()
        for (tipo, fecha), g in sorted(grupos.items(), key=lambda kv: (kv[0][1], kv[0][0])):
            mascotas_ord = sorted(g["mascotas"])
            vacunas_ord = sorted(g["vacunas"])
            if len(mascotas_ord) == 1:
                mascotas_txt = f"su mascota {mascotas_ord[0]}"
                tiene = "tiene"
            else:
                mascotas_txt = f"sus mascotas {', '.join(mascotas_ord[:-1])} y {mascotas_ord[-1]}"
                tiene = "tienen"
            vacunas_txt = " / ".join(vacunas_ord)
            frases.append(
                f"{mascotas_txt} {tiene} pendiente {tipo} ({vacunas_txt}) "
                f"el día {_fecha_larga_desde_corta(fecha)}"
            )
            todas_fechas.add(fecha)
            todas_vacunas.update(vacunas_ord)
            todos_tipos.add(tipo)

        cuerpo = f"{nombre_clinica} le informa que " + "; y ".join(frases) + "."

        aviso = ""
        if len(todas_vacunas) > 1 or len(todas_fechas) > 1:
            aviso = "\n\nPara cualquier duda sobre el detalle de las vacunas, por favor comuníquese con nosotros."
        return [saludo, cuerpo + aviso, "\n🐾 ¿Quiere agendar su cita?"]

    # --- Caso 3: diferencias de tipo o pocas mascotas → listar por mascota ---
    partes = []
    for nombre_m, info in mascotas_info.items():
        por_tipo_fecha: dict[tuple[str, str], list[str]] = {}
        for (tipo, vacuna_norm), fechas in info.items():
            for f in fechas:
                por_tipo_fecha.setdefault((tipo, f), []).append(
                    vacunas_display[(tipo, vacuna_norm)]
                )
        sub = []
        for (tipo, fecha), vacunas in sorted(por_tipo_fecha.items()):
            sub.append(f"{tipo} ({', '.join(sorted(set(vacunas)))}) el {_fecha_larga_desde_corta(fecha)}")
        if sub:
            partes.append(f"'{nombre_m}' tiene pendiente {' y '.join(sub)}")

    if not partes:
        return []

    if len(partes) == 1:
        cuerpo = f"{nombre_clinica} le informa que su mascota {partes[0]}."
    else:
        cuerpo = f"{nombre_clinica} le informa que sus mascotas: {', '.join(partes)}."

    todas_fechas = set()
    todos_tipos = set()
    for info in mascotas_info.values():
        for (tipo, _), fechas in info.items():
            todos_tipos.add(tipo)
            todas_fechas.update(fechas)

    aviso = ""
    if len(partes) > 1 or len(todas_fechas) > 1 or len(todos_tipos) > 1:
        aviso = "\n\nPara cualquier duda sobre el detalle de las vacunas, por favor comuníquese con nosotros."

    return [saludo, cuerpo + aviso, "\n🐾 ¿Quiere agendar su cita?"]


# ============================================================
# API pública
# ============================================================

def procesar_excel(ruta: str, nombre_clinica: str = None) -> dict: # type: ignore
    """
    Procesa un Excel y devuelve:
      {
        "citas":   [cliente, ...],
        "vacunas": [cliente, ...],
      }
    Puede devolver ambas listas si el archivo tiene hojas de ambos tipos.
    """
    if nombre_clinica is None:
        nombre_clinica = nombre_clinica_activa()

    resultado = {"citas": [], "vacunas": []}

    wb = load_workbook(ruta, data_only=True)
    try:
        for nombre_hoja in wb.sheetnames:
            ws = wb[nombre_hoja]
            headers = _leer_encabezado(ws)
            tipo = _detectar_tipo_hoja(headers)
            if tipo == "citas":
                resultado["citas"].extend(_procesar_hoja_citas(ws, nombre_clinica))
            elif tipo == "vacunas":
                resultado["vacunas"].extend(_procesar_hoja_vacunas(ws, nombre_clinica))
    finally:
        wb.close()

    return resultado


def regenerar_mensajes_cliente(cliente: dict, nombre_clinica: str) -> None:
    """Regenera los mensajes de un cliente según su tipo."""
    if cliente.get("tipo") == "citas":
        cliente["mensajes"] = _generar_mensaje_citas(cliente, nombre_clinica)
    else:
        cliente["mensajes"] = _generar_mensaje_vacunas(cliente, nombre_clinica)