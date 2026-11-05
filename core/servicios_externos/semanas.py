from core.corte_semanal.semanas import (
    lunes_de,
    dias_de,
    semana_actual as _semana_actual,
    semana_de_fecha,
)


def semana_actual() -> tuple[int, int]:
    return _semana_actual()


def asegurar_semana(conn, anio: int, semana: int) -> dict:
    """Devuelve la fila de servicios_semanas, la crea si no existe."""
    row = conn.execute(
        "SELECT * FROM servicios_semanas WHERE anio=? AND semana=?",
        (anio, semana),
    ).fetchone()
    if row:
        return dict(row)

    desde = lunes_de(anio, semana)
    hasta = dias_de(anio, semana)[-1]
    conn.execute(
        "INSERT INTO servicios_semanas (anio, semana, desde, hasta) "
        "VALUES (?, ?, ?, ?)",
        (anio, semana, desde, hasta),
    )
    conn.commit()
    return dict(conn.execute(
        "SELECT * FROM servicios_semanas WHERE anio=? AND semana=?",
        (anio, semana),
    ).fetchone())