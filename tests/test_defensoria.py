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
