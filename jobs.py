"""
Gestor de jobs con persistencia en disco.
Los jobs se guardan en jobs_state.json cada vez que se actualizan.
Al arrancar, se cargan automáticamente.
"""
import json
import threading
import uuid
from datetime import datetime, timedelta
from pathlib import Path

STATE_FILE = Path(__file__).parent / "jobs_state.json"

_jobs = {}
_lock = threading.Lock()


def _cargar_de_disco():
    """Carga los jobs del archivo JSON al arrancar."""
    global _jobs
    if not STATE_FILE.exists():
        return
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            _jobs = json.load(f)
    except Exception:
        _jobs = {}


def _guardar_a_disco():
    """Guarda los jobs al archivo JSON."""
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(_jobs, f, ensure_ascii=False, indent=2, default=str)
    except Exception as e:
        print(f"[jobs] Error guardando estado: {e}")


# Cargar al importar
_cargar_de_disco()


def crear_job():
    job_id = uuid.uuid4().hex[:12]
    with _lock:
        _jobs[job_id] = {
            "id": job_id,
            "estado": "pendiente",
            "progreso": 0,
            "mensajes": [],
            "resultado": None,
            "iniciado": datetime.now().isoformat(),
            "terminado": None,
        }
        _guardar_a_disco()
    return job_id


def actualizar_job(job_id, **kwargs):
    with _lock:
        if job_id in _jobs:
            _jobs[job_id].update(kwargs)
            _guardar_a_disco()


def agregar_mensaje(job_id, mensaje):
    with _lock:
        if job_id in _jobs:
            _jobs[job_id]["mensajes"].append(mensaje)
            if len(_jobs[job_id]["mensajes"]) > 50:
                _jobs[job_id]["mensajes"] = _jobs[job_id]["mensajes"][-50:]
            _guardar_a_disco()


def obtener_job(job_id):
    with _lock:
        job = _jobs.get(job_id)
        if not job:
            return None
        # Sanitizar: eliminar campos que no sean JSON-serializables
        limpio = {}
        for k, v in job.items():
            try:
                json.dumps(v, default=str)
                limpio[k] = v
            except (TypeError, ValueError):
                limpio[k] = str(v)
        return limpio


def limpiar_jobs_viejos(max_horas=6):
    """Borra jobs terminados hace más de max_horas."""
    limite = datetime.now() - timedelta(hours=max_horas)
    with _lock:
        a_borrar = []
        for jid, j in _jobs.items():
            if j.get("estado") in ("ok", "error", "cancelado") and j.get("terminado"):
                try:
                    t = datetime.fromisoformat(j["terminado"])
                    if t < limite:
                        a_borrar.append(jid)
                except Exception:
                    pass
        for jid in a_borrar:
            del _jobs[jid]
        if a_borrar:
            _guardar_a_disco()