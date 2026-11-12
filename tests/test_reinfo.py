from collections import Counter

from tremor.reinfo import lugares, por_ubigeo

PAGINA = """<input id="txtpagina" name="txtpagina" value="3"><input id="txttotal" name="txttotal" value="942">
<table id="stdregistro"><tr><th>#</th><th>DATOS</th></tr>
<tr><td><td>51</td><td>10000000001</td><td>DECLARANTE DE PRUEBA</td><td>010000001</td><td>LA PRUEBA</td><td>AREQUIPA</td><td>CAYLLOMA</td><td>CAYLLOMA</td><td>VIGENTE</td></td></tr>
<tr><td><td>52</td><td>10000000002</td><td>OTRO DE PRUEBA</td><td>010000002</td><td>OTRA</td><td>AREQUIPA</td><td>CAYLLOMA</td><td>CAYLLOMA</td><td>VIGENTE</td></td></tr>
<tr><td colspan="9">pie</td></tr></table>"""


def test_solo_el_lugar_nunca_el_declarante():
    pag, total, filas, _ = lugares(PAGINA)
    assert (pag, total) == (3, 942)
    assert filas == [("AREQUIPA", "CAYLLOMA", "CAYLLOMA")] * 2  # ni RUC ni nombre


def test_por_ubigeo():
    out, fuera = por_ubigeo(Counter({("AREQUIPA", "CAYLLOMA", "CAYLLOMA"): 2, ("AREQUIPA", "CAYLLOMA", "NO EXISTE"): 1}))
    assert out == {"040505": 2} and fuera == 1


def test_ubicar_nota_de_mineria_ilegal():
    from tremor.web import _lugares, ubicar_ilegal
    deps = {"21": "puno", "06": "cajamarca", "15": "lima"}
    idx = _lugares()
    assert ubicar_ilegal("PNP inmoviliza maquinaria en Yanahuaya por minería ilegal", "Puno", idx, deps) == "211208"
    assert ubicar_ilegal("La minería ilegal amenaza el futuro de Cajamarca", "Cajamarca", idx, deps) is None  # la región, no la provincia
    assert ubicar_ilegal("Operativo contra la minería ilegal en Yanahuaya", None, idx, deps) is None  # sin departamento que la ancle
