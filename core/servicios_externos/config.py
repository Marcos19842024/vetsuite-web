import json
from pathlib import Path

RUTA = Path("servicios_externos_config.json")

DEFAULTS = {
    "conceptos": ["Incineración", "Hemograma"],
    "tipos_pago": ["Efectivo", "Transfer.", "TD", "TC"],
}


def cargar() -> dict:
    if not RUTA.exists():
        RUTA.write_text(
            json.dumps(DEFAULTS, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return {"conceptos": list(DEFAULTS["conceptos"]),
                "tipos_pago": list(DEFAULTS["tipos_pago"])}
    try:
        cfg = json.loads(RUTA.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"conceptos": list(DEFAULTS["conceptos"]),
                "tipos_pago": list(DEFAULTS["tipos_pago"])}
    cfg.setdefault("conceptos", list(DEFAULTS["conceptos"]))
    cfg.setdefault("tipos_pago", list(DEFAULTS["tipos_pago"]))
    return cfg


def guardar(cfg: dict) -> None:
    RUTA.write_text(
        json.dumps(cfg, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def agregar_concepto(valor: str) -> dict:
    cfg = cargar()
    valor = (valor or "").strip()
    if valor and valor not in cfg["conceptos"]:
        cfg["conceptos"].append(valor)
        guardar(cfg)
    return cfg