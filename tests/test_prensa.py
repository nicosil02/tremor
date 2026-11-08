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


def test_ubicar_caso_defensoria():
    from tremor.prensa.eventos import ubicar_caso
    assert ubicar_caso("Cusco", ["Distrito de Chamaca, provincia de Chumbivilcas, región Cusco"]) == ("080703", "distrito")
    assert ubicar_caso("Ayacucho", ["Provincia de Cangallo Eduardo, Alcalde Provincial"]) == ("0502", "provincia")
    assert ubicar_caso("Ica", ["", "Distrito de San Andrés, provincia de Pisco, región Ica"])[1] == "distrito"
    assert ubicar_caso("Puno", [""]) == ("21", "departamento")


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


def test_bcrp_y_pobreza_enaho():
    import pandas as pd
    from tremor.territorio import periodo_bcrp, pobreza
    assert periodo_bcrp("Set.2024") == "2024-09"
    s = pd.DataFrame({"ubigeo": [10101, 10102, 80101], "factor07": [1.0, 3.0, 2.0], "mieperho": [2, 2, 1],
                      "pobreza": [1, 3, 2]})
    assert pobreza(s) == [("01", 25.0, 25.0, 2), ("08", 100.0, 0.0, 1), ("00", 40.0, 20.0, 3)]


def test_stock_concesiones():
    from tremor.distritos import stock_concesiones
    s = stock_concesiones([(["010101"], 2020, 100, True), (["010101", "010102"], 2022, 50, False)], 2023)
    assert s[("010101", 2020)]["concesiones"] == 1 and s[("010101", 2021)] == {"concesiones": 1, "concesiones_ha": 100,
                                                                               "concesiones_metalicas_ha": 100}
    assert s[("010101", 2023)]["concesiones_ha"] == 125 and s[("010102", 2022)]["concesiones_nuevas_ha"] == 25


def test_resultados_electorales():
    import pandas as pd
    from tremor.distritos import resultados_electorales
    t = pd.DataFrame({"UBIGEO": ["010101"] * 4, "MESA": [1, 1, 2, 2], "TIPO_ELECCION": ["MUNICIPAL DISTRITAL"] * 4,
                      "AGRUPACION_POLITICA": ["A", "B", "A", "B"], "VOTOS_OBTENIDOS": [30, 10, 30, 30],
                      "ELECTORES_HABILES": [50, 50, 100, 100], "otros": [5, 5, 10, 10]})
    r = resultados_electorales(t)["010101"]
    assert r["voto_ganador"] == 0.6 and r["margen_victoria"] == 0.2 and r["listas"] == 2
    assert r["participacion"] == round(115 / 150, 4) and r["nep_listas"] == round(1 / (0.36 + 0.16), 3)


def test_niveles_y_rezagos():
    import numpy as np
    from tremor.modelo import futuro, nivel_accion, resto, ventana
    assert [nivel_accion(a) for a in ("Plantón", "Paro de 48 horas", "Bloqueo de vías", "Huelga de hambre",
                                      "Enfrentamiento entre sectores de la sociedad y la PNP")] == [2, 3, 3, 2, 4]
    x = np.array([[1, 0, 2, 0, 3.0]])
    assert ventana(x, 2).tolist() == [[1, 1, 2, 2, 3]]  # incluye el mes t, nunca t+1
    f = futuro(x, 2)  # t+1 … t+2; sin datos suficientes = NaN
    assert f[0, :3].tolist() == [2, 2, 3] and np.isnan(f[0, 3:]).all()
    assert resto(np.array([[1.0], [2.0], [5.0]]), ["a", "a", "b"]).ravel().tolist() == [2, 1, 0]


def test_extractivo():
    from tremor.modelo import extractivo
    for a, d in [("Comunidad campesina de Fuerabamba", "Exigen a Las Bambas cumplir el convenio marco"),
                 ("Pobladores", "Rechazan la contaminación del río por relaves"),
                 ("Comunidades nativas de Andoas", "Exigen remediación del Lote 192")]:
        assert extractivo(a, d), d
    for a, d in [("Trabajadores de la empresa Chinalco", "Exigen el aumento de sus remuneraciones"),
                 ("Población", "En rechazo a las represalias del alcalde"),
                 ("Federación de taxistas", "Rechazan el alza del precio del gas"),
                 ("Padres de familia de la I.E. La Inmaculada", "Exigen el inicio del año escolar")]:
        assert not extractivo(a, d), d


def test_afinar_lugar():
    from tremor.prensa.eventos import afinar_lugar
    assert afinar_lugar("09", "Huancavelica . Población del distrito de Lircay . Exigen") == "090301"
    assert afinar_lugar("0807", "Chumbivilcas . Comuneros de Velille . Exigen a la minera") == "080708"
    assert afinar_lugar("09", "Huancavelica . Población . Exigen el asfaltado") is None


def test_acled_extractivo():
    from tremor.distritos import ACLED_EXTRACTIVO as E, ACLED_NO as N
    def etiqueta(t):
        return bool(E.search(t)) and not N.search(t)
    assert etiqueta("protesters blocked the entrance to the Inmaculada mine")
    assert etiqueta("Awajun residents took station 5 of the Nor Peruvian Oil pipeline")
    assert not etiqueta("artisanal miners blocked the Panamericana demanding REINFO extension")
    assert etiqueta("artisan fishers marched against the oil spill")
    assert not etiqueta("teachers protested in Lima demanding higher wages")


def test_radio_trozos():
    from tremor.radio import trozos
    texto = "Comuneros de Chumbivilcas anuncian paro. " * 60
    partes = trozos(texto, 300)
    assert all(len(x) <= 350 for x in partes) and "".join(partes).count("paro") == 60


def test_animo():
    from tremor.animo import menciones, provincias, tono
    m = menciones("Hoy llovió en Abancay. Comuneros denuncian que Las Bambas incumple el acuerdo y anuncian paro. "
                  "En otras noticias, el clima.")
    assert [n for n, _ in m] == ["Las Bambas (MMG)"]
    neg, pos, t = tono(m[0][1])
    assert neg >= 3 and t < 0  # denuncian, incumple, paro (y "acuerdo" positivo)
    assert tono("Se firmó un acuerdo y la empresa cumplió con el convenio")[2] > 0
    assert provincias()["Las Bambas (MMG)"] == ["0305", "0307"]


def test_lead_de_la_nota():
    from tremor.prensa.ampliar import lead
    p = ('<meta property="og:description" content="Comuneros de Chamaca bloquean la vía">'
         '<p>Menú</p><p>Los comuneros del distrito de Chamaca, provincia de Chumbivilcas, iniciaron un paro indefinido.</p>')
    t = lead(p)
    assert t.startswith("Comuneros de Chamaca") and "Chumbivilcas" in t and "Menú" not in t


def test_mcp_pobreza_enaho_departamento_desconocido():
    from tremor.mcp_server import pobreza_enaho
    assert "error" in pobreza_enaho("Narnia")


def test_cadena_llm_salta_proveedores_sin_clave(monkeypatch):
    from tremor import llm
    monkeypatch.setattr(llm, "_env", lambda: None)
    monkeypatch.setenv("LLM_MODEL", "a,gemini:b,c")
    monkeypatch.setenv("LLM_API_KEY", "x")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert [m for m, _, _ in llm.cadena()] == ["a", "c"]
    monkeypatch.setenv("GEMINI_API_KEY", "y")
    assert [m for m, _, _ in llm.cadena()] == ["a", "b", "c"]


def test_filtro_radio():
    from tremor.radio import filtro_radio
    noticia = ("Los comuneros de Chumbivilcas anunciaron un paro indefinido desde el lunes contra la empresa minera "
               "por el incumplimiento de las actas firmadas, informó el presidente del frente de defensa de la "
               "provincia, que pidió la presencia de la presidencia del consejo de ministros en la zona para dialogar")
    assert filtro_radio(noticia) is None
    assert filtro_radio("mi amor mi amor " * 30) == "musica_o_ruido"
    predica = ("Isaías capítulo 32, hermanos, lo dice la palabra de Dios: mi pueblo habitará en morada de paz. "
               "Amén, hermanos, el Señor nuestro Dios es la mejor seguridad que tenemos en esta vida, y no hay otra "
               "seguridad que la de Jesús, que nos da su paz en la casa y en el trabajo de cada día con la familia")
    assert filtro_radio(predica) == "religioso"


def test_boosting_con_variable_vacia():
    import numpy as np
    from tremor.modelo import modelos
    x = np.random.default_rng(0).random((400, 3)); x[:, 1] = np.nan
    m = modelos()["gradient_boosting"].fit(x, (x[:, 0] > .5).astype(int))
    assert m.predict_proba(x[:5]).shape == (5, 2)


def test_avisos_de_animo():
    import pandas as pd
    from tremor.animo import avisos
    r = pd.DataFrame({"proyecto": ["Tía María"] * 5 + ["Conga"],
                      "fecha": ["2026-11-01"] * 3 + ["2026-11-03", "2026-11-05", "2026-11-02"],
                      "tono": [-1, -1, -1, -1, -1, 1]})
    a = avisos(r, r.iloc[:0])
    assert "pico negativo el 2026-11-01" in a["Tía María"] and "racha" in a["Tía María"]
    assert "Conga" not in a


def test_historial_empresa():
    import sqlite3
    import pandas as pd
    from tremor.empresas import historial
    con = sqlite3.connect(":memory:")
    pd.DataFrame({"empresa": ["MINERA X"], "unidad": ["Mina"], "tipo": ["mineria"], "ubigeo": ["030101"]}).to_sql("operacion", con)
    pd.DataFrame({"ubigeo": ["030101"], "lugar": ["x"]}).reindex(columns=[
        "ubigeo", "lugar", "prob_zona", "prob_zona_extractivo", "razones_zona_extractivo", "puesto_zona",
        "puesto_zona_extractivo", "alerta_inmediata", "senal_prensa", "animo_proyectos", "ventana"]).to_sql("alerta", con)
    pd.DataFrame({"ubigeo": ["030101"] * 4 + ["990101"], "m": [1, 2, 3, 4, 1], "objetivo": "z_fuerza", "modelo": "lasso",
                  "puntaje": 0.5, "y": [1, 1, 0, 0, 1], "pct": [0.05, 0.5, 0.05, 0.9, 0.01]}).to_sql("modelo_prediccion", con)
    h = historial(con, "minera x").iloc[0]
    assert (h.eventos, h.vistos, h.alertas) == (2, 1, 2)


def test_web_anillo_horario(monkeypatch, tmp_path):
    from shapely.geometry import Polygon
    from shapely.geometry.polygon import orient
    from tremor import web
    import json
    antihorario = orient(Polygon([(0, 0), (1, 0), (1, 1), (0, 1)]), sign=1.0)
    geo = {"features": [{"properties": {"ubigeo": "010101"}, "geometry": antihorario.__geo_interface__}]}
    (tmp_path / "distritos.geojson").write_text(json.dumps(geo), encoding="utf-8")
    monkeypatch.setattr(web, "DATOS", tmp_path)
    anillo = json.loads(web.geo())["features"][0]["geometry"]["coordinates"][0]
    assert not Polygon(anillo).exterior.is_ccw  # d3 lo necesita horario


def test_cambios_de_caso():
    import pandas as pd
    from tremor.modelo import cambios_de_caso
    t = pd.DataFrame({"caso_id": [1, 1, 1, 2, 2], "ubigeo": "010101", "m": [10, 11, 12, 11, 12],
                      "estado": ["latente", "activo", "activo", "activo", "activo"],
                      "dialogo": [None, "HAY DIÁLOGO", "NO HAY DIÁLOGO", "NO HAY", "NO HAY"]})
    r = cambios_de_caso(t).set_index(["caso_id", "m"])
    assert not r.loc[(1, 10), "nuevos"] and r.loc[(2, 11), "nuevos"]  # el primer mes de la serie no cuenta
    assert r.loc[(1, 11), "activados"] and not r.loc[(1, 12), "activados"]
    assert r.loc[(1, 12), "dialogo_roto"] and r[["dialogo_roto"]].sum().item() == 1
