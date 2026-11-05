"""
Wrapper del SAT para la web.
Importa las funciones de sat/ (que son tu código original) y las adapta
para el flujo web (sin tkinter, sin mensajes bloqueantes).
"""
import json
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
CONFIG_FILE = BASE_DIR / "egresos_config.json"
PROVEEDORES_FILE = BASE_DIR / "proveedores_sucursal.json"
SOLICITUD_FILE = BASE_DIR / "solicitud_sat_activa.json"

DEFAULT_CONFIG = {
    "rfc_receptor": "",
    "nombre_receptor": "",
    "certificado_cer": "",
    "certificado_key": "",
    "password_fiel": "",
    "ultima_descarga": "",
}


def cargar_config():
    if not CONFIG_FILE.exists():
        return dict(DEFAULT_CONFIG)
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except Exception:
        return dict(DEFAULT_CONFIG)


def guardar_config(cfg):
    CONFIG_FILE.write_text(
        json.dumps(cfg, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def cargar_solicitud_activa():
    if not SOLICITUD_FILE.exists():
        return None
    try:
        return json.loads(SOLICITUD_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None


def guardar_solicitud_activa(datos):
    SOLICITUD_FILE.write_text(
        json.dumps(datos, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def limpiar_solicitud_activa():
    try:
        SOLICITUD_FILE.unlink(missing_ok=True)
    except Exception:
        pass


def cargar_proveedores_sucursal():
    if not PROVEEDORES_FILE.exists():
        return {}
    try:
        return json.loads(PROVEEDORES_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def guardar_proveedores_sucursal(prov):
    PROVEEDORES_FILE.write_text(
        json.dumps(prov, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def probar_fiel(rfc, cer, key, pwd):
    """
    Prueba la FIEL sin gastar solicitud.
    Devuelve {"ok": bool, "mensaje": str}.
    """
    try:
        from sat.descarga import probar_fiel as _probar
        return _probar(cer, key, pwd)
    except Exception as e:
        return {"ok": False, "mensaje": f"Error: {e}"}


def solicitar_descarga(rfc, cer, key, pwd, fecha_inicio, fecha_fin):
    """
    Solicita descarga al SAT.
    fecha_inicio, fecha_fin: datetime.
    Devuelve el dict con id_solicitud o error.
    """
    try:
        from sat.descarga import solicitar_descarga as _solicitar
        return _solicitar(cer, key, pwd, rfc, fecha_inicio, fecha_fin)
    except Exception as e:
        return {"error": str(e)}


def verificar_solicitud(rfc, cer, key, pwd, id_solicitud):
    """
    Verifica el estado de una solicitud.
    Devuelve {"estado": "1"|"2"|"3"|"4"|"5", "mensaje", "paquetes", "numero_cfdis"}.
    """
    try:
        from sat.descarga import verificar_solicitud as _verificar
        return _verificar(cer, key, pwd, rfc, id_solicitud)
    except Exception as e:
        return {"estado": "?", "mensaje": f"Error: {e}", "paquetes": [], "numero_cfdis": "0"}


def descargar_paquetes(rfc, cer, key, pwd, paquetes, carpeta_destino, id_solicitud=None):
    """
    Descarga los paquetes ZIP y extrae los XMLs.
    Devuelve lista de paths de XMLs.
    """
    try:
        from sat.descarga import descargar_paquetes as _descargar
        return _descargar(
            cer, key, pwd, rfc, paquetes,
            carpeta_destino=str(carpeta_destino),
            id_solicitud=id_solicitud,
        )
    except Exception as e:
        print(f"Error descargando paquetes: {e}")
        return []


def procesar_xmls(carpeta_xml):
    """
    Procesa todos los XMLs de una carpeta con `sat/procesar_xml.py`.
    Devuelve lista de facturas (dicts).
    """
    try:
        from sat.procesar_xml import procesar_carpeta
        return procesar_carpeta(str(carpeta_xml))
    except Exception as e:
        print(f"Error procesando XMLs: {e}")
        return []


def guardar_facturas_egresos(facturas, anio):
    """
    Guarda las facturas en SQLite (no en JSON como escritorio).
    Deduplica por UUID.
    Devuelve (nuevas, duplicadas).
    """
    from db import get_conn
    from datetime import datetime as dt

    conn = get_conn()
    nuevas = 0
    duplicadas = 0

    for f in facturas:
        uuid = (f.get("uuid") or "").strip().upper()
        if not uuid:
            continue

        existe = conn.execute(
            "SELECT 1 FROM egresos WHERE uuid = ?", (uuid,)
        ).fetchone()
        if existe:
            duplicadas += 1
            continue

        # Fecha ISO
        fecha_iso = ""
        if f.get("fecha"):
            try:
                fecha_iso = dt.strptime(
                    f["fecha"], "%d/%m/%Y"
                ).strftime("%Y-%m-%d")
            except ValueError:
                fecha_iso = ""

        # Sucursal: por proveedores_sucursal.json o default Baalak
        rfc_emisor = (f.get("rfc_emisor") or "").strip().upper()
        prov = cargar_proveedores_sucursal()
        sucursal = prov.get(rfc_emisor, "Baalak")

        conn.execute(
            "INSERT INTO egresos "
            "(fecha, folio, uuid, proveedor, rfc, total, sucursal, "
            "metodo_pago, forma_pago, notas) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                fecha_iso,
                f.get("folio", ""),
                uuid,
                f.get("nombre_emisor", ""),
                rfc_emisor,
                f.get("total", 0),
                sucursal,
                f.get("metodo_pago", "PUE"),
                f.get("forma_pago_texto", "Efectivo"),
                f.get("observacion", ""),
            ),
        )
        nuevas += 1

    conn.commit()
    conn.close()
    return nuevas, duplicadas


def marcar_animalia(uuid, rfc):
    """
    Marca un proveedor como Animalia:
    1. Actualiza el registro en SQLite (sucursal = 'Animalia').
    2. Guarda el RFC en proveedores_sucursal.json para futuras descargas.
    """
    from db import get_conn

    conn = get_conn()
    conn.execute(
        "UPDATE egresos SET sucursal = 'Animalia' WHERE uuid = ?",
        (uuid,),
    )
    conn.commit()
    conn.close()

    if rfc:
        prov = cargar_proveedores_sucursal()
        prov[rfc.strip().upper()] = "Animalia"
        guardar_proveedores_sucursal(prov)

    return True