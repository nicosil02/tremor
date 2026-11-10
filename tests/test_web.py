

def test_juntar_sin_actor():
    import math
    from tremor.web import juntar
    e = {"ubigeo": "080803", "fecha_evento": "2026-11-09", "reclamo": None, "accion": "paro", "actor": math.nan, "n_notas": 1}
    assert len(juntar([e, {**e, "ubigeo": "040505"}])) == 2


def test_lugares_cliente_sin_departamentos():
    import sqlite3
    from tremor.prensa.recolectar import lugares_cliente
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE operacion (empresa, unidad, tipo, ubigeo, etapa)")
    con.execute("INSERT INTO operacion VALUES ('MINERA BATEAS S.A.C.', 'Cailloma', 'mineria', '040505', '')")
    grupos = lugares_cliente(con)
    nombres = {n for g in grupos for n in g}
    assert all(len(g) <= 8 for g in grupos) and "CAYLLOMA" in nombres and "AREQUIPA" not in nombres
