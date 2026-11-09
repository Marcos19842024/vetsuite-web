import os
import shutil
import zipfile
import tkinter as tk
from tkinter import filedialog, messagebox
from datetime import datetime
from pathlib import Path
import re
import tempfile

# ==========================================
# LÓGICA DE PROCESAMIENTO
# ==========================================
def calcular_quincena(fecha_inicial, fecha_final):
    """
    Calcula la quincena usando la FechaInicialPago.
    - Día 1 → primera quincena del mes (impar).
    - Día 16 → segunda quincena del mes (par).
    Fallback: FechaFinalPago.
    """
    fecha_ref = fecha_inicial or fecha_final
    if not fecha_ref:
        return None
    try:
        dt = datetime.strptime(fecha_ref, "%Y-%m-%d")
        mes = dt.month
        dia = dt.day
        if dia == 1:
            return (mes * 2) - 1
        elif dia == 16:
            return mes * 2
        else:
            # Casos raros (finiquitos, extraordinarias)
            if dia <= 15:
                return (mes * 2) - 1
            else:
                return mes * 2
    except Exception:
        return None

def extraer_datos_xml(xml_path):
    try:
        with open(xml_path, 'r', encoding='utf-8') as f:
            contenido = f.read()

        # 1. Fechas
        fecha_inicial = None
        fecha_final = None
        match_inicial = re.search(r'FechaInicialPago="([^"]+)"', contenido)
        if match_inicial:
            fecha_inicial = match_inicial.group(1).split('T')[0]
        match_final = re.search(r'FechaFinalPago="([^"]+)"', contenido)
        if match_final:
            fecha_final = match_final.group(1).split('T')[0]

        num_quincena = calcular_quincena(fecha_inicial, fecha_final)
        if not num_quincena:
            return None, None, None, None

        # 2. Clave de Cobro
        clave = None
        match_clave = re.search(r'ClavePlaza:([^\s]+)', contenido)
        if match_clave:
            clave = match_clave.group(1)

        # 3. Comprobante (puede traer varios separados por coma)
        comprobante = None
        match_comp = re.search(r'NumComprobante:([\d,\s]+)', contenido)
        if match_comp:
            # Tomamos el primer número (el más representativo)
            comprobante = match_comp.group(1).split(',')[0].strip()

        # 4. UUID
        uuid_str = None
        match_uuid = re.search(r'UUID="([^"]+)"', contenido)
        if match_uuid:
            uuid_str = match_uuid.group(1)

        if not clave or not comprobante:
            return None, None, None, None

        return num_quincena, clave, comprobante, uuid_str

    except Exception:
        return None, None, None, None

def procesar_carpeta(carpeta_procesar, carpeta_salida, claves_procesadas, nombres_generados):
    xmls = list(carpeta_procesar.glob("*.xml"))
    procesados = 0
    omitidos = 0
    duplicados = 0

    for xml_path in xmls:
        num_quincena, clave, comprobante, uuid_str = extraer_datos_xml(xml_path)

        if not num_quincena or not clave or not comprobante:
            print(f"⏭️  Omitido (no es nómina o faltan datos): {xml_path.name}")
            omitidos += 1
            continue

        pdf_path = xml_path.with_suffix('.pdf')
        if not pdf_path.exists():
            print(f"⚠️ Sin PDF asociado: {xml_path.name}")
            omitidos += 1
            continue

        # DUPLICADO: mismo UUID
        if uuid_str and uuid_str in claves_procesadas:
            print(f"⏭️  Duplicado real (UUID ya procesado): {xml_path.name}")
            duplicados += 1
            continue

        try:
            # Nombre: Quincena_Clave4_Comp4_UUID4.pdf
            clave_limpia = "".join(filter(str.isalnum, str(clave)))
            clave_corta = clave_limpia[-4:] if len(clave_limpia) >= 4 else clave_limpia
            
            comp_limpio = "".join(filter(str.isalnum, str(comprobante)))
            comp_corto = comp_limpio[-4:] if len(comp_limpio) >= 4 else comp_limpio
            
            uuid_corto = uuid_str.replace("-", "")[-4:].upper() if uuid_str else "0000"
            
            nuevo_nombre = f"{num_quincena}_{clave_corta}_{comp_corto}_{uuid_corto}.pdf"
            ruta_destino = carpeta_salida / nuevo_nombre

            # Respaldo por si el nombre ya existe (muy raro)
            contador = 1
            nombre_temporal = nuevo_nombre
            while nombre_temporal in nombres_generados or (carpeta_salida / nombre_temporal).exists():
                nombre_base = nuevo_nombre.replace('.pdf', '')
                nombre_temporal = f"{nombre_base}_{contador}.pdf"
                contador += 1

            ruta_destino = carpeta_salida / nombre_temporal

            if uuid_str:
                claves_procesadas.add(uuid_str)
            nombres_generados.add(nombre_temporal)
            
            shutil.copy2(pdf_path, ruta_destino)
            print(f"✅ {pdf_path.name} -> {nombre_temporal}")
            procesados += 1

        except Exception as e:
            print(f"💥 Error con {xml_path.name}: {e}")
            omitidos += 1

    return procesados, omitidos, duplicados

def procesar_todo(carpeta_origen):
    carpeta_origen = Path(carpeta_origen)
    carpeta_salida = carpeta_origen.parent / f"{carpeta_origen.name}_Organizadas"
    carpeta_salida.mkdir(exist_ok=True)

    claves_procesadas = set()
    nombres_generados = set()
    
    total_procesados = 0
    total_omitidos = 0
    total_duplicados = 0

    print("\n📂 Procesando archivos sueltos en la carpeta origen...")
    p, o, d = procesar_carpeta(carpeta_origen, carpeta_salida, claves_procesadas, nombres_generados)
    total_procesados += p
    total_omitidos += o
    total_duplicados += d

    zips = list(carpeta_origen.glob("*.zip"))
    if zips:
        print(f"\n📦 Encontrados {len(zips)} archivos ZIP. Descomprimiendo y procesando...")
        
        with tempfile.TemporaryDirectory(prefix="nominas_tmp_") as temp_dir:
            temp_dir_path = Path(temp_dir)
            
            for zip_path in zips:
                print(f"\n📦 Procesando ZIP: {zip_path.name}")
                extract_path = temp_dir_path / zip_path.stem
                extract_path.mkdir(exist_ok=True)
                
                try:
                    with zipfile.ZipFile(zip_path, 'r') as z:
                        for member in z.namelist():
                            if member.lower().endswith('.pdf') or member.lower().endswith('.xml'):
                                filename = os.path.basename(member)
                                source = z.open(member)
                                target = extract_path / filename
                                with open(target, 'wb') as f:
                                    shutil.copyfileobj(source, f)
                                source.close()
                    
                    p, o, d = procesar_carpeta(extract_path, carpeta_salida, claves_procesadas, nombres_generados)
                    total_procesados += p
                    total_omitidos += o
                    total_duplicados += d
                    
                except zipfile.BadZipFile:
                    print(f"❌ ZIP corrupto: {zip_path.name}")
                except Exception as e:
                    print(f"💥 Error con ZIP {zip_path.name}: {e}")

    print("\n" + "="*50)
    print("🎉 ¡Proceso terminado!")
    print(f"✅ PDFs generados: {total_procesados}")
    print(f"⏭️  Omitidos (no nómina / sin PDF): {total_omitidos}")
    print(f"⏭️  Duplicados reales (mismo UUID): {total_duplicados}")
    print(f"📁 Carpeta de salida: {carpeta_salida}")
    print("="*50)
    
    messagebox.showinfo(
        "Proceso Terminado", 
        f"PDFs generados: {total_procesados}\n"
        f"Omitidos (no nómina): {total_omitidos}\n"
        f"Duplicados (mismo UUID): {total_duplicados}\n\n"
        f"Revisa la carpeta:\n{carpeta_salida}"
    )

def main():
    root = tk.Tk()
    root.withdraw()
    print("Esperando selección de carpeta...")
    carpeta_origen = filedialog.askdirectory(
        title="Selecciona la carpeta con los ZIPs, PDFs o XMLs de nómina",
        mustexist=True
    )
    if not carpeta_origen:
        return
    print(f"Carpeta seleccionada: {carpeta_origen}")
    procesar_todo(carpeta_origen)

if __name__ == "__main__":
    main()