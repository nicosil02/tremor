

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
    # El Búho: el LLM puso "urbanos", pero la nota nombra la carga pesada: es el mismo paro nacional, Arequipa se suma
    aqp = {**base, "id": 3, "ubigeo": "04", "actor": "Transportistas urbanos", "carga": True, "reclamo": "Económicos",
           "titular": "¿Qué se sabe sobre el paro de transportistas en Arequipa por alza de combustibles?"}
    for orden in ([aqp, {**nac, "reclamo": "Económicos"}], [{**nac, "reclamo": "Económicos"}, aqp]):
        (e,) = juntar([dict(x) for x in orden])
        assert e["ubigeo"] == "00" and e["focos"] == ["04"] and e["actor"] == "Transportistas de carga"


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
    assert senal(3600, 3500, 100000, 100000, True) == "vía cerrada"
    assert senal(3600, 3500, 160000, 100000, False) == "desvío de 60 km"
    assert senal(7200, 3600, 100000, 100000, False) == "tarda 2.0 veces lo normal"


def test_causa_de_la_demora():
    import sqlite3
    from datetime import datetime
    from tremor.tiempos import causa
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE sutran_alerta (motivo, submotivo, titulo, ubigeo, via, visto_ultimo, estado_via)")
    con.execute("CREATE TABLE evento_prensa (ubigeo, accion, fecha_evento, fecha_anuncio)")
    con.execute("CREATE TABLE emergencia (ubigeo, anio, mes, tipo)")
    t, hoy = {"ubigeos": ["040128", "040104"], "via": "PE-34A"}, datetime(2026, 11, 10, 12)
    assert causa(con, t, hoy) == "causa sin confirmar"
    assert causa(con, t, hoy, lluvia=25) == "lluvia fuerte: 25 mm en 6 horas"
    con.execute("INSERT INTO evento_prensa VALUES ('0401', 'Bloqueo de vías', '2026-11-10', NULL)")
    assert causa(con, t, hoy).startswith("protesta según la prensa")
    con.execute("INSERT INTO sutran_alerta VALUES ('fenomenos_naturales', 'fenomenos_naturales.climatologico', "
                "'HUAICO EN EL KM 12', '040128', 'PE-34A', '2026-11-10T11:00:00', 'interrumpido')")
    assert causa(con, t, hoy) == "fenómeno natural según SUTRAN: Huaico en el km 12"   # SUTRAN manda sobre la prensa


def test_distritos_nombrados_en_la_provincia():
    from tremor.web import distritos_nombrados
    t = "MILES DE PROFESORES DE SAN MARTÍN DE PORRES Y LOS OLIVOS ACATARON PARO DEL 29 DE OCTUBRE"
    assert sorted(distritos_nombrados(t, "1501")) == ["150117", "150135"]
    assert distritos_nombrados(t, "150135") == []           # ya está en un distrito
    assert distritos_nombrados("Paro de docentes en Lima", "1501") == []   # "Lima" es la provincia: no es un distrito


def test_emergencia_vigente_hoy():
    import sqlite3
    from datetime import date
    from tremor.web import emergencia_hoy
    con = sqlite3.connect(":memory:")
    assert emergencia_hoy(con) == {}  # base sin decretos
    con.executescript("""CREATE TABLE decreto_emergencia (id, titulo, causas, inicio, dias, lugares);
        CREATE TABLE distrito_mes (ubigeo, m, variable, valor);
        INSERT INTO decreto_emergencia VALUES ('a', 't', 'crimen', '2026-10-20', 60, '["130801"]'), ('b', 't', 'hereda', '2026-11-01', 30, '["080907"]'),
            ('c', 't', 'conflicto', '2026-08-01', 30, '["040101"]'), ('d', 't', NULL, '2026-11-01', 60, '["150101"]');
        INSERT INTO distrito_mes VALUES ('130801', 24322, 'emergencia_crimen', 1), ('080907', 24322, 'emergencia_conflicto', 1);""")
    assert emergencia_hoy(con, date(2026, 11, 12)) == {"130801": "crimen", "080907": "conflicto"}  # la vencida y la que no es de orden interno, fuera
