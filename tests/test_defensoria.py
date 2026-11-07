"""Pruebas del recolector de la Defensoría con títulos y nombres de archivo reales del sitio."""
import pytest

from tremor.defensoria.catalogo import es_reporte_mensual, leer_portada, num_pista

U = "https://www.defensoria.gob.pe/wp-content/uploads/"
W = "http://www.defensoria.gob.pe/modules/Downloads/conflictos/"


@pytest.mark.parametrize("titulo, url, esperado", [
    ("Reporte de conflictos sociales n.° 270 – agosto 2026", U + "2026/09/Reporte-de-conflictos-sociales-n-270.pdf", 270),
    ("Reporte de conflictos sociales n.º 271 – septiembre 2026", U + "2026/10/RCS_271_setiembre_2026.html", 271),
    ("Reporte de conflictos sociales n.° 263 – enero 2026", U + "2026/02/10.pdf", 263),  # el archivo no dice nada
    ("Conflictos Sociales", U + "2018/05/conflictos_sociales42.pdf", 42),
    ("", U + "2025/03/RCS-N%C2%B0-252-Feb-2025.pdf", 252),
    ("", W + "2009/reporte-64.pdf", 64),
    ("", W + "2008/Conflictos-055.pdf", 55),
    ("", W + "2009/conflictos_reporte_61_marzo2009.pdf", 61),
    ("", W + "2010/cronologia/cronologia-258.pdf", None),
    ("", "http://www.defensoria.gob.pe/conflictos-sociales/objetos/descargas/45reporte_70.pdf", 70),
])
def test_num_pista(titulo, url, esperado):
    assert num_pista(titulo, url) == esperado


@pytest.mark.parametrize("titulo, url, esperado", [
    ("Reporte Mensual de Conflictos Sociales N° 179", U + "2019/02/x.pdf", True),
    ("", W + "2010/reporte-80.pdf", True),
    ("Reporte Igualdad y No Violencia n.° 80 – septiembre 2026", U + "2026/10/Reporte-Igualdad-y-No-Violencia-80.pdf", False),
    ("Crisis política y conflicto social: Reporte de personas heridas", U + "2023/05/Reporte-de-personas-heridas.pdf", False),
])
def test_es_reporte_mensual(titulo, url, esperado):
    assert es_reporte_mensual(titulo, url) is esperado


# Fragmentos reales del inicio de cada reporte, uno por época.
@pytest.mark.parametrize("texto, esperado", [
    ("Defensoría del Pueblo REPORTE Nº 5 CONFLICTOS DE DISTINTA INTENSIDAD ENTRE POBLACIÓN Y"
     " ENTIDADES PÚBLICAS CONOCIDOS POR LA DEFENSORÍA DEL PUEBLO Al 19 de julio de 2004", (5, 7, 2004)),
    ("UNIDAD DE CONFLICTOS SOCIALES REPORTE DE CONFLICTOS SOCIALES REPORTE Nº 42 CONFLICTOS SOCIALES"
     " CONOCIDOS POR LA DEFENSORÍA DEL PUEBLO1 Al 30 de agosto del 2007", (42, 8, 2007)),
    ("DIRECCIÓN DE LA UNIDAD DE CONFLICTOS SOCIALES 60°REPORTE DE CONFLICTOS SOCIALES"
     " Al 28 de febrero del 2009", (60, 2, 2009)),
    ("REPORTE DE CONFLICTOS SOCIALES Nº 95 Enero 2012 DEFENSORÍA DEL PUEBLO", (95, 1, 2012)),
    ("REPORTE DE CONFLICTOS SOCIALES N.° 179 Enero 2019 DEFENSORÍA DEL PUEBLO", (179, 1, 2019)),
    ("Reporte Mensual de\nConflictos\nSociales\nN.° 271\nSETIEMBRE 2026", (271, 9, 2026)),
])
def test_leer_portada(texto, esperado):
    assert leer_portada(texto) == esperado


from tremor.defensoria.extraer import contar_lista, fichas, totales


@pytest.mark.parametrize("texto, esperado", [
    ("Se da cuenta de 180 conflictos sociales: 133 activos y 47 latentes (Pág. 5).",
     {"total": 180, "activos": 133, "latentes": 47}),
    ("Se da cuenta de 206 conflictos sociales: 161activos, de los cuales 90 están en proceso de diálogo, y 45 latentes.",
     {"total": 206, "activos": 161, "latentes": 45, "en_dialogo": 90}),
    ("Se da cuenta de 193 conflictos sociales registrados: 144 activos (de los cuales 59 están en diálogo) y 49 latentes ."
     " Acciones colectivas de protesta registradas: 151 .",
     {"total": 193, "activos": 144, "latentes": 49, "en_dialogo": 59, "acciones": 151}),
    ("Se da cuenta de 153 conflictos activos y 75 conflictos latentes (P. 5).",
     {"activos": 153, "latentes": 75, "total": 228}),
])
def test_totales(texto, esperado):
    assert totales(texto) == esperado


FICHA_2019 = """Amazonas
Tipo: Socioambiental.
Ingresó como caso nuevo: Diciembre de 2008.
Caso: La Organización para el Desarrollo de las Comunidades
Fronterizas de El Cenepa (ODECOFROC) se opone a la actividad minera.
Ubicación: Distrito de El Cenepa, provincia de Condorcanqui,
región Amazonas.
Actores primarios: ODECOFROC, Compañía Minera Afrodita S.A.C.
Actores secundarios: Ministerio del Ambiente (MINAM).
Actores terciarios: Defensoría del Pueblo.
NO HAY DIÁLOGO
El 15 de enero, la comunidad denunció el ingreso de mineros.
"""

FICHA_2026 = """Wampis - Minería ilegal (Amazonas)
Tipo: Socioambiental
Código: 1053-0717
Desescalamiento
Ubicación:
 Distrito de Río Santiago, provincia de Condorcanqui
Ingreso al registro:
 Julio 2017
Competencia:
 Gobierno nacional
Fase / Diálogo:
 Desescalamiento · No Hay Diálogo
Actuaciones DP:
 2
Caso:
El Gobierno Territorial Autónomo de la Nación Wampis expresó su preocupación por la minería ilegal.
Actores primarios:
Gobierno Territorial Autónomo de la Nación Wampis
Actores secundarios:
Gobierno Regional de Amazonas
Actores terciarios:
Defensoría del Pueblo
NO HAY DIÁLOGO
El 29 de setiembre, la Defensoría convocó una reunión de coordinación.
"""


def test_ficha_2019():
    [f] = fichas(FICHA_2019)
    assert f["departamento"] == "Amazonas" and f["tipo"] == "Socioambiental"
    assert f["ubicacion"].startswith("Distrito de El Cenepa")
    assert f["dialogo"] == "NO HAY DIÁLOGO" and f["hechos_mes"].startswith("El 15 de enero")
    assert f["actores_terciarios"] == "Defensoría del Pueblo"


def test_ficha_2026():
    [f] = fichas(FICHA_2026)
    assert f["codigo"] == "1053-0717" and f["nombre"] == "Wampis - Minería ilegal"
    assert f["fase"] == "desescalamiento" and f["competencia"] == "Gobierno nacional"
    assert f["hechos_mes"].startswith("El 29 de setiembre")


def test_contar_lista():
    assert contar_lista("03/2025\nApurímac\nTapayrihua\nSocioambiental\n06/2022\nApurímac\nChuicuni\nSocioambiental") == 2
    assert contar_lista("1.\n\nAbr-22\nAmazonas\nKuélap\n2.\n\nOct-22\nAmazonas\nX\n") == 2


def test_enlace():
    from tremor.defensoria.validar import _con_tokens, calcular_idf, enlazar_reporte
    viejo = {"departamento": "Puno", "descripcion": "La comunidad campesina de Ocuviri acusa a la minera Arasi de contaminar el río.",
             "ubicacion": "Distrito de Ocuviri, provincia de Lampa", "actores_primarios": "CC Ocuviri, Minera Arasi"}
    otro = {"departamento": "Puno", "descripcion": "La comunidad campesina de Tumpa se opone a la minera California.",
            "ubicacion": "Distrito de Tumpa", "actores_primarios": "CC Tumpa, Minera California"}
    casos = {1: _con_tokens(viejo), 2: _con_tokens(otro), 3: _con_tokens(dict(viejo, departamento="Cusco")),
             4: _con_tokens(dict(otro, codigo="1053-0717"))}
    idf = calcular_idf([viejo["descripcion"], otro["descripcion"], "La comunidad campesina reclama a la minera."] * 3)
    reescrito = dict(viejo, descripcion="Pobladores de Ocuviri demandan a la empresa Arasi cumplir compromisos.")
    nuevo = {"departamento": "Puno", "descripcion": "Comerciantes del mercado de Juliaca reclaman al municipio."}
    con_codigo = {"departamento": "Lima", "codigo": "1053-0717", "descripcion": "otro texto"}
    assert enlazar_reporte([reescrito, nuevo, con_codigo], casos, idf) == [(1, enlazar_reporte([reescrito], casos, idf)[0][1]), (None, 0.0), (4, 1.0)]


def test_victimas_declaradas():
    from tremor.defensoria.extraer import victimas_declaradas
    assert victimas_declaradas("De acuerdo con el SIMCO en el mes se registró cuatro heridos.") == {"fallecidos": 0, "heridos": 4}
    assert victimas_declaradas("se registró 11 personas heridas y un fallecido") == {"fallecidos": 1, "heridos": 11}


def test_fecha_de_protesta():
    from tremor.defensoria.extraer import _FECHA
    assert _FECHA.match("01/06/2017").group(1) == "01/06/2017"
    assert _FECHA.match("5 de octubre").group(1) == "5 de octubre"
    assert _FECHA.match("Plantón") is None


@pytest.mark.parametrize("texto, esperado", [
    ("Asunto de Gobierno nacional", "Asuntos de gobierno nacional"),
    ("Socioambiental. HAY DIÁLOGO", "Socioambiental"),
    ("Por asuntos de gobierno local", "Asuntos de gobierno local"),
    ("Demarcación Territorial", "Demarcación territorial"),
    ("Conflictos en Universidades", "Conflictos en universidades"),
])
def test_tipo_canonico(texto, esperado):
    from tremor.defensoria.extraer import tipo_canonico
    assert tipo_canonico(texto) == esperado


def test_ficha_a_dos_columnas():
    # PDF 2012-2024: la columna derecha (marcada) trae el diálogo y los hechos, aunque quede antes de los actores.
    from tremor.defensoria.extraer import DERECHA
    texto = ("Tipo: Socioambiental.\nCaso: Comunidades Wampis exigen el retiro de mineros ilegales.\n"
             + DERECHA + "HAY DIÁLOGO\n" + DERECHA + "No se registraron nuevos hechos durante el mes.\n"
             "Ubicación: Distrito de Río Santiago.\nActores primarios: Comunidades Wampis.\n"
             "Actores terciarios: Defensoría del Pueblo.\n")
    [f] = fichas(texto)
    assert f["dialogo"] == "HAY DIÁLOGO" and f["hechos_mes"].startswith("No se registraron")
    assert f["actores_terciarios"] == "Defensoría del Pueblo"


def test_enlace_por_ingreso():
    # Misma fecha de ingreso decide aunque el texto cambie; fecha distinta separa aunque el texto se parezca.
    from tremor.defensoria.validar import _con_tokens, calcular_idf, enlazar_reporte
    base = {"departamento": "Puno", "descripcion": "La comunidad de Ocuviri reclama a la minera Arasi.",
            "ubicacion": "Distrito de Ocuviri", "actores_primarios": "CC Ocuviri"}
    casos = {1: _con_tokens(dict(base, ingreso="Marzo de 2012")), 2: _con_tokens(dict(base, ingreso="Junio de 2019"))}
    idf = calcular_idf([base["descripcion"]] * 3)
    reescrito = dict(base, descripcion="Pobladores exigen cumplimiento de compromisos.", ingreso="Jun-19")
    assert enlazar_reporte([reescrito], casos, idf)[0][0] == 2
