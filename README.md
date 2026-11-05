# VetSuite Web

## Instalación en Windows 11 (servidor)

1. Instalar Python 3.13 desde https://www.python.org/downloads/windows/
   - Marcar "Add Python to PATH" durante la instalación.

2. Copiar esta carpeta al servidor (por ejemplo a `C:\vetsuite_web`).
   - NO copiar la carpeta `venv` (es de Mac).
   - NO copiar `vetsuite.db` si quieres empezar limpio.

3. Abrir CMD en la carpeta y ejecutar:

   python -m venv venv
   venv\Scripts\activate
   pip install -r requirements.txt

4. Arrancar el servidor:

   uvicorn main:app --host 0.0.0.0 --port 8000

5. Abrir el puerto 8000 en el Firewall de Windows (regla de entrada TCP).

6. Acceder desde cualquier PC de la red:

   http://IP_DEL_SERVIDOR:8000

## Arranque automático (opcional)

Crear `iniciar.bat` en la carpeta del proyecto:

    @echo off
    cd /d C:\vetsuite_web
    call venv\Scripts\activate
    uvicorn main:app --host 0.0.0.0 --port 8000

Programarlo con el Programador de tareas de Windows al iniciar sesión.
