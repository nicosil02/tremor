from datetime import date

from tremor.gobierno import leer_decreto
from tremor.lugares import catalogo

CONSIDERANDOS = "CONSIDERANDO: Que, habiéndose producido actos contrarios al Orden Interno; DECRETA: "


def nombres(d):
    return sorted({catalogo()[3][u[:4]] for u in d["lugares"]})


def test_conflicto_provincias_enteras():
    d = leer_decreto(CONSIDERANDOS + "Artículo 1.- Declarar por el término de treinta (30) días calendario a partir del 29 "
                     "de setiembre de 2015 el Estado de Emergencia en las provincias de Cotabambas, Grau, Andahuaylas y "
                     "Chincheros del Departamento de Apurímac. La Policía Nacional mantendrá el control del Orden Interno. "
                     "Artículo 2.- Suspensión")
    assert d["causas"] == {"conflicto"} and d["inicio"] == date(2015, 9, 29) and d["dias"] == 30
    assert nombres(d) == ["ANDAHUAYLAS", "CHINCHEROS", "COTABAMBAS", "GRAU"]


def test_crimen_distritos_y_provincia_entera():
    d = leer_decreto("CONSIDERANDO: Que, el accionar de organizaciones criminales; DECRETA: Artículo 1.- Prorrogar el "
                     "Estado de Emergencia por el término de sesenta (60) días a partir del 09 de julio de 2012 en el "
                     "distrito de Cholón de la provincia de Marañón, en el distrito de Monzón de la provincia de Huamalíes, "
                     "y en la provincia de Leoncio Prado, circunscripciones ubicadas en el departamento de Huánuco; "
                     "en la provincia de Tocache del departamento de San Martín. La Policía Nacional del Perú mantendrá el "
                     "control del orden interno. Artículo 2.-")
    assert d["causas"] == {"crimen"}
    assert nombres(d) == ["HUAMALIES", "LEONCIO PRADO", "MARAÑON", "TOCACHE"]
    assert len([u for u in d["lugares"] if u[:4] in {"1005", "1007"}]) == 2  # solo Monzón y Cholón


def test_desastre_no_es_orden_interno():
    assert leer_decreto("CONSIDERANDO: Que, las lluvias intensas; DECRETA: Artículo 1.- Declarar el Estado de Emergencia "
                        "en el distrito de Huantán por peligro inminente. Artículo 2.- Acciones") is None
