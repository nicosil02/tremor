from tremor.lugares import resolver


def test_distrito_con_region():
    assert resolver(region="Puno", distrito="Ilave") == ("210501", "distrito")


def test_nombre_repetido_sin_pista_no_baja_a_distrito():
    assert resolver(distrito="San Juan") == (None, None)
    assert resolver(distrito="San Juan", pista="Cajamarca") == ("060112", "distrito")


def test_solo_departamento_y_alias():
    assert resolver(region="Cusco") == ("08", "departamento")
    assert resolver(region="Región Cuzco") == ("08", "departamento")
    assert resolver(provincia="Lima Metropolitana") == ("1501", "provincia")


def test_localidad_que_es_provincia():
    assert resolver(localidad="Chumbivilcas", pista="Cusco") == ("0807", "provincia")
