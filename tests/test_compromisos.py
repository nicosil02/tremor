from datetime import date

from tremor.compromisos import compromisos, seguimiento


def test_compromiso_y_su_seguimiento():
    # reporte de mayo de 2023: la mesa se programa para junio; el de junio dice que se hizo (caso real, Chiquintirca)
    c = compromisos("Las partes acuerdan que la siguiente Mesa de Diálogo se llevará a cabo el 15 de junio en Ayacucho. "
                    "El 2 de junio se reunieron las partes en Ayacucho.", 2023, 5)
    assert [f for f, _ in c] == [date(2023, 6, 15)]  # "el 2 de junio se reunieron" ya pasó: no es compromiso
    despues = [(232, 2023, 6, 31, "El 15 de junio de 2023, se realizó la reunión de la mesa de diálogo.")]
    assert seguimiento(date(2023, 6, 15), despues)[:3] == ("se realizó", 232, 31)
    assert seguimiento(date(2023, 6, 20), despues)[0] == "sin noticia"  # el caso tuvo hechos ese mes y no la nombra
    assert seguimiento(date(2023, 9, 1), despues)[0] == "pendiente"  # todavía no hay reporte de setiembre


def test_convocatoria_a_paro_no_es_compromiso():
    assert compromisos("El comité ha convocado a un paro regional para el 21 y 22 de agosto.", 2012, 7) == []


def test_pagina_real_de_la_frase():
    from tremor.compromisos import pagina_real, plano
    paginas = [plano("Portada"), plano("Caso X. Las partes acuer-\ndan que la siguiente Mesa de Diálogo se llevará a cabo el 15 de junio")]
    assert pagina_real(paginas, "Las partes acuerdan que la siguiente Mesa de Diálogo se llevará a cabo el 15 de junio") == 2
    assert pagina_real(paginas, "Una frase que no está en ninguna página del reporte") is None



def test_tipo_sin_frase():
    from tremor.compromisos import tipo
    assert tipo("Las partes acuerdan que la siguiente Mesa de Diálogo se llevará a cabo el 15 de junio") == "Mesa de diálogo"
    assert tipo("El gobernador se comprometió a ingresar a la comunidad el 8 de octubre") == "Compromiso"
    assert tipo("La próxima reunión se realizará el 07 de mayo") == "Reunión"
