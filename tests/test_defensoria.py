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


def test_enlace_por_descripcion():
    from tremor.db import conectar
    from tremor.defensoria.validar import enlazar
    con = conectar(":memory:")
    f = {"departamento": "Amazonas", "descripcion": "Comunidades awajún se oponen a la minería en El Cenepa."}
    a, _ = enlazar(con, f, set(), 100)
    con.execute("INSERT INTO caso_mes (caso_id, reporte_num) VALUES (?, 100)", (a,))
    b, conf = enlazar(con, dict(f, descripcion=f["descripcion"] + " Exigen consulta previa."), set(), 101)
    c, _ = enlazar(con, dict(f, departamento="Puno"), set(), 101)
    assert a == b and conf >= 0.8 and c != a
