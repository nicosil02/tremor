from tremor.oefa import soles


def test_soles_dos_formatos():
    assert soles("S/.24.866,80") == 24866.8
    assert soles("S/.23,000,000.00") == 23000000.0
    assert soles("S/.324327.60") == 324327.6
    assert soles(None) is None


def test_dfai_sin_nombres_de_personas():
    import re
    from tremor.oefa import JURIDICA
    for n in ["ROSA SANCHEZ PEREZ", "JUAN SAAVEDRA RIOS", "MARTHA CHAVEZ ALVAREZ"]:
        assert not re.search(JURIDICA, n), n
    for n in ["MINERA BATEAS S.A.C", "NOREX ENERGIA S.A", "ARPE E.I.R.L", "INDUSTRIAS DESCO SAC", "MUNICIPALIDAD DISTRITAL DE OTOCA"]:
        assert re.search(JURIDICA, n), n


def test_leer_dfai():
    from tremor.oefa import leer_dfai
    # orden real de gob.pe: fecha, número, resumen, "Disponible"
    html_ = ("<time>31 de julio de 2026</time>\n<h3>Resolución N° 1320-2026-OEFA/DFAI</h3>\n<p>Se impone una multa al "
             "administrado Empresa Administradora Cerro S.A.C., por los fundamentos ...</p>\n<span>Disponible en formato PDF</span>\n"
             "<time>27 de febrero de 2023</time>\n<h3>Resolución N° 0256-2023-OEFA/DFAI</h3>\n<p>Se declara la responsabilidad "
             "administrativa sin medida correctiva a Rosa Sanchez Perez, por los ...</p>\n<span>Disponible en formato PDF</span>")
    a, b = leer_dfai(html_)
    assert b["fecha"] == "2023-02-27"  # la última de la página también entra, con su propia fecha
    assert (a["num"], a["fecha"], a["tipo"], a["administrado"]) == ("1320-2026", "2026-07-31", "multa", "EMPRESA ADMINISTRADORA CERRO S.A.C")
    assert (b["administrado"], b["resumen"], b["tipo"]) == ("PERSONA NATURAL", None, "responsabilidad")
    # redacción de 2017: "responsabilidad administrativa de"
    c, = leer_dfai("<time>29 de diciembre de 2017</time>\n<h3>Resolución N° 0072-2017-OEFA/DFAI</h3>\n<p>Declarar la "
                   "existencia de responsabilidad administrativa de Aguaytia Energy del Perú S.R.L., por la comisión de un ...</p>")
    assert c["administrado"] == "AGUAYTIA ENERGY DEL PERÚ S.R.L"
    # la DFSAI (hasta nov 2017) numera aparte
    d, = leer_dfai("<time>16 de diciembre de 2016</time>\n<h3>Resolución N°1890-2016-OEFA-DFSAI</h3>\n<p>Se declara la "
                   "responsabilidad administrativa de Fulgas Planta Envasadora S.A. al haberse ...</p>")
    assert (d["num"], d["fecha"]) == ("1890-2016-S", "2016-12-16")


def test_razon_social_cruza_formatos():
    from tremor.oefa import razon_social
    assert razon_social("MINERA BATEAS S.A.C.") == razon_social("Minera Bateas SAC") == "minera bateas"
    assert razon_social("SOUTHERN PERU COPPER CORPORATION, SUCURSAL DEL PERU") == "southern peru copper corporation"


def test_leer_tfa():
    from tremor.oefa import leer_tfa
    html_ = ("<time>19 de octubre de 2026</time>\n<h3>Resolución N° 606-2026-OEFA/TFA-SE</h3>\n<p>Se confirma la Resolución "
             "Directoral N.° 01132-2026-OEFA/DFAI del 26 de junio de 2026, en el extremo ...</p>\n<span>Disponible en formato PDF</span>")
    assert leer_tfa(html_) == [{"num": "0606-2026", "fecha": "2026-10-19", "dfai": "1132-2026", "decision": "confirma"}]


def test_leer_tfa_formato_antiguo():
    from tremor.oefa import leer_tfa
    html_ = ("<time>19 de octubre de 2018</time>\n<h3>RESOLUCIÓN N° 338-2018-OEFA/TFA-SMEPIM</h3>\n<p>PRIMERO.- CONFIRMAR el "
             "artículo N° 1 de la Resolución Directoral No 2089-2018-OEFA/DFAI del 29 de agosto de 2018, ...</p>")
    assert leer_tfa(html_) == [{"num": "0338-2018-SMEPIM", "fecha": "2018-10-19", "dfai": "2089-2018", "decision": "confirma"}]

