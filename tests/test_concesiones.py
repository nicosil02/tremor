from shapely.geometry import box, mapping

from tremor.concesiones import pisa


def test_pisa_solo_comunidades_dentro_de_la_concesion():
    com = lambda n, g, caso=None: {"properties": {"n": n, "u": "030506", "caso": caso}, "geometry": mapping(g)}
    area = box(0, 0, 10, 10)
    r = pisa(area, [com("Dentro", box(1, 1, 2, 2), "CC Dentro - Minera"), com("Mitad", box(9, 0, 11, 1)),
                    com("Roce", box(9.999, 5, 20, 6)), com("Lejos", box(20, 20, 21, 21))])
    assert [(x["n"], x["pct"]) for x in r] == [("Dentro", 1.0), ("Mitad", 0.5)]  # el roce (<1%) y la lejana no cuentan
    assert r[0]["caso"] == "CC Dentro - Minera"
