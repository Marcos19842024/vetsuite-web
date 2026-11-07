"""
Descarga de adjuntos XML/PDF de Gmail vía IMAP.
Versión web con rango de fechas libre.
"""
import json
import re
import imaplib
import email
from email.header import decode_header
from pathlib import Path
from datetime import datetime, timedelta


IMAP_SERVER = "imap.gmail.com"
IMAP_PORT = 993

BASE_DIR = Path(__file__).parent
CARPETA_UPLOADS = BASE_DIR / "uploads" / "ingresos"
CARPETA_LOGS = BASE_DIR / "uploads" / "logs"
CARPETA_CACHE = BASE_DIR / "uploads" / "correos_procesados.json"


def _ruta_log():
    CARPETA_LOGS.mkdir(parents=True, exist_ok=True)
    nombre = datetime.now().strftime("sync_%Y-%m-%d_%H-%M-%S.log")
    return CARPETA_LOGS / nombre


def cargar_cache_correos():
    if CARPETA_CACHE.exists():
        try:
            with open(CARPETA_CACHE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return set(data.get("ids", []))
        except Exception:
            pass
    return set()


def guardar_cache_correos(ids):
    CARPETA_CACHE.parent.mkdir(parents=True, exist_ok=True)
    with open(CARPETA_CACHE, "w", encoding="utf-8") as f:
        json.dump({"ids": sorted(ids)}, f, ensure_ascii=False, indent=2)


def _decodificar_cabecera(valor):
    if not valor:
        return ""
    partes = decode_header(valor)
    resultado = []
    for texto, encoding in partes:
        if isinstance(texto, bytes):
            try:
                texto = texto.decode(encoding or "utf-8", errors="ignore")
            except Exception:
                texto = texto.decode("utf-8", errors="ignore")
        resultado.append(texto)
    return "".join(resultado)


def _fecha_imap_desde_iso(fecha_iso):
    """
    'YYYY-MM-DD' → 'DD-Mon-YYYY' (formato IMAP).
    Si no se puede parsear, devuelve None.
    """
    if not fecha_iso:
        return None
    try:
        dt = datetime.strptime(fecha_iso.strip()[:10], "%Y-%m-%d")
    except ValueError:
        return None
    meses = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
             "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    return f"{dt.day:02d}-{meses[dt.month-1]}-{dt.year}"


def descargar_adjuntos_gmail(usuario, password_app, etiqueta,
                              carpeta_destino=None,
                              solo_no_leidos=False,
                              filtro_remitente=None,
                              fecha_desde=None,
                              fecha_hasta=None,
                              usar_cache=True,
                              callback_log=None,
                              callback_progreso=None,
                              callback_cancelado=None):
    """
    fecha_desde, fecha_hasta: strings 'YYYY-MM-DD' (o None).
    El filtro de fecha se hace en Python sobre el header 'Date:' del correo,
    NO con SINCE/BEFORE de IMAP (Gmail los ignora o los aplica mal).
    """
    from email.utils import parsedate_to_datetime

    # print(f"[DEBUG] descargar_adjuntos_gmail fecha_desde={fecha_desde!r} fecha_hasta={fecha_hasta!r}")

    ruta_log = _ruta_log()
    archivo_log = open(ruta_log, "w", encoding="utf-8")

    def log(msg):
        timestamp = datetime.now().strftime("%H:%M:%S")
        linea = f"[{timestamp}] {msg}"
        try:
            archivo_log.write(linea + "\n")
            archivo_log.flush()
        except Exception:
            pass
        if callback_log:
            callback_log(msg)

    def progreso(texto):
        if callback_progreso:
            try:
                callback_progreso(texto)
            except Exception:
                pass

    log(f"Log guardado en: {ruta_log}")

    carpeta_destino = Path(carpeta_destino) if carpeta_destino else CARPETA_UPLOADS
    carpeta_destino.mkdir(parents=True, exist_ok=True)

    descargados = []
    errores = []
    qvet_por_archivo = {}
    no_factura_por_archivo = {}
    archivos_por_correo = {}
    info = {
        "total_correos": 0,
        "procesados": 0,
        "omitidos_cache": 0,
        "omitidos_filtros": 0,
        "omitidos_fecha": 0,
        "log": str(ruta_log),
    }

    cache_ids = cargar_cache_correos() if usar_cache else set()
    ids_procesados_esta_vez = set()

    # --- Preparsear fechas del filtro ---
    fecha_desde_dt = None
    fecha_hasta_dt = None
    if fecha_desde:
        try:
            fecha_desde_dt = datetime.strptime(fecha_desde[:10], "%Y-%m-%d").date()
            log(f"Filtro desde (header Date): {fecha_desde_dt}")
        except ValueError:
            log(f"fecha_desde invalida: {fecha_desde}")
    if fecha_hasta:
        try:
            fecha_hasta_dt = datetime.strptime(fecha_hasta[:10], "%Y-%m-%d").date()
            log(f"Filtro hasta (header Date): {fecha_hasta_dt}")
        except ValueError:
            log(f"fecha_hasta invalida: {fecha_hasta}")

    try:
        progreso("Conectando a Gmail...")
        log(f"Conectando a {IMAP_SERVER}...")
        mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        mail.login(usuario, password_app)
        log("Conexion exitosa")

        etiqueta_escaped = etiqueta.replace('"', '\\"')
        log(f"Abriendo etiqueta: {etiqueta}")
        status, data = mail.select(f'"{etiqueta_escaped}"')
        if status != "OK":
            status, data = mail.select(etiqueta_escaped)
        if status != "OK":
            errores.append(f"No se pudo abrir la etiqueta '{etiqueta}'")
            return descargados, errores, info

        # ---- Criterios de búsqueda IMAP ----
        # IMPORTANTE: NO usar SINCE/BEFORE. Gmail los ignora o los aplica
        # sobre INTERNALDATE (fecha de entrega), no sobre el header Date:.
        # El filtro de fecha real se hace en Python mas abajo.
        criterios = []
        if solo_no_leidos:
            criterios.append("UNSEEN")

        if filtro_remitente:
            rem = filtro_remitente.strip()
            if " " in rem:
                rem = f'"{rem}"'
            criterios.extend(["FROM", rem])
            log(f"Filtro de remitente (IMAP): {rem}")

        if not criterios:
            criterios = ["ALL"]

        progreso("Buscando correos en la etiqueta...")
        log(f"Buscando correos con criterios: {criterios}")
        # print(f"[DEBUG] criterios IMAP = {criterios}")
        status, data = mail.search(None, *criterios)
        if status != "OK":
            errores.append("Error al buscar correos")
            return descargados, errores, info

        ids = data[0].split()
        info["total_correos"] = len(ids)
        log(f"Correos encontrados (sin filtro de fecha): {len(ids)}")

        if not ids:
            progreso("No hay correos en la etiqueta.")
            return descargados, errores, info

        total_correos = len(ids)
        cancelado = False

        for i, num in enumerate(ids, 1):
            try:
                if callback_cancelado and callback_cancelado():
                    log("Cancelacion solicitada")
                    cancelado = True
                    break

                porcentaje = int((i / total_correos) * 100)
                progreso(
                    f"Correo {i} de {total_correos} ({porcentaje}%) | "
                    f"Descargados: {len(descargados)} archivos"
                )

                status, msg_data = mail.fetch(num, "(RFC822)")
                if status != "OK":
                    errores.append(f"Error al obtener correo {num}")
                    continue

                raw_email = msg_data[0][1] # type: ignore
                msg = email.message_from_bytes(raw_email) # type: ignore

                asunto = _decodificar_cabecera(msg.get("Subject", ""))
                remitente = _decodificar_cabecera(msg.get("From", ""))

                # ---- Filtro de fecha por header Date: (confiable) ----
                if fecha_desde_dt or fecha_hasta_dt:
                    fecha_header = msg.get("Date")
                    fecha_correo = None
                    if fecha_header:
                        try:
                            dt_correo = parsedate_to_datetime(fecha_header)
                            if dt_correo is not None:
                                fecha_correo = dt_correo.date()
                        except Exception:
                            fecha_correo = None

                    if fecha_correo is None:
                        info["omitidos_fecha"] += 1
                        log(f"[{i}/{len(ids)}] Sin Date parseable. Se omite. Asunto: {asunto[:60]}")
                        continue

                    if fecha_desde_dt and fecha_correo < fecha_desde_dt:
                        info["omitidos_fecha"] += 1
                        log(f"[{i}/{len(ids)}] Fuera de rango ({fecha_correo} < {fecha_desde_dt}). Se omite. Asunto: {asunto[:60]}")
                        continue

                    if fecha_hasta_dt and fecha_correo > fecha_hasta_dt:
                        info["omitidos_fecha"] += 1
                        log(f"[{i}/{len(ids)}] Fuera de rango ({fecha_correo} > {fecha_hasta_dt}). Se omite. Asunto: {asunto[:60]}")
                        continue

                # ---- Cache ----
                message_id = (msg.get("Message-ID") or "").strip()
                if usar_cache and message_id and message_id in cache_ids:
                    log(f"[{i}/{len(ids)}] Ya procesado (cache). Se omite.")
                    info["omitidos_cache"] += 1
                    continue

                log(f"[{i}/{len(ids)}] Asunto: {asunto}")

                qvet_detectado = ""
                no_factura_detectado = ""

                # Regex tolerante: S1, Prado, Prados (con o sin /, espacio o guion)
                # Ejemplos que debe capturar:
                #   "Factura de venta S1/08511-8363"     -> S1 + 08511
                #   "Factura de venta Prados/00265-264"  -> PRADOS + 00265
                #   "Factura de venta prados268-267"     -> PRADOS + 268
                #   "Factura de venta PRADOS 270-269"    -> PRADOS + 270
                #   "Factura de venta S1/8527"           -> S1 + 8527
                m_serie = re.search(
                    r"\b(S1|PRADOS?)\b[\/\s\-]*(\d+)",
                    asunto, re.IGNORECASE
                )
                if m_serie:
                    serie_norm = m_serie.group(1).strip().upper()
                    if serie_norm == "PRADO":
                        serie_norm = "PRADOS"
                    folio_str = m_serie.group(2).strip()
                    if folio_str.isdigit():
                        folio_str = str(int(folio_str))   # quitar ceros a la izq
                    no_factura_detectado = folio_str
                    qvet_detectado = f"{serie_norm}/{folio_str}"
                else:
                    # Fallback: buscar cualquier "SERIE-FOLIO" genérico
                    m_asunto = re.search(
                        r"([A-Za-z0-9]+)\s*-\s*(\d+)",
                        asunto, re.IGNORECASE
                    )
                    if m_asunto:
                        serie_generica = m_asunto.group(1).strip().upper()
                        folio_gen = m_asunto.group(2).strip()
                        if folio_gen.isdigit():
                            folio_gen = str(int(folio_gen))
                        no_factura_detectado = folio_gen
                        qvet_detectado = f"{serie_generica}/{folio_gen}"

                # Filtro de remitente en Python (doble seguro)
                if filtro_remitente:
                    if filtro_remitente.lower() not in remitente.lower():
                        info["omitidos_filtros"] += 1
                        continue

                adjuntos_correo = []
                for part in msg.walk():
                    if part.get_content_maintype() == "multipart":
                        continue
                    if part.get("Content-Disposition") is None:
                        continue

                    nombre_archivo = part.get_filename()
                    if not nombre_archivo:
                        continue
                    nombre_archivo = _decodificar_cabecera(nombre_archivo)

                    ext = Path(nombre_archivo).suffix.lower()
                    if ext not in (".xml", ".pdf"):
                        continue

                    payload = part.get_payload(decode=True)
                    if not payload:
                        continue

                    destino = carpeta_destino / nombre_archivo
                    contador = 1
                    while destino.exists():
                        base = Path(nombre_archivo).stem
                        destino = carpeta_destino / f"{base}_{contador}{ext}"
                        contador += 1

                    with open(destino, "wb") as f:
                        f.write(payload) # type: ignore

                    adjuntos_correo.append(destino)
                    descargados.append(destino)
                    log(f"  Adjunto: {destino.name}")

                    if qvet_detectado:
                        qvet_por_archivo[destino.name] = qvet_detectado
                    if no_factura_detectado:
                        no_factura_por_archivo[destino.name] = no_factura_detectado

                    if message_id:
                        archivos_por_correo.setdefault(message_id, []).append(str(destino))

                if adjuntos_correo:
                    info["procesados"] += 1
                    if message_id:
                        ids_procesados_esta_vez.add(message_id)

                    if solo_no_leidos:
                        mail.store(num, "+FLAGS", "\\Seen")

            except Exception as e:
                errores.append(f"Correo {num}: {e}")
                log(f"Error: {e}")

        if cancelado:
            progreso(f"Cancelado. {len(descargados)} archivos obtenidos.")
        else:
            progreso(f"Descarga completa. {len(descargados)} archivos obtenidos.")

        try:
            mail.close()
        except Exception:
            pass
        mail.logout()

        if usar_cache and ids_procesados_esta_vez:
            cache_ids.update(ids_procesados_esta_vez)
            guardar_cache_correos(cache_ids)

    except imaplib.IMAP4.error as e:
        errores.append(f"Error IMAP: {e}")
        log(f"Error IMAP: {e}")
    except Exception as e:
        errores.append(f"Error: {e}")
        log(f"Error: {e}")
    finally:
        try:
            archivo_log.close()
        except Exception:
            pass

    info["qvet_por_archivo"] = qvet_por_archivo
    info["no_factura_por_archivo"] = no_factura_por_archivo
    info["archivos_por_correo"] = archivos_por_correo
    return descargados, errores, info