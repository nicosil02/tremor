from tremor.contexto import claves, emparejar

OPS = [("SOUTHERN PERU COPPER CORPORATION", "Regional - Atico", "040101"), ("SOUTHERN PERU COPPER CORPORATION", "Cuajone", "180106"),
       ("MINERA AGUILA DE ORO SOCIEDAD", "Planta de Beneficio Río Seco", "190101"), ("ALTURAS MINERALS S.A.", "Baños del Indio", "230101"),
       ("CORPORACION ACEROS AREQUIPA S.A.", "Coribeni", "080101"), ("ARUNTANI S.A.C.", "Florencia - Tucari", "180201"),
       ("LA ARENA S.A.", "Corral Grande", "130101"), ("CERRO DE PASCO RESOURCES", "Quiulacocha", "190101")]


def test_claves():
    assert claves("Comunidad Campesina de Maure – Penal de Challapalca / INPE")[:3] == ["Maure", "Penal", "Challapalca"]


def test_emparejar_rechaza_parecidos():
    assert emparejar(OPS, None, "Hospital Regional II-2 JAMO") == (None, None, None)
    for empresa, unidad, ub in [("Minera Oro Negro", None, "120101"), ("Korimallco Minerals S.A.C.", "Minera Korimallko", "030101"),
                                ("Municipalidad Provincial de Arequipa", "tarifa de pasaje", "040101"), ("Cerro S.A.C.", "planta de oxígeno", "200101")]:
        assert emparejar(OPS, empresa, unidad, ub) == (None, None, None), empresa


def test_emparejar_acepta_y_elige_unidad():
    assert emparejar(OPS, "Aruntani", "Pasto Grande", "180101")[0] == "ARUNTANI S.A.C."
    assert emparejar(OPS, "Southern Perú Copper Corporation", None, "180105")[1] == "Cuajone"
    assert emparejar(OPS, "Tía María", "proyecto minero Tía María", "180101") == (None, None, None)


def test_unidad_sola_exige_nombre_entero():
    ops = [("MINERA PEÑOLES DE PERU S.A.", "Santa Cruz", "020101"), ("MINERA CHINALCO PERÚ S.A.", "Casaracra", "120801"),
           ("MINERA CHINALCO PERÚ S.A.", "Toromocho", "120806")]
    assert emparejar(ops, "MTC", "Valle Santa Lacramarca", "021801") == (None, None, None)
    assert emparejar(ops, "Chinalco", None, "120806")[1] == "Toromocho"


def test_limpiar_proyecto():
    from tremor.empresas import limpiar_proyecto
    assert limpiar_proyecto('EIA-SD DEL PROYECTO "PARQUE EÓLICO URANI Y SU INTERCONEXION AL SEIN"') == "Parque Eólico Urani"
    assert limpiar_proyecto('EIA-SD DEL PROYECTO DE EXPLORACIÓN MINERA "SUMAC WAYRA"') == "Sumac Wayra"
    assert limpiar_proyecto("ESTUDIO DE IMPACTO AMBIENTAL DETALLADO (EIAD) DEL PROYECTO TRAPICHE") == "Trapiche"


def test_unidad_que_no_tenemos_no_se_pega_a_otra_lejana():
    ops = [("REPSOL EXPLORACION PERU", "Lote 101", "160101"), ("MINERA LAS BAMBAS S.A.", "Bordebamba", "030506")]
    assert emparejar(ops, "Repsol", "Refinería La Pampilla", "070106") == (None, None, None)
    assert emparejar(ops, "MMG Las Bambas", "carretera (Ruta Nacional)", "030506")[1] == "Bordebamba"


def test_lugar_lote():
    from tremor.empresas import lugar_lote
    assert lugar_lote("área inicial del Lote 206, ubicado en la provincia de Talara del departamento de Piura, adjudicándolo") == "200701"
    assert lugar_lote("Lote Z-69, ubicado en el zócalo continental frente a Tumbes") is None
