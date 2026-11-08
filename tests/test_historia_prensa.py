import sqlite3

from tremor.prensa.historia import meses, notas_wp, ordenar


def test_meses_cruzan_el_anio():
    assert list(meses("2018-11", "2019-02")) == ["2018-11", "2018-12", "2019-01", "2019-02"]


def test_notas_wp_solo_titular_extracto_y_fecha():
    n, = notas_wp([{"date": "2019-08-05T17:51:02", "link": "https://x.pe/a/",
                    "title": {"rendered": "Agricultores acatan paro &#8211; Piura"},
                    "excerpt": {"rendered": "<p>" + "texto " * 200 + "[&hellip;]</p>"}}], "Cutivalú")
    assert n["titular"] == "Agricultores acatan paro – Piura" and n["publicado"] == "2019-08-05T17:51-05:00"
    assert len(n["resumen"]) <= 600


def test_cola_vivo_primero_y_luego_lugar_con_operacion():
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE operacion (empresa, unidad, tipo, ubigeo)")
    con.execute("INSERT INTO operacion VALUES ('X', 'Las Bambas', 'mineria', '030506')")  # Challhuahuacho
    filas = [("a", "Marcha en Trujillo", "", "2019-01-01", None, "historia:M"),
             ("b", "Paro en Challhuahuacho", "", "2018-01-01", None, "historia:M"),
             ("c", "Inauguran colegio", "", "2018-05-01", None, "historia:M"),
             ("d", "Bloqueo hoy", "", "2026-11-08", None, "feed:RPP")]
    assert [r[0] for r in ordenar(con, filas)] == ["d", "b", "a", "c"]
