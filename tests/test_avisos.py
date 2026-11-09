import sqlite3

from tremor.avisos import empujan, eventos, zona


def test_empujan_descarta_lo_que_esta_bajo_lo_habitual():
    r = ("sube: medidas de fuerza en la zona en los últimos 3 meses: 1 (lo habitual, 2) · sube: casos nuevos: 3 (lo habitual, 0)"
         "; señales cerca de lo habitual · baja: algo: 5 (lo habitual, 1) · sube: en octubre suele haber más protestas")
    assert empujan(r) == ["casos nuevos: 3 (lo habitual, 0)", "en octubre suele haber más protestas"]


def test_eventos_en_la_zona_o_que_nombran_a_la_empresa():
    con = sqlite3.connect(":memory:")
    con.executescript("""
        CREATE TABLE operacion (empresa, unidad, tipo, ubigeo, etapa);
        INSERT INTO operacion VALUES ('MINERA LAS BAMBAS S.A.', 'Las Bambas', 'mineria', '030506', 'operación');
        CREATE TABLE evento_prensa (id, estado, fecha_anuncio, fecha_evento, ubigeo, accion, empresa, operacion, tipo_conflicto, actor);
        INSERT INTO evento_prensa VALUES (1, 'anunciada', '2026-11-08', '2026-11-12', '030501', 'Paro', NULL, NULL, 'otro', NULL),
                                         (2, 'ocurrida', NULL, '2026-11-08', '150101', 'Marcha', NULL, NULL, 'otro', NULL),
                                         (3, 'ocurrida', NULL, '2026-11-08', '04', 'Bloqueo', 'Minera Las Bambas', NULL, 'otro', NULL),
                                         (4, 'anunciada', '2026-10-01', '2026-10-02', '030506', 'Paro', NULL, NULL, 'otro', NULL);
        CREATE TABLE evento_nota (evento_id, nota_id); CREATE TABLE nota (id, medio, enlace, titular);
""")
    z = zona(con, "minera las bambas", {"030506": ["030501"]})
    assert z == {"030506": "Las Bambas", "030501": "Las Bambas"}
    assert [e["clave"] for e in eventos(con, z, r"las bambas", "2026-11-01")] == ["evento:1", "evento:3"]


def test_focos():
    import sqlite3
    from tremor.web import focos
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE egpp_evento (ubigeo TEXT, actor TEXT, capital_por_defecto INT)")
    con.executemany("INSERT INTO egpp_evento VALUES (?,?,?)", [("040108", "Transportistas de carga", 0)] * 3
                    + [("040128", "Transportistas de carga", 0), ("040101", "Transportistas de carga", 1)])
    assert focos(con) == {"04|Transportistas de carga": [["040108", 3], ["040128", 1]]}


def test_leer_adhesiones():
    from tremor.web import leer
    x = leer("Paro nacional de carga. La convocatoria tiene el respaldo de bases de Huacho, Barranca y Chiclayo. "
             "El gremio de Sullana no se sumará a la medida.")
    assert "150801" in x["adhieren"] and "1502" in x["adhieren"] and "1401" in x["adhieren"]
    assert "2006" in x["retiran"] and "2006" not in x["adhieren"]
    assert not x["suspendido"] and not x["urbano"]
    assert leer("Transportistas suspenden el paro tras acuerdo con el MTC")["suspendido"]
    assert leer("Movilización contra la extorsión y asesinatos de choferes")["urbano"]
    assert not leer("Alza de combustibles afecta a transportistas")["urbano"]
    assert not leer("Transporte de carga pesada y mototaxistas anuncian paro en Piura")["urbano"]
    assert leer("La protesta bloqueó vías, entre ellas un tramo de la carretera Central. Exigen agua.")["puntos"] == ["La protesta bloqueó vías, entre ellas un tramo de la carretera Central."]


def test_plazo_y_juntar():
    from datetime import date
    from tremor.web import juntar, plazo
    t = "El Comité de Lucha dio plazo hasta el jueves 12 de noviembre para que el ministro llegue a Huánuco. Paro el 4 de noviembre."
    assert plazo(t, date(2026, 11, 9)) == "2026-11-12"
    assert plazo("Paro el 4 de noviembre", date(2026, 11, 9)) is None
    base = {"fecha_evento": "2026-11-04", "reclamo": "Servicios", "adhieren": [], "retiran": [], "puntos": [], "suspendido": False, "plazo": None}
    evs = [{**base, "ubigeo": "1001", "accion": "Paro", "actor": "Pobladores", "n_notas": 20},
           {**base, "ubigeo": "10", "accion": "Paro", "actor": "Transportistas de carga", "n_notas": 1, "plazo": "2026-11-12"},
           {**base, "ubigeo": "2301", "accion": "Paro", "actor": "Pobladores", "n_notas": 3}]
    j = juntar(evs)
    assert len(j) == 2 and j[0]["n_notas"] == 21 and j[0]["ubigeo"] == "1001" and j[0]["plazo"] == "2026-11-12"


def test_dia_dicho():
    from tremor.web import dia_dicho
    assert dia_dicho("Aplazan paro y convocan marcha para el martes 20", "2026-11-20") == "2026-10-20"
    assert dia_dicho("Paro el miércoles 4", "2026-11-04") == "2026-11-04"
    assert dia_dicho("Paro nacional", "2026-11-16") == "2026-11-16"
