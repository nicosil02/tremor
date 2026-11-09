import csv

from tremor.radio import CATALOGO, filtro_radio, lengua, no_castellano, trozos

# Ñuqanchik (TV Perú), 20/09/2022, transcrito con MMS quz: mototaxistas de Huancavelica contra una ordenanza
QUECHUA = ("ñawpaqninpi sayariykunku paykunan huk ordenanzata mana uyachkankuchu chaymi kamachikun llaqtapa "
           "chawpinpi mana purinankuta huk ordenanzatan uyarqonku chaymi harkakun llaqtapa chawpinman chayanaykuta "
           "manan chaypi muyuriytachu munaniku pasayllatan munachkaniku moto taxistakunan autoridadkunata "
           "mañakuchkanku chay ordenansata holluchinankupaq kay sasachakuymantapas rimariykun municipalidad "
           "purinankupaq permesota mana hunchu kinsa pachak moto taxistakunan kanku jerente municipalñataqmi")


def test_no_castellano_detecta_voz_sin_texto():
    voz = [(0, 180)]  # tres minutos de habla
    segs = [(i, i + 5, "x" * 70) for i in range(0, 60, 5)]  # castellano: 14 caracteres por segundo
    segs += [(130, 134, "en el sector agrario")]  # Whisper casi calla ante el quechua
    assert no_castellano(segs, voz, 180) == [(60, 180)]
    assert no_castellano([], [(0, 10)], 60) == []  # música o silencio: poca voz, no se gasta MMS


def test_lengua_por_provincia():
    assert lengua({"provincia": "El Collao", "departamento": "Puno"}) == "ayr"
    assert lengua({"provincia": "Espinar", "departamento": "Cusco"}) == "quz"
    assert lengua({"provincia": "Huanta", "departamento": "Ayacucho"}) == "quy"


def test_filtro_y_trozos_en_quechua():
    assert filtro_radio(QUECHUA) is None  # sayari- (pararse) + municipalidad
    t = trozos(QUECHUA * 4)  # MMS no puntúa: igual se parte
    assert len(t) == 2 and all(len(x) < 1400 for x in t)


def test_catalogo_sin_repetidos():
    with open(CATALOGO, encoding="utf-8") as f:
        filas = list(csv.DictReader(f))
    assert len({f["stream"] for f in filas}) == len(filas)
    assert all(len(f["ubigeo_provincia"]) == 4 or f["medio"].startswith("TV:") for f in filas)  # la TV es nacional
