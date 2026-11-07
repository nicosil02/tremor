from tremor.prensa.codificar import limpiar
from tremor.prensa.recolectar import filtro, id_nota, parsear

RSS = """<rss><channel><item><title>Comuneros anuncian paro indefinido contra minera - Pachamama Radio</title>
<link>https://news.google.com/rss/articles/abc</link><pubDate>Thu, 05 Nov 2026 23:29:00 GMT</pubDate>
<description>&lt;a href="x"&gt;Comuneros anuncian paro&lt;/a&gt;</description><source url="x">Pachamama Radio</source></item>
</channel></rss>"""


def test_parsear_google_news():
    n, = parsear(RSS)
    assert n["medio"] == "Pachamama Radio" and n["titular"] == "Comuneros anuncian paro indefinido contra minera"
    assert n["publicado"] == "2026-11-05T18:29-05:00" and n["resumen"] == ""


def test_identidad_estable_y_filtro():
    assert id_nota("RPP", "Paro  en Puno") == id_nota("rpp", "paro en puno")
    assert filtro("Cienciano toma ventaja en la Sudamericana") == "no_es_protesta"
    assert filtro("Inauguran hospital en Juliaca") == "sin_palabra_de_accion"
    assert filtro("Ronderos bloquean la vía Cajamarca-Bambamarca") is None


def test_limpiar_respuesta_llm():
    c = limpiar({"es_protesta": True, "estado": "anunciada", "fecha_evento": "12 de noviembre",
                 "sector": "Comunidades tradicionales", "actor": "Docentes colegios", "accion": "Paro",
                 "reclamo": "Ambientales", "sub_reclamo": "Aumentos salariales", "adversario": "Empresas Privadas",
                 "heridos": "3", "region": "Cusco"})
    assert c["es_protesta"] == 1 and c["estado"] == "anunciada" and c["accion"] == "Paro"
    assert c["fecha_evento"] is None            # no es AAAA-MM-DD
    assert c["actor"] is None                   # no pertenece al sector
    assert c["sub_reclamo"] is None             # no pertenece al reclamo
    assert c["heridos"] == 3 and c["region"] == "Cusco"


from datetime import date

from tremor.prensa.eventos import mismo_evento, ubicar_texto


def _c(ubigeo, accion, d, sector=None):
    return {"ubigeo": ubigeo, "accion": accion, "fecha": date(2026, 11, d), "sector": sector}


def test_mismo_evento():
    assert mismo_evento(_c("210501", "Paro", 12), _c("2105", "Bloqueo de vías", 13))      # mismo paro, otra nota
    assert mismo_evento(_c("0807", "Paro", 12), _c("080701", "Paro", 15))                # paro de varios días
    assert not mismo_evento(_c("0807", "Marcha", 12), _c("0807", "Marcha", 15))
    assert not mismo_evento(_c("0807", "Paro", 12), _c("0803", "Paro", 12))              # otra provincia
    assert not mismo_evento(_c("0807", "Paro", 12, "Educativo"), _c("0807", "Paro", 12, "Transporte"))


def test_ubicar_texto_defensoria():
    assert ubicar_texto("Espinar, Cusco") == ("080801", "distrito")
    assert ubicar_texto("Lima Metropolitana") == ("1501", "provincia")
    assert ubicar_texto("Cusco") == ("08", "departamento")


def test_medio_extranjero_y_departamento_copiado():
    from tremor.prensa.codificar import ubicar
    from tremor.prensa.recolectar import filtro
    assert filtro("Paro nacional", "https://www.clarin.com.ar") == "medio_extranjero"
    assert filtro("Paro nacional en Puno", "https://rpp.pe") is None
    c = {"region": "Madre de Dios", "provincia": None, "distrito": None, "localidad": None}
    assert ubicar(c, "Jerez convoca la manifestación de la huelga general", "Madre de Dios") == (None, None)
    assert ubicar(c, "Paro en Madre de Dios", None)[1] == "departamento"


def test_sutran_fila():
    from tremor.sutran import fila
    f = fila({"region": "Huanuco", "provincia": "Huanuco", "distrito": "Pillco Marca", "fechaEvento": "04/11/2026",
              "estadoVia": "interrumpido", "motivo": "humano", "submotivo": "humano.protestas"})
    assert f["fecha_evento"] == "2026-11-04" and f["precision"] == "distrito" and f["ubigeo"].startswith("1001")


def test_parsear_mef():
    from tremor.territorio import filas_mef, por_municipalidad
    fila = ('<tr id="tr1"><td><input name="grp1" value="010101"></td><td>010101-300001: MUNICIPALIDAD PROVINCIAL DE '
            'CHACHAPOYAS</td><td>1,000</td><td>4,242,072</td><td></td><td></td><td></td><td>2,110,431</td></tr>')
    assert por_municipalidad(filas_mef(fila)) == {"010101": ("MUNICIPALIDAD PROVINCIAL DE CHACHAPOYAS", 4242072, 2110431)}


def test_mcp_buscar_lugar():
    from tremor.mcp_server import buscar_lugar
    assert buscar_lugar("challhuahuacho")[0]["ubigeo"] == "030506"
