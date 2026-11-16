# core/recordatorios/convenios_generator.py
"""Genera los mensajes de recordatorio de convenios vencidos / por vencer."""
import datetime
import hashlib

from core.convenios.numero_a_letras import numero_a_letras
from core.recordatorios.convenios_cache import (
    agregar, cargar, existe_id, guardar,
)
from shared.db import get_conn


def _fmt_monto(m: float) -> str:
    return f"{m:,.2f}"


def _fmt_fecha(iso: str) -> str:
    if not iso:
        return ""
    try:
        d = datetime.date.fromisoformat(iso)
        meses = ["enero", "febrero", "marzo", "abril", "mayo", "junio",
                 "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
        return f"{d.day} de {meses[d.month - 1]} de {d.year}"
    except Exception:
        return iso


def _hash_item(item: dict) -> str:
    raw = f"{item['id']}|{item['mensaje']}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _mensaje_vencido(propietario: str, mascota: str, pendiente: float, fecha: str) -> str:
    return (
        f"Hola {propietario}, le saludamos de Clínica Veterinaria Baalak.\n"
        f"Le recordamos que tiene un convenio de pago pendiente por {mascota} "
        f"con saldo de ${_fmt_monto(pendiente)}, que venció el {_fmt_fecha(fecha)}.\n"
        f"Le agradecemos pasar a recepción o comunicarse para regularizar."
    )


def _mensaje_por_vencer(propietario: str, mascota: str, pendiente: float, fecha: str) -> str:
    return (
        f"Hola {propietario}, le saludamos de Clínica Veterinaria Baalak.\n"
        f"Le recordamos que tiene un convenio de pago pendiente por {mascota} "
        f"con saldo de ${_fmt_monto(pendiente)}, que vence el {_fmt_fecha(fecha)}.\n"
        f"Le agradecemos pasar a recepción o comunicarse para regularizar."
    )


def generar(conn=None, dias_por_vencer: int = 3) -> dict:
    """Recorre los convenios y agrega los mensajes que falten al JSON.

    Devuelve {'nuevos': N, 'omitidos': M, 'total': T}.
    """
    if conn is None:
        conn = get_conn()
        cerrar = True
    else:
        cerrar = False

    hoy = datetime.date.today()
    data = cargar()
    data["generado_en"] = datetime.datetime.now().isoformat(timespec="seconds")

    # Convenios activos con vencimiento
    rows = conn.execute(
        """SELECT c.*,
                  (SELECT COALESCE(SUM(importe), 0)
                   FROM convenios_pagos
                   WHERE convenio_id = c.id AND efectuado = 1) AS pagado
           FROM convenios c
           WHERE c.estado NOT IN ('pagado', 'cancelado')
             AND c.fecha_vencimiento != ''
           ORDER BY c.fecha_vencimiento ASC"""
    ).fetchall()

    nuevos = 0
    omitidos = 0
    for r in rows:
        cid = r["id"]
        pendiente = float(r["monto_total"] or 0) - float(r["pagado"] or 0)
        if pendiente <= 0.01:
            omitidos += 1
            continue

        try:
            fv = datetime.date.fromisoformat(r["fecha_vencimiento"])
        except Exception:
            omitidos += 1
            continue

        dias = (fv - hoy).days
        if dias < 0:
            tipo = "vencido"
            dias_conteo = -dias
            mensaje = _mensaje_vencido(
                r["propietario"], r["mascota"], pendiente, r["fecha_vencimiento"]
            )
        elif dias <= dias_por_vencer:
            tipo = "por_vencer"
            dias_conteo = dias
            mensaje = _mensaje_por_vencer(
                r["propietario"], r["mascota"], pendiente, r["fecha_vencimiento"]
            )
        else:
            omitidos += 1
            continue

        item_id = f"conv-{cid}-{hoy.isoformat()}"
        if existe_id(data, item_id):
            omitidos += 1
            continue

        # Verificar que no esté descartado hoy
        ya_descartado = any(
            it.get("id") == item_id and it.get("descartado")
            for it in data.get("items", [])
        )
        if ya_descartado:
            omitidos += 1
            continue

        item = {
            "id": item_id,
            "convenio_id": cid,
            "folio": r["folio"] or "",
            "tipo": tipo,
            "propietario": r["propietario"] or "",
            "mascota": r["mascota"] or "",
            "telefono": r["telefono"] or "",
            "monto_total": float(r["monto_total"] or 0),
            "pagado": float(r["pagado"] or 0),
            "pendiente": pendiente,
            "fecha_vencimiento": r["fecha_vencimiento"],
            "dias": dias_conteo,
            "mensaje": mensaje,
            "enviado": False,
            "descartado": False,
            "hash": "",
            "generado_en": data["generado_en"],
        }
        item["hash"] = _hash_item(item)
        agregar(data, item)
        nuevos += 1

    guardar(data)
    if cerrar:
        conn.close()

    return {"nuevos": nuevos, "omitidos": omitidos, "total": len(data["items"])}