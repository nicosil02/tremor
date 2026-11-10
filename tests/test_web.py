

def test_juntar_sin_actor():
    import math
    from tremor.web import juntar
    e = {"ubigeo": "080803", "fecha_evento": "2026-11-09", "reclamo": None, "accion": "paro", "actor": math.nan, "n_notas": 1}
    assert len(juntar([e, {**e, "ubigeo": "040505"}])) == 2
