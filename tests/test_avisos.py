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
    ev = lambda i, est, f, ub, acc, emp=None, actor=None, **k: {"id": i, "estado": est, "fecha_evento": f, "ubigeo": ub, "accion": acc,
                                                                  "empresa": emp, "actor": actor, "tipo_conflicto": "otro", **k}
    web = {"eventos": [ev(1, "anunciada", "2099-11-12", "030501", "Paro"), ev(2, "ocurrida", "2026-11-08", "150101", "Marcha"),
                       ev(3, "ocurrida", "2026-11-08", "04", "Bloqueo", "Minera Las Bambas"), ev(4, "anunciada", "2026-10-02", "030506", "Paro"),
                       ev(5, "anunciada", "2099-11-10", "00", "Marcha", actor="Transportistas urbanos", urbano=True),
                       ev(6, "anunciada", "2026-11-03", "00", "Paro", actor="Transportistas de carga"),
                       ev(7, "anunciada", "2099-11-12", "030506", "Paro", suspendido=True),
                       ev(8, "ocurrida", "2026-11-08", "030506", "Bloqueo", leida=False)]}
    assert [e["clave"] for e in eventos(web, z, r"las bambas", "2026-11-01")] == ["evento:030501:Paro:2099-11-12"]  # por contenido (el id cambia al reagrupar); el bloqueo del 8 nov ya pasó: no se avisa


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


def test_provincia_nombrada():
    from tremor.web import provincia_nombrada
    assert provincia_nombrada("Frente de Defensa de Datem del Marañón anuncia movilizaciones", "1601") == "1607"
    assert provincia_nombrada("Paro en Iquitos", "1601") == "1601"
    assert provincia_nombrada("Bloqueo en Datem del Marañón", "160701") == "160701"


def test_tarjeta_png():
    import pytest
    from tremor.db import DATOS
    if not (DATOS / "distritos.geojson").exists():
        pytest.skip("sin límites distritales")
    from tremor.tarjeta import tarjeta
    png = tarjeta("Prueba", "49%", ["Nivel alto", "Octubre a diciembre"], ["080803"], {"080803"}, [], p=0.49)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


def test_juntar_focos():
    from tremor.web import juntar
    base = {"adhieren": [], "retiran": [], "puntos": [], "suspendido": False, "plazo": None, "reclamo": None}
    lima = [{**base, "fecha_evento": "2026-11-10", "ubigeo": "15", "accion": "Paro", "actor": "Transportistas urbanos", "n_notas": 5},
            {**base, "fecha_evento": "2026-11-10", "ubigeo": "00", "accion": "Paro", "actor": "Transportistas urbanos", "n_notas": 2},
            {**base, "fecha_evento": "2026-11-16", "ubigeo": "00", "accion": "Paro", "actor": "Transportistas de carga", "n_notas": 3}]
    j = juntar(lima)
    assert len(j) == 2 and [x["ubigeo"] for x in j if x["n_notas"] == 7] == ["15"]
    piura = [{**base, "fecha_evento": "2026-11-07", "ubigeo": "200604", "accion": "Bloqueo", "actor": "Pobladores", "n_notas": 2, "reclamo": "Servicios"},
             {**base, "fecha_evento": "2026-11-06", "ubigeo": "20", "accion": "Petición", "actor": "Pobladores", "n_notas": 1, "reclamo": "Servicios"}]
    assert len(juntar(piura)) == 2


def test_urbano_por_rutas():
    from tremor.web import juntar, leer
    assert leer("Lima: más de 50 empresas suspenderán rutas por protesta")["urbano"]
    base = {"adhieren": [], "retiran": [], "puntos": [], "suspendido": False, "plazo": None, "reclamo": None}
    j = juntar([{**base, "fecha_evento": "2026-11-10", "ubigeo": "15", "accion": "Paro", "actor": "Transportistas urbanos", "n_notas": 5},
                {**base, "fecha_evento": "2026-11-09", "ubigeo": "15", "accion": "Paro", "actor": "Comerciantes", "n_notas": 1, "urbano": True}])
    assert len(j) == 1 and j[0]["n_notas"] == 6


def test_cola_prioriza_carga(monkeypatch):
    import tremor.prensa.historia as H
    monkeypatch.setattr(H, "_lugares_con_operacion", lambda con: None)
    filas = [("a", "Vecinos protestan por la tala de árboles", "", "2026-11-09", None, "rss"),
             ("b", "Transportistas de carga pesada anuncian paro nacional de 72 horas", "", "2026-11-03", None, "rss")]
    assert [r[0] for r in H.ordenar(None, filas)][0] == "b"


def test_por_reglas():
    from tremor.prensa.codificar import por_reglas
    c = por_reglas("VIDEO | Transportistas de carga anuncian paro nacional de 72 horas", "En Lima el gremio...", "2026-11-03")
    assert (c["estado"], c["ubigeo"], c["actor"], c["accion"]) == ("anunciada", None, "Transportistas de carga", "Paro")
    c = por_reglas("Paro de transportistas en Lima este 10 de noviembre: conoce qué líneas", "", "2026-11-09T18:02")
    assert (c["estado"], c["fecha_evento"], c["actor"]) == ("anunciada", "2026-11-10", "Transportistas urbanos")
    c = por_reglas("Huánuco: protestas por falta de agua estallan en bloqueos y choques", "anuncio publicidad tumbes", "2026-11-06")
    assert (c["estado"], c["ubigeo"]) == ("ocurrida", "1001")
    assert por_reglas("Paro de transporte en Lima este 10 de octubre", "", "2026-11-09") is None  # nota vieja


def test_por_reglas_dia_sin_mes():
    from tremor.prensa.codificar import por_reglas
    c = por_reglas("¿Qué se sabe sobre el paro de transportistas en Arequipa?", "evalúan sumarse a una paralización convocada "
                   "a nivel nacional para los días 16, 17 y 18", "2026-11-06T11:11")
    assert (c["estado"], c["fecha_evento"], c["ubigeo"]) == ("anunciada", "2026-11-16", "0401")


def test_por_reglas_rango():
    from tremor.prensa.codificar import por_reglas
    c = por_reglas("Transportistas de carga pesada anuncian paro nacional del 16 al 18 de noviembre", "", "2026-11-03")
    assert c["fecha_evento"] == "2026-11-16" and c["ubigeo"] is None


def test_por_reglas_dia_del_mes_siguiente():
    from tremor.prensa.codificar import por_reglas
    c = por_reglas("Transportistas de Arequipa anuncian paro", "se acatará los días 3 y 4", "2026-11-28")
    assert c["fecha_evento"] == "2026-12-03"


def test_sutran_en_zona_o_ruta():
    import sqlite3
    from tremor.avisos import sutran
    from tremor.db import ahora
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE sutran_alerta (codigo, motivo, submotivo, estado_via, titulo, descripcion, ubigeo, fecha_evento, "
                "visto_ultimo)")
    con.executemany("INSERT INTO sutran_alerta VALUES (?, ?, ?, ?, ?, '', ?, '2026-11-10', ?)", [
        ("A", "humano", "humano.protestas", "interrumpido", "PROTESTA KM 20", "040108", ahora()),          # protesta en la ruta
        ("B", "fenomenos_naturales", "fenomenos_naturales.climatologico", "interrumpido", "HUAICO", "040108", ahora()),
        ("C", "accidentes", "accidentes.siniestro_vial", "restringido", "CHOQUE", "040108", ahora()),       # solo restringida: no
        ("D", "humano", "humano.protestas", "interrumpido", "PROTESTA", "100111", ahora())])                # fuera de la zona
    z = {"040108": "en su ruta, tramo Puerto de Matarani"}
    xs = {x["clave"]: x["accion"] for x in sutran(con, z, "2026-11-09")}
    assert xs == {"sutran:A": "Bloqueo de vías", "sutran:B": "Vía interrumpida por fenómeno natural"}


def test_ruta_lenta_un_aviso_por_tramo():
    import sqlite3
    from datetime import datetime
    from tremor.avisos import lentas
    con = sqlite3.connect(":memory:")
    assert lentas(con, "Bateas") == []  # sin clave de TomTom no hay tabla
    con.execute("CREATE TABLE tiempo_viaje (cliente, tramo, hora, segundos, sin_trafico, metros, cierre, senal, causa)")
    con.executemany("INSERT INTO tiempo_viaje VALUES ('Bateas', ?, ?, ?, 7200, 0, 0, ?, ?)", [
        ("Puerto de Matarani, zinc", "2026-11-10T11:00:00", 13000, "tarda 1.8 veces lo normal", "lluvia fuerte: 25 mm en 6 horas"),
        ("Puerto de Matarani, zinc", "2026-11-10T10:00:00", 12000, "tarda 1.7 veces lo normal", None),   # el mismo tramo, antes
        ("Lima, plomo", "2026-11-10T11:00:00", 7300, None, None)])                                       # normal: no avisa
    (clave, texto, _), = lentas(con, "Bateas", datetime(2026, 11, 10, 12))
    assert clave == "ruta:Puerto de Matarani, zinc:2026-11-10"
    assert "Puerto de Matarani (zinc)" in texto and "3 h 36 min" in texto and "lluvia fuerte" in texto
