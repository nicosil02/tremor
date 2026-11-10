

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


def test_oefa_unidades_por_nombre_normalizado():
    import sqlite3
    from tremor.web import clave_unidad, oefa_unidades
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE oefa_medida (administrado, unidad, estado, fecha)")
    con.execute("CREATE TABLE oefa_multa (administrado, unidad, soles, fecha)")
    con.execute("CREATE TABLE oefa_supervision (administrado, unidad, fecha)")
    con.execute("INSERT INTO oefa_medida VALUES ('MINERA BATEAS S.A.C.', 'ACUMULACIÓN CAILLOMA', 'INCUMPLIDA', '2024-05-01')")
    con.execute("INSERT INTO oefa_multa VALUES ('MINERA BATEAS S.A.C.', 'Acumulación Cailloma', 1000.5, '2023-01-01')")
    con.execute("INSERT INTO oefa_multa VALUES ('MINERA BATEAS S.A.C.', 'Acumulación Cailloma', NULL, '2023-01-02')")
    con.execute("INSERT INTO oefa_supervision VALUES ('OTRA S.A.', 'Acumulación Cailloma', '2025-01-01')")
    o = oefa_unidades(con)[clave_unidad("Acumulación Cailloma")]
    assert (o["m"], o["mi"], o["f"], o["s"], o["v"], o["u"]) == (1, 1, 2, 1000, 0, "2024-05-01")


def test_senal_tiempo_de_viaje():
    from tremor.tiempos import senal
    assert senal(3600, 3500, 100000, 100000, False) is None
    assert senal(3600, 3500, 100000, 100000, True) == "el ruteador marca la vía cerrada"
    assert senal(3600, 3500, 160000, 100000, False) == "el ruteador desvía por 60 km más"
    assert senal(7200, 3600, 100000, 100000, False) == "tarda 2.0 veces lo normal"
