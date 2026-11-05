# -*- coding: utf-8 -*-
"""
sat/procesar_xml.py
Procesa los XML descargados del SAT.
"""
import sys
from pathlib import Path

# Agregar la raíz del proyecto al path
_raiz = Path(__file__).parent.parent
if str(_raiz) not in sys.path:
    sys.path.insert(0, str(_raiz))
    
import xml.etree.ElementTree as ET
from pathlib import Path


NS = {
    "cfdi": "http://www.sat.gob.mx/cfd/4",
    "tfd": "http://www.sat.gob.mx/TimbreFiscalDigital",
}


# Mapeo de FormaPago
MAPA_FORMA_PAGO = {
    "01": "EFVO",
    "03": "TRANSF",
    "04": "TC",
    "28": "TD",
}


# Mapeo de UsoCFDI a observación
MAPA_USO_CFDI = {
    "G01": "ADQUISICION DE MERCANCIA",
    "G02": "DEVOLUCIONES",
    "G03": "GASTOS EN GENERAL",
    "I01": "CONSTRUCCIONES",
    "I02": "MOBILIARIO",
    "I03": "EQUIPO DE TRANSPORTE",
    "I04": "EQUIPO DE COMPUTO",
    "I08": "MAQUINARIA Y EQUIPO",
    "D01": "HONORARIOS MEDICOS",
    "D02": "GASTOS MEDICOS",
    "D03": "GASTOS FUNERALES",
    "D04": "DONATIVOS",
    "D05": "INTERESES HIPOTECARIOS",
    "D06": "APORTACIONES SAR",
    "D07": "SEGUROS MEDICOS",
    "D08": "TRANSPORTE ESCOLAR",
    "D09": "AHORRO",
    "D10": "COLEGIATURAS",
    "P01": "POR DEFINIR",
    "S01": "SIN EFECTOS FISCALES",
    "CP01": "COMPLEMENTO DE PAGO",
}


# Palabras clave para observación (por orden de prioridad)
PALABRAS_CLAVE = [
    ("GASOLINA", ["gasolina", "combustible", "pemex"]),
    ("INTERNET", ["internet", "telmex", "megacable", "izzi"]),
    ("CELULAR", ["celular", "telcel", "movistar", "at&t"]),
    ("ESCUELA", ["escuela", "colegiatura", "educación"]),
    ("MEMBRESIA", ["membresía", "membresia", "suscripción", "amazon"]),
    ("TRANSPORTE", ["transporte", "ado", "pasaje", "vuelo"]),
    ("HONORARIOS", ["honorarios", "consultoría", "asesoría"]),
    ("SEGUROS", ["seguro", "póliza", "poliza"]),
    ("PUBLICIDAD", ["publicidad", "marketing", "anuncio"]),
    ("GASTOS EN GENERAL", ["papelería", "limpieza", "ferretería"]),
]


def formatear_fecha(fecha_iso):
    """Convierte 'YYYY-MM-DDThh:mm:ss' a 'dd/mm/yyyy'."""
    try:
        from datetime import datetime
        dt = datetime.strptime(fecha_iso[:19], "%Y-%m-%dT%H:%M:%S")
        return dt.strftime("%d/%m/%Y")
    except Exception:
        return fecha_iso


def leer_xml_egreso(ruta_xml):
    """
    Lee un XML de Egresos y devuelve un dict con los datos.
    Devuelve None si el XML no es de tipo Ingreso.
    """
    try:
        tree = ET.parse(ruta_xml)
        root = tree.getroot()
    except Exception as e:
        return {"error": str(e), "ruta": str(ruta_xml)}

    # Filtrar por tipo de comprobante
    tipo = root.get("TipoDeComprobante", "")
    if tipo != "I":
        print(f"  [omitido] {ruta_xml.name}: tipo={tipo}")
        return None

    # Datos generales
    folio = (root.get("Folio") or "").strip()
    serie = (root.get("Serie") or "").strip()
    cp = (root.get("LugarExpedicion") or "").strip()

    # Si no hay folio, usar el UUID como fallback
    if not folio:
        # Primero extraer el UUID
        tfd_temp = root.find("cfdi:Complemento/tfd:TimbreFiscalDigital", NS)
        if tfd_temp is not None:
            uuid_temp = tfd_temp.get("UUID", "")
            if uuid_temp:
                folio = f"SIN_FOLIO-{uuid_temp[:8].upper()}"
            else:
                folio = "SIN_FOLIO"
        else:
            folio = "SIN_FOLIO"
    fecha = formatear_fecha(root.get("Fecha", ""))
    subtotal = float(root.get("SubTotal", 0) or 0)
    total = float(root.get("Total", 0) or 0)
    metodo_pago = (root.get("MetodoPago") or "").strip()
    forma_pago = (root.get("FormaPago") or "").strip()

    # Emisor
    emisor = root.find("cfdi:Emisor", NS)
    rfc_emisor = emisor.get("Rfc", "") if emisor is not None else ""
    nombre_emisor = emisor.get("Nombre", "") if emisor is not None else ""

    # Receptor
    receptor = root.find("cfdi:Receptor", NS)
    rfc_receptor = receptor.get("Rfc", "") if receptor is not None else ""
    nombre_receptor = receptor.get("Nombre", "") if receptor is not None else ""
    uso_cfdi = receptor.get("UsoCFDI", "") if receptor is not None else ""

    # UUID
    tfd = root.find("cfdi:Complemento/tfd:TimbreFiscalDigital", NS)
    uuid = tfd.get("UUID", "") if tfd is not None else ""

    # IVA e IEPS
    iva = 0.0
    ieps = 0.0
    for imp in root.findall("cfdi:Impuestos/cfdi:Traslados/cfdi:Traslado", NS):
        tipo_imp = imp.get("Impuesto", "")
        importe = float(imp.get("Importe", 0) or 0)
        if tipo_imp == "002":
            iva += importe
        elif tipo_imp == "003":
            ieps += importe

    # Conceptos
    conceptos = []
    for conc in root.findall("cfdi:Conceptos/cfdi:Concepto", NS):
        conceptos.append({
            "descripcion": conc.get("Descripcion", ""),
            "importe": float(conc.get("Importe", 0) or 0),
        })

    return {
        "tipo": tipo,
        "serie": serie,
        "folio": folio,
        "fecha": fecha,
        "subtotal": subtotal,
        "iva": iva,
        "ieps": ieps,
        "total": total,
        "metodo_pago": metodo_pago,
        "forma_pago": forma_pago,
        "rfc_emisor": rfc_emisor,
        "nombre_emisor": nombre_emisor,
        "rfc_receptor": rfc_receptor,
        "nombre_receptor": nombre_receptor,
        "uso_cfdi": uso_cfdi,
        "uuid": uuid,
        "conceptos": conceptos,
        "cp": cp,
    }


def obtener_observacion(uso_cfdi, conceptos):
    """Determina la observación según palabras clave y UsoCFDI."""
    # 1. Por palabras clave en conceptos
    for obs, palabras in PALABRAS_CLAVE:
        for conc in conceptos:
            desc = conc.get("descripcion", "").lower()
            for palabra in palabras:
                if palabra in desc:
                    return obs

    # 2. Por UsoCFDI
    return MAPA_USO_CFDI.get(uso_cfdi, "GASTOS EN GENERAL")


def obtener_forma_pago(forma_pago):
    """Convierte el código de FormaPago a texto."""
    return MAPA_FORMA_PAGO.get(forma_pago, forma_pago)


def procesar_carpeta(carpeta_xml):
    """
    Procesa todos los XML de una carpeta.
    Devuelve la lista de facturas de Ingreso.
    """
    carpeta = Path(carpeta_xml)
    if not carpeta.exists():
        return []

    xmls = list(carpeta.glob("*.xml"))
    print(f"XMLs encontrados: {len(xmls)}")

    facturas = []
    ignorados = 0
    errores = 0

    for ruta in xmls:
        resultado = leer_xml_egreso(ruta)

        if resultado is None:
            ignorados += 1
            continue

        if "error" in resultado:
            errores += 1
            print(f"  ❌ Error en {ruta.name}: {resultado['error']}")
            continue

        # Agregar campos calculados
        resultado["ruta_xml"] = str(ruta)
        resultado["observacion"] = obtener_observacion(
            resultado["uso_cfdi"], resultado["conceptos"]
        )
        forma_texto = obtener_forma_pago(resultado["forma_pago"]) or "Efectivo"
        resultado["forma_pago_texto"] = forma_texto
        
        # Si es PPD, el método es PPD
        if resultado["metodo_pago"] == "PPD":
            resultado["forma_pago_texto"] = "PPD"
        
        # Clasificar PUE/PPD
        resultado["tipo_relacion"] = "PPD" if resultado["metodo_pago"] == "PPD" else "PUE"

        facturas.append(resultado)

    print()
    print(f"Facturas de Ingreso: {len(facturas)}")
    print(f"Ignorados (no son Ingreso): {ignorados}")
    print(f"Errores: {errores}")

    return facturas


if __name__ == "__main__":
    # Procesar la carpeta de descargas
    facturas = procesar_carpeta("/tmp/sat_descargas")

    if not facturas:
        print("No hay facturas para guardar.")
        exit()

    # Guardar en el JSON
    from sat.guardar_egresos import guardar_facturas

    nuevas, duplicadas = guardar_facturas(facturas, anio=2026)

    print()
    print("=" * 80)
    print("RESULTADO")
    print("=" * 80)
    print(f"✅ Facturas nuevas:     {nuevas}")
    print(f"⏭️  Facturas duplicadas: {duplicadas}")
    print()

    # Mostrar las primeras 10
    print("Primeras 10 facturas guardadas:")
    for i, f in enumerate(facturas[:10], 1):
        print(f"{i}. Folio: {f['folio']}")
        print(f"   Fecha:        {f['fecha']}")
        print(f"   Emisor:       {f['rfc_emisor']} — {f['nombre_emisor'][:40]}")
        print(f"   Método:       {f['metodo_pago']}")
        print(f"   Forma:        {f['forma_pago_texto']}")
        print(f"   Total:        ${f['total']:,.2f}")
        print(f"   Observación:  {f['observacion']}")
        print()