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


def test_decreto_antiguo_sin_decir_orden_interno():
    # DS 030-2007-PCM (Tía María): el artículo 1 solo prorroga; es de orden interno porque invoca el artículo 137
    from datetime import date
    from tremor.gobierno import leer_decreto
    t = ("Fecha de publicación: 31/03/2007 Prorrogan Estado de Emergencia en el distrito de Cocachacra CONSIDERANDO: Que, "
         "de conformidad con el inciso 1) del artículo 137 de la Constitución Política del Perú; DECRETA: Artículo 1º.- "
         "Prórroga de Estado de Emergencia Prorrogar por el término de quince (15) días, a partir del 1 de abril de 2007, el "
         "Estado de Emergencia en el distrito de Cocachacra, de la provincia de Islay del departamento de Arequipa. "
         "Artículo 2º.- Suspensión del ejercicio de Derechos Constitucionales.")
    d = leer_decreto(t)
    assert d["inicio"] == date(2007, 4, 1) and d["dias"] == 15 and d["lugares"] == {"040702"} and d["causas"] == {"hereda"}


def test_articulo_137_solo_no_basta():
    # antes de 2011 las heladas y los sismos también invocaban el artículo 137; el COVID suspende derechos y no cuenta
    from tremor.gobierno import leer_decreto
    base = "Fecha de publicación: 15/06/2007 CONSIDERANDO: Que, el artículo 137 de la Constitución {} DECRETA: Artículo 1º.- {} Artículo 2º.- {}"
    assert leer_decreto(base.format("y las bajas temperaturas;", "Declárese en Estado de Emergencia el departamento de Puno, por sesenta (60) días.",
                                    "El INDECI ejecutará las acciones.")) is None
    assert leer_decreto(base.format("y la propagación del COVID-19;", "Prorrogar el Estado de Emergencia Nacional por treinta (30) días.",
                                    "Queda suspendido el ejercicio de los derechos constitucionales.")) is None
