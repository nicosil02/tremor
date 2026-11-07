from tremor.egpp import operacion, tipo_conflicto


def test_tia_maria_socioambiental():
    t = "Demandan que no se continúe con el proyecto minero Tía María"
    assert tipo_conflicto("Agricultores", "Ambientales", "Agropecuario", "Empresas Privadas", t) == "socioambiental_extractivo"
    assert operacion(t) == "Tía María"


def test_huelga_minera_es_laboral():
    assert tipo_conflicto("Mineros", "Laborales", "Extractivo", "Empresas Privadas", "Aumento de sueldos") == "laboral_minero"


def test_marcha_docente_es_otro():
    assert tipo_conflicto("Docentes colegios", "Laborales", "Educativo", "Poder Ejecutivo", "Aumento de sueldos") == "otro"


def test_limite_territorial_sin_extraccion_es_otro():
    assert tipo_conflicto("Pobladores", "Territoriales", "Ciudadanía", "Poder Legislativo",
                          "Rechazo a que la localidad de Ucayali sea devuelta a Loreto") == "otro"


def test_operacion_por_nombre_propio():
    assert operacion("Rechazan a la compañía minera Mataz y exigen no otorgarle la licencia") == "Mataz"
    assert operacion("Piden mejoras salariales") is None
