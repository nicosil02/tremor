

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
def test_paro_nacional_no_se_achica():
    from tremor.web import juntar
    base = {"fecha_evento": "2026-11-16", "reclamo": None, "accion": "Paro", "actor": "Transportistas de carga", "n_notas": 1}
    piura = {**base, "id": 1, "ubigeo": "20", "titular": "Transporte de carga pesada anuncian paro en Piura"}
    nac = {**base, "id": 2, "ubigeo": "00", "titular": "Transportistas de carga anuncian paro nacional de 72 horas"}
    for orden in ([piura, nac], [nac, piura]):
        (e,) = juntar([dict(x) for x in orden])
        assert e["ubigeo"] == "00" and e["focos"] == ["20"] and "nacional" in e["titular"]
