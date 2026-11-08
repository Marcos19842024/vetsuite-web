"""Helpers de semana ISO (lunes → domingo)."""
from datetime import date, timedelta


def lunes_de(anio: int, semana: int) -> date:
    """Lunes de la semana ISO `semana` del año `anio`."""
    # El 4 de enero siempre cae en la semana 1 (ISO 8601)
    ene4 = date(anio, 1, 4)
    lunes_sem1 = ene4 - timedelta(days=ene4.weekday())
    return lunes_sem1 + timedelta(weeks=semana - 1)


def dias_de(anio: int, semana: int) -> list[str]:
    """7 fechas YYYY-MM-DD del lunes al domingo."""
    l = lunes_de(anio, semana)
    return [(l + timedelta(days=i)).isoformat() for i in range(7)]


def semana_actual() -> tuple[int, int]:
    hoy = date.today()
    iso = hoy.isocalendar()
    return iso.year, iso.week


def semana_de_fecha(f: date) -> tuple[int, int]:
    iso = f.isocalendar()
    return iso.year, iso.week


def rango_legible(anio: int, semana: int) -> str:
    """'26 oct al 1 nov 2026'"""
    from shared.campos import MESES_ES
    dias = dias_de(anio, semana)
    l = date.fromisoformat(dias[0])
    d = date.fromisoformat(dias[6])
    mes_l = MESES_ES[l.month - 1][:3].lower()
    mes_d = MESES_ES[d.month - 1][:3].lower()
    if l.month == d.month:
        return f"{l.day} {mes_l} al {d.day} {mes_d} {d.year}"
    return f"{l.day} {mes_l} al {d.day} {mes_d} {d.year}"


def asegurar_semana(conn, anio: int, semana: int) -> dict:
    """Crea la fila en cortes_semanas si no existe. Devuelve la fila."""
    dias = dias_de(anio, semana)
    row = conn.execute(
        "SELECT * FROM cortes_semanas WHERE anio=? AND semana=?",
        (anio, semana),
    ).fetchone()
    if row:
        return dict(row)
    conn.execute(
        "INSERT INTO cortes_semanas (anio, semana, desde, hasta, estado) "
        "VALUES (?, ?, ?, ?, 'abierta')",
        (anio, semana, dias[0], dias[6]),
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM cortes_semanas WHERE anio=? AND semana=?",
        (anio, semana),
    ).fetchone()
    return dict(row)