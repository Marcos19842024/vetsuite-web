# shared/jobs_convenios.py
"""Thread daemon que corre el job de recordatorios de convenios una vez al día."""
import datetime
import json
import threading
import time

from core.recordatorios.convenios_generator import generar
from shared.rutas import CONVENIOS_CONFIG


_thread_iniciado = False
_ultima_ejecucion = {"fecha": None}


def _leer_config() -> dict:
    try:
        with open(CONVENIOS_CONFIG, encoding="utf-8") as f:
            cfg = json.load(f)
        return cfg.get("recordatorios", {})
    except Exception:
        return {}


def _hora_objetivo(ahora: datetime.datetime, hora_str: str) -> datetime.datetime:
    try:
        h, m = hora_str.split(":")
        h, m = int(h), int(m)
    except Exception:
        h, m = 8, 0
    objetivo = ahora.replace(hour=h, minute=m, second=0, microsecond=0)
    if ahora >= objetivo:
        objetivo += datetime.timedelta(days=1)
    return objetivo


def _ejecutar_si_toca() -> None:
    cfg = _leer_config()
    if not cfg.get("activo", True):
        return
    hoy = datetime.date.today().isoformat()
    if _ultima_ejecucion["fecha"] == hoy:
        return
    try:
        resultado = generar(dias_por_vencer=int(cfg.get("dias_por_vencer", 3)))
        _ultima_ejecucion["fecha"] = hoy # type: ignore
        print(f"[convenios_job] {datetime.datetime.now().isoformat(timespec='seconds')} "
              f"nuevos={resultado['nuevos']} omitidos={resultado['omitidos']} total={resultado['total']}")
    except Exception as e:
        print(f"[convenios_job] Error: {e}")


def _loop() -> None:
    # Al arrancar, si ya pasó la hora y no se ejecutó hoy, corre de inmediato
    cfg = _leer_config()
    if cfg.get("activo", True):
        _ejecutar_si_toca()
    while True:
        cfg = _leer_config()
        if not cfg.get("activo", True):
            time.sleep(3600)
            continue
        hora_str = cfg.get("hora", "08:00")
        ahora = datetime.datetime.now()
        objetivo = _hora_objetivo(ahora, hora_str)
        espera = (objetivo - ahora).total_seconds()
        time.sleep(max(espera, 60))
        _ejecutar_si_toca()


def iniciar() -> None:
    global _thread_iniciado
    if _thread_iniciado:
        return
    _thread_iniciado = True
    t = threading.Thread(target=_loop, name="convenios_job", daemon=True)
    t.start()
    print("[convenios_job] Thread iniciado")