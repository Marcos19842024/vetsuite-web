# -*- coding: utf-8 -*-
"""
sat/conversion.py
Convierte los archivos de la e.firma del SAT (.cer y .key)
a formatos que las librerías modernas puedan leer.

El .key del SAT viene en formato DER cifrado con 3DES.
Las librerías modernas (cryptography, cfdiclient) no pueden leerlo.
Solo openssl 1.1.1 puede desencriptarlo.
"""

import subprocess
import tempfile
from pathlib import Path


# Rutas posibles de openssl 1.1.1
RUTAS_OPENSSL_111 = [
    "/usr/local/openssl-1.1.1/bin/openssl",
    "/opt/homebrew/opt/openssl@1.1/bin/openssl",
    "/usr/local/opt/openssl@1.1/bin/openssl",
    "/usr/bin/openssl",  # Fallback al sistema
]


def _encontrar_openssl():
    """Encuentra una versión de openssl 1.1.1 o compatible."""
    for ruta in RUTAS_OPENSSL_111:
        if Path(ruta).exists():
            # Verificar la versión
            try:
                resultado = subprocess.run(
                    [ruta, "version"],
                    capture_output=True, text=True, timeout=5
                )
                if "1.1" in resultado.stdout or "1.0" in resultado.stdout:
                    return ruta
            except Exception:
                continue

    # Si no hay 1.1.1, usar la del sistema (puede no funcionar con 3DES)
    try:
        resultado = subprocess.run(
            ["openssl", "version"],
            capture_output=True, text=True, timeout=5
        )
        if resultado.returncode == 0:
            return "openssl"
    except Exception:
        pass

    return None


def _convertir_certificado_a_der(ruta_cer, ruta_salida):
    """Convierte el certificado .cer a DER."""
    openssl = _encontrar_openssl()
    if not openssl:
        raise Exception("No se encontró openssl")

    # El .cer del SAT suele estar en DER. Convertirlo a DER de nuevo no daña.
    # Pero si está en PEM, lo convierte.
    cmd = [
        openssl, "x509",
        "-in", str(ruta_cer),
        "-inform", "DER",
        "-outform", "DER",
        "-out", str(ruta_salida)
    ]

    resultado = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

    # Si falla con DER, probar con PEM
    if resultado.returncode != 0:
        cmd = [
            openssl, "x509",
            "-in", str(ruta_cer),
            "-inform", "PEM",
            "-outform", "DER",
            "-out", str(ruta_salida)
        ]
        resultado = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

    if resultado.returncode != 0:
        raise Exception(f"Error al convertir el certificado: {resultado.stderr}")

    return ruta_salida


def _convertir_key_a_sin_cifrar(ruta_key, password, ruta_salida_der):
    """
    Convierte el .key cifrado del SAT a un .key sin cifrar en DER.
    Usa openssl 1.1.1 (que sí soporta 3DES).
    """
    openssl = _encontrar_openssl()
    if not openssl:
        raise Exception("No se encontró openssl")

    # Paso 1: Convertir el .key cifrado a PEM cifrado
    ruta_pem_cifrado = Path(tempfile.gettempdir()) / "sat_key_cifrado.pem"

    cmd = [
        openssl, "pkcs8",
        "-inform", "DER",
        "-in", str(ruta_key),
        "-outform", "PEM",
        "-out", str(ruta_pem_cifrado),
        "-passin", f"pass:{password}",
    ]

    resultado = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    if resultado.returncode != 0:
        raise Exception(
            f"Error al desencriptar el .key.\n"
            f"Verifica que la contraseña sea correcta.\n"
            f"Error: {resultado.stderr}"
        )

    # Paso 2: Convertir el PEM cifrado a DER sin cifrar
    ruta_der_sin_cifrar = Path(ruta_salida_der)

    cmd = [
        openssl, "pkcs8",
        "-inform", "PEM",
        "-in", str(ruta_pem_cifrado),
        "-outform", "DER",
        "-out", str(ruta_der_sin_cifrar),
        "-nocrypt",
    ]

    resultado = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    if resultado.returncode != 0:
        raise Exception(f"Error al convertir a DER: {resultado.stderr}")

    # Limpiar archivo temporal
    try:
        ruta_pem_cifrado.unlink()
    except Exception:
        pass

    return ruta_der_sin_cifrar


def preparar_fiel(ruta_cer, ruta_key, password):
    """
    Prepara los archivos de la FIEL para usarlos con cfdiclient.

    Devuelve:
      - (ruta_cer_der, ruta_key_der)
    """
    # Carpeta temporal
    carpeta_temp = Path(tempfile.gettempdir()) / "sat_fiel"
    carpeta_temp.mkdir(parents=True, exist_ok=True)

    ruta_cer_der = carpeta_temp / "cert_der.cer"
    ruta_key_der = carpeta_temp / "key_der.key"

    # Convertir el certificado
    _convertir_certificado_a_der(ruta_cer, ruta_cer_der)

    # Convertir la llave
    _convertir_key_a_sin_cifrar(ruta_key, password, ruta_key_der)

    return ruta_cer_der, ruta_key_der