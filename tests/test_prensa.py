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
    otro = lambda **k: {**_c("0807", "Paro", 12), **k}
    assert not mismo_evento(otro(reclamo="Laborales"), otro(reclamo="Ambientales"))      # otro reclamo
    assert not mismo_evento(otro(operacion="Las Bambas"), otro(operacion="Antapaccay"))  # otra operación
    assert mismo_evento(otro(reclamo="Ambientales"), otro())                             # sin dato no separa


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
            'CHACHAPOYAS</td><td>1,000</td><td>4,242,072</td><td></td><td></td><td></td><td>2,110,431</td><td>2,000,000</td><td>49.7</td></tr>')  # como la página: girado y avance al final
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


def test_bitacora_guarda_una_vez_por_mes():
    import sqlite3
    import pandas as pd
    from tremor.modelo import bitacora
    con = sqlite3.connect(":memory:")
    a = pd.DataFrame({"mes_base": "2026-09", "ventana_1m": "2026-10", "ubigeo": ["010101", "010102"],
                      "prob_zona_1m": [0.2, None], "creado": "x"})
    assert bitacora(con, a) == 1 and bitacora(con, a) == 0  # la de septiembre no se reescribe
    assert bitacora(con, a.assign(mes_base="2026-10")) == 1


def test_bolsa_fusiona_repeticiones_y_cita():
    import pandas as pd
    from tremor.bolsa import fusionar, plano
    base = dict(tipo="bloqueo", lugar="", causa="", efecto="", fuente="SEC", documento="d", url="u", cita="c",
                fecha_fin="", dias_afectados="")
    df = pd.DataFrame([
        {**base, "empresa": "MMG", "unidad": "Las Bambas", "fecha_inicio": "2023-01", "fecha_fin": "2023-03-11",
         "fecha_documento": "2023-04-26"},
        {**base, "empresa": "MMG", "unidad": "Las Bambas mine", "fecha_inicio": "2023-02", "fecha_documento": "2023-02-10",
         "dias_afectados": "40"},
        {**base, "empresa": "MMG", "unidad": "Las Bambas", "fecha_inicio": "", "fecha_documento": "2023-05-15"},
        {**base, "empresa": "MMG", "unidad": "Las Bambas", "fecha_inicio": "2023", "fecha_documento": "2026-01-01"},
        {**base, "empresa": "MMG", "unidad": "Las Bambas", "fecha_inicio": "2023-09-01", "fecha_documento": "2023-10-25"},
        {**base, "empresa": "Freeport", "unidad": "Cerro Verde", "fecha_inicio": "2023-01", "fecha_documento": "2023-04-21"},
        {**base, "empresa": "Buenaventura", "unidad": "Cerro Verde", "fecha_inicio": "2023-01-15",
         "fecha_documento": "2023-05-01"},
        {**base, "empresa": "Hudbay", "unidad": "Constancia", "fecha_inicio": "2022-11", "fecha_fin": "2022-12",
         "fecha_documento": "2023-03-31"},
    ])
    f = fusionar(df).set_index("unidad")
    assert len(f) == 3 and "Constancia" not in f.index  # 2022: fuera de rango; año suelto: sin ubicar
    bambas = f[f["fecha_inicio"] == "2023-01"].iloc[0]  # la de 2023-09 queda aparte
    assert bambas["fecha_documento"] == "2023-02-10" and bambas["fecha_fin"] == "2023-03-11"
    assert bambas["dias_afectados"] == "40"
    cv = f.loc["Cerro Verde"]
    assert cv["empresa"] == "Freeport" and cv["fecha_inicio"] == "2023-01-15"
    assert plano("road  blockade\nin Chumbivilcas") in plano("A ROAD BLOCKADE in Chumbivilcas started")


def test_anomalia_frente_a_su_historia():
    import numpy as np
    from tremor.modelo import anomalia
    x = np.array([[0, 0, 0, 0, 3], [2, 2, 2, 2, 2]], float)
    z = anomalia(x, k=4)
    assert np.isnan(z[0, 0]) and z[0, 4] == 6.0  # siempre en cero y de pronto 3: (3 - 0) / (0 + 0.5)
    assert z[1, 4] == 0.0  # igual que siempre


def test_gobierno_titulos_jne_y_revocatoria():
    from tremor.gobierno import clases, municipio, resultado_revocatoria
    t = "Convocan a ciudadana para que asuma, de manera provisional, el cargo de regidora del Concejo Distrital de Sachaca, provincia y departamento de Arequipa"
    assert municipio(t) == ("040117", False) and clases(t) == ["jne_convoca_provisional"]
    t = "Declaran infundado recurso sobre vacancia de alcalde de la Municipalidad Provincial de Espinar, departamento de Cusco"
    assert municipio(t) == ("080801", True) and clases(t) == ["jne_vacancia"]  # provincial → capital (..01)
    assert municipio("Declaran nulo procedimiento de vacancia contra regidor de la Municipalidad Distrital de Carmen de la Legua Reynoso, Provincia Constitucional del Callao") == ("070103", False)
    assert municipio("Convocan a ciudadano para que asuma el cargo de consejero del Consejo Regional de Cajamarca") is None
    csv = ("UBIGEO;DEPARTAMENTO;PROVINCIA;DISTRITO;UBICACION_EN_CEDULA;VOTOS_SI;VOTOS_NO\n"
           "030317;APURIMAC;ANDAHUAYLAS;HUAYANA;1;55;67\n030317;APURIMAC;ANDAHUAYLAS;HUAYANA;1;45;33\n"
           "030317;APURIMAC;ANDAHUAYLAS;HUAYANA;2;99;0\n")  # la posición 2 (regidor) no cuenta
    assert resultado_revocatoria(csv.splitlines(), False) == {"030206": (50.0, 1, 100.0)}  # ubigeo RENIEC 030317 → INEI 030206


def test_mef_mancomunidad_no_pisa_a_la_municipalidad():
    from tremor.territorio import por_municipalidad
    filas = [{"nombre": "050101-300507: MUNICIPALIDAD PROVINCIAL DE HUAMANGA", "pim": 9, "devengado": 7},
             {"nombre": "050101-301999: MANCOMUNIDAD MUNICIPAL LOS WARI- MANWARI", "pim": 1, "devengado": 1}]
    assert por_municipalidad(filas) == {"050101": ("MUNICIPALIDAD PROVINCIAL DE HUAMANGA", 9, 7)}


def test_fusion_estima_lo_que_nadie_vio():
    """Tres listas independientes que ven 50% cada una de 800 protestas: ninguna ve 1/8 → unas 100 no vistas."""
    import numpy as np
    import pandas as pd
    from tremor.fusion import fusion, no_vistas
    r = np.random.default_rng(0)
    vistas = {k: r.random(800) < 0.5 for k in ("defensoria", "egpp", "acled")}
    fuentes = {k: pd.DataFrame({"ubigeo": "080101", "m": np.flatnonzero(v)}) for k, v in vistas.items()}
    f = fusion(fuentes)
    assert len(f) == sum(np.any(list(vistas.values()), axis=0))
    lo, hi, ll = no_vistas(f, ("defensoria", "egpp", "acled"))
    assert 70 < ll < 135 and lo <= ll <= hi


def test_comunidad_de_caso():
    from tremor.comunidades import comunidad_de_caso as c
    assert c("CC Chuicuni - Las Bambas") == "chuicuni"
    assert c("Comunidad Campesina de Maure – Penal de Challapalca") == "maure"
    assert c("CC Ajoyani-MINSUR") == "ajoyani"
    assert c("Wampis - Minería ilegal") is None


def test_dudosas_solo_otro_que_nombra_operacion():
    import sqlite3
    from tremor.prensa.codificar import dudosas
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE nota (id INTEGER, titular TEXT, resumen TEXT)")
    con.execute("CREATE TABLE codificacion (nota_id INTEGER, version TEXT, es_protesta INTEGER, tipo_conflicto TEXT, "
                "empresa TEXT, operacion TEXT)")
    con.executemany("INSERT INTO nota VALUES (?, ?, NULL)", [(1, "Velille protesta por acuerdos con Las Bambas"),
                    (2, "Paro por agua potable en Juliaca"), (3, "Bloqueo en Santa Ana por la carretera")])
    con.executemany("INSERT INTO codificacion VALUES (?, 'v2', 1, 'otro', NULL, NULL)", [(1,), (2,), (3,)])
    assert [n for n, _, _ in dudosas(con)] == [1]
    con.execute("INSERT INTO revision_operacion VALUES (1, 'v2', 'socioambiental_extractivo')")
    assert dudosas(con) == []


def test_anuncio_y_fecha_relativa():
    from tremor.prensa.codificar import ANUNCIA_PAR, fecha_relativa
    assert ANUNCIA_PAR.search("transportistas convocan a un paro indefinido")
    assert ANUNCIA_PAR.search("acordaron realizar una marcha")
    assert not ANUNCIA_PAR.search("el ministro anuncio ayuda. el bloqueo sigue")       # otra frase
    assert fecha_relativa("paro desde el lunes", "2026-11-10") == "2026-11-16"          # 10 nov 2026 es martes
    assert fecha_relativa("marcha el proximo martes", "2026-11-10") == "2026-11-17"
    assert fecha_relativa("bloqueo manana en la via", "2026-11-10") == "2026-11-11"
    assert fecha_relativa("esta manana bloquearon", "2026-11-10") is None


def test_animo_historia_mensual():
    import sqlite3
    import pandas as pd
    from tremor.animo import historia
    con = sqlite3.connect(":memory:")
    m = pd.DataFrame({"proyecto": ["A", "A", "B", "A"], "fecha": ["2026-11-01", "2026-11-05", "2026-11-05", "2026-10-30"], "tono": [-1, 1, -1, -1]})
    a = pd.DataFrame({"proyecto": ["A", "B"], "alza": [2.5, 1.0]})
    historia(con, m, a, "2026-11"); historia(con, m, a, "2026-11")  # dos corridas: se reemplaza, no se duplica
    assert con.execute("SELECT proyecto, menciones, negativas, tono, alza FROM animo_mes ORDER BY proyecto").fetchall() == [("A", 2, 1, 0.0, 2.5), ("B", 1, 1, -1.0, 1.0)]


def test_dicho_de_menciones_de_radio(monkeypatch):
    """Una oración del LLM por mención de radio; 'no habla del proyecto' queda guardado y web.menciones lo deja fuera."""
    import sqlite3
    from tremor import animo
    con = sqlite3.connect(":memory:")
    con.executescript("""
        CREATE TABLE nota (id, medio, titular, resumen, enlace, publicado, consulta, filtro);
        INSERT INTO nota VALUES ('a', 'Radio Calor', 'Radio Calor, en vivo 10/11/2026 13:19 (1)', 'saludos ' || 'x ' || 'los comuneros dicen que Minera Bateas contamina el río', 'https://s/x.m3u8', '2026-11-10', 'radio', NULL),
                                ('b', 'Radio Feliz', 'Radio Feliz, en vivo 10/11/2026 16:59 (13)', 'la poderosa sangre de Cristo', 'https://s/y.m3u8', '2026-11-10', 'radio', NULL);
        CREATE TABLE mencion (nota_id, proyecto, fecha, medio, origen, negativos, positivos, tono);
        INSERT INTO mencion VALUES ('a', 'Minera Bateas', '2026-11-10', 'Radio Calor', 'radio', 1, 0, -1),
                                   ('b', 'Minera Poderosa', '2026-11-10', 'Radio Feliz', 'radio', 0, 0, 0);
    """)
    monkeypatch.setattr("tremor.llm.chat_json", lambda con, s, u, v: {"dicho": "No habla del proyecto" if "Poderosa" in u else "Comuneros dicen que la minera contamina el río."})
    monkeypatch.setattr(animo, "date", type("D", (), {"today": staticmethod(lambda: __import__("datetime").date(2026, 11, 11))}))
    assert animo.dicho(con) == 2
    assert dict(con.execute("SELECT nota_id, dicho FROM mencion_dicho")) == {"a": "Comuneros dicen que la minera contamina el río.", "b": "No habla del proyecto"}


def test_parsear_gobpe():
    from tremor.prensa.recolectar import parsear_gobpe
    pag = ('<script>x = {"total_count":2,"results":[{"publication":" 9 de noviembre de 2026 -  1:15 p. m.",'
           '"name_with_parent":"PNP restablece el tránsito en la vía bloqueada","content":"En Chumbivilcas.",'
           '"url":"<a class=\\"x\\" href=\\"/institucion/pnp/noticias/1-pnp\\">t</a>"},'
           '{"publication":"20 de octubre de 2026 - 12:02 a. m.","name_with_parent":"Comunicado","url":""}]}</script>')
    a, b = parsear_gobpe(pag, "Policía Nacional")
    assert a["publicado"] == "2026-11-09T13:15-05:00" and a["enlace"] == "https://www.gob.pe/institucion/pnp/noticias/1-pnp"
    assert a["medio"] == "Policía Nacional" and a["resumen"] == "En Chumbivilcas."
    assert b["publicado"] == "2026-10-20T00:02-05:00" and b["enlace"] is None
    assert list(parsear_gobpe("<html>sin resultados</html>", "PCM")) == []
