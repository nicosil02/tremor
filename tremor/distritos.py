"""Perfil distrital de todo el Perú: variables por ubigeo y año para el modelo (spec en specs/005-modelo).

Una sola tabla larga, `distrito_variable(ubigeo, anio, variable, valor, fuente)`. `anio` es el año del dato; 0 marca
una foto sin serie (p. ej. dónde hay una operación hoy). Fuentes verificadas el 7 nov 2026:
- PNUD: IDH distrital 2017-2024 y sus componentes; su capa trae también los límites INEI 2025 (`datos/distritos.geojson`).
- INEI: mapa de pobreza distrital 2018 (intervalo de confianza al 95 %).
- INGEMMET (GEOCATMIN): catastro minero (concesiones con fecha de petitorio) y pasivos ambientales mineros.
- OEFA (PIFA): unidades mineras fiscalizadas, lotes de hidrocarburos y el Oleoducto Norperuano.
- ONPE (datos abiertos): resultados mesa por mesa de las elecciones municipales distritales 2006-2022.
- Ministerio de Cultura (BDPI): territorios de comunidades campesinas y nativas, reservas indígenas.
- MTC (red vial nacional, en GEOCATMIN): km de vía nacional y corredores logísticos por distrito.
- INEI (Censo 2017, REDATAM): ruralidad, lengua materna e identidad indígena, agua y electricidad.

`python -m tremor.distritos {pnud,pobreza,catastro,pasivos,oefa,onpe,comunidades,vias,censo,ambiente,senace,ana,oefa_denuncias,emergencias,geobosques,renamu,acled,todo}`
"""
import argparse
import io
import re
import sys
import zipfile
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

import requests

from tremor.db import DATOS, ahora, conectar
from tremor.lugares import catalogo, norm, resolver
from tremor.territorio import UA

PNUD = "https://geosmarthosting.undp.org/arcgis/rest/services/Hosted/Distritos_INEI_2025_IDH_2017_2024/FeatureServer/0"
POBREZA_2018 = "https://cdn.www.gob.pe/uploads/document/file/3340937/Anexo%20Estad%C3%ADstico.xlsx"
GEOCATMIN = "https://geocatminnube.ingemmet.gob.pe/arcgis/rest/services"  # geocatmin. no envía la cadena SSL completa
# El catastro completo solo está en geocatmin., que no envía la cadena SSL completa: se valida con el almacén del
# sistema (truststore), que sí la completa. geocatminnube. tiene la cadena bien y el inventario de pasivos más nuevo.
CATASTRO = "https://geocatmin.ingemmet.gob.pe/arcgis/rest/services/SERV_CATASTRO_MINERO_WGS84/MapServer/0"
PASIVOS = f"{GEOCATMIN}/SERV_PASIVO_AMBIENTAL/MapServer/0"
OEFA = "https://pifa.oefa.gob.pe/ags_server/rest/services/PORTAL"
GEOJSON = DATOS / "distritos.geojson"
BDPI = "https://geoportal.cultura.gob.pe/mapa_bdpi/layer/listarCapaDgpiInfo"
VIA_NACIONAL = f"{GEOCATMIN}/SERV_CARTOGRAFIA_BASE_WGS84/MapServer/4"
# Corredor Minero del Sur: la PE-3SG (Challhuahuacho - Espinar), por donde sale el concentrado de Las Bambas.
CORREDORES = {"Corredor Minero del Sur": {"PE-3SG"}}
ONPE = "https://www.datosabiertos.gob.pe/sites/default/files/ERM{anio}_Municipal_Distrital{sufijo}"
# El archivo "ERM2002_Municipal_Distrital" de la ONPE trae en realidad la elección regional: 2002 queda fuera.
ELECCIONES = {2006: ".zip", 2010: ".zip", 2014: ".zip", 2018: "_total.zip", 2022: ".zip"}
EPOCA = datetime(1970, 1, 1, tzinfo=timezone.utc)
ESQUEMA = """CREATE TABLE IF NOT EXISTS distrito_variable (
    ubigeo TEXT NOT NULL, anio INTEGER NOT NULL, variable TEXT NOT NULL, valor REAL, fuente TEXT,
    consultado TEXT NOT NULL, PRIMARY KEY (ubigeo, anio, variable))"""


def _post(url, data, intentos=6):
    """POST con reintentos: el servidor del SENACE corta conexiones a menudo."""
    import time
    for i in range(intentos):
        try:
            return requests.post(url, data=data, headers=UA, timeout=300).json()
        except requests.RequestException:
            if i == intentos - 1:
                raise
            time.sleep(5 * (i + 1))


def arcgis(capa, campos="*", geometria=False, lote=500):
    """Todas las filas de una capa ArcGIS REST: primero los ids y luego lotes por objectIds (GEOCATMIN no pagina
    con resultOffset). Con geometría devuelve GeoJSON en WGS84."""
    ids = _post(f"{capa}/query", dict(where="1=1", returnIdsOnly="true", f="json"))["objectIds"] or []
    salida = []
    for i in range(0, len(ids), lote):
        r = _post(f"{capa}/query", data=dict(
            objectIds=",".join(map(str, sorted(ids)[i:i + lote])), outFields=campos, outSR=4326,
            returnGeometry=str(geometria).lower(), f="geojson" if geometria else "json"))
        salida += r["features"] if geometria else [f["attributes"] for f in r["features"]]
    return salida


def guardar(con, filas, fuente):
    """filas: [(ubigeo, anio, variable, valor)]. Reemplaza todo lo anterior de esas variables (idempotente)."""
    con.execute(ESQUEMA)
    momento = ahora()
    con.executemany("DELETE FROM distrito_variable WHERE variable = ?", [(v,) for v in {f[2] for f in filas}])
    con.executemany("INSERT OR REPLACE INTO distrito_variable VALUES (?, ?, ?, ?, ?, ?)",
                    [(u, a, v, x, fuente, momento) for u, a, v, x in filas])
    con.commit()
    variables = sorted({f[2] for f in filas})
    print(f"  {len(filas)} filas, {len({f[0] for f in filas})} distritos: {', '.join(variables)}")


def pnud(con):
    """IDH 2017-2024 por distrito (PNUD) y límites distritales INEI 2025 simplificados (~100 m) para mapas y cruces."""
    import geopandas as gpd
    nombres = {"idh": "idh", "evn": "esperanza_vida", "veaeh": "secundaria_completa", "aedu": "anios_educacion",
               "irpc": "ingreso_pc", "pob": "poblacion"}
    attrs = requests.get(f"{PNUD}/query", headers=UA, timeout=300, params=dict(
        where="1=1", outFields="*", returnGeometry="false", f="json")).json()["features"]
    filas = []
    for f in (x["attributes"] for x in attrs):
        for anio in range(2017, 2025):
            for corto, var in nombres.items():
                v = f.get(f"pob_{anio}" if corto == "pob" else f"{corto}_{anio % 100}")
                if v:  # 0 = distrito creado después, sin dato
                    filas.append((f["ubigeo"], anio, var, float(v)))
    guardar(con, filas, f"{PNUD} (PNUD, IDH distrital 2017-2024)")
    geo = requests.get(f"{PNUD}/query", headers=UA, timeout=600, params=dict(
        where="1=1", outFields="ubigeo,departamen,provincia,distrito", returnGeometry="true", outSR=4326,
        maxAllowableOffset=0.001, f="geojson")).json()
    gpd.GeoDataFrame.from_features(geo["features"], crs=4326).to_file(GEOJSON, driver="GeoJSON")
    print(f"  límites: {len(geo['features'])} distritos → {GEOJSON}")


def pobreza(con):
    """Mapa de pobreza distrital 2018 del INEI: límites del intervalo al 95 % y grupo robusto (1 = más pobre)."""
    import pandas as pd
    t = pd.read_excel(io.BytesIO(requests.get(POBREZA_2018, headers=UA, timeout=300).content), sheet_name="Anexo1",
                      header=None, skiprows=7, dtype={0: str})
    t = t[t[0].str.fullmatch(r"\d{6}", na=False)]
    filas = [(r[0], 2018, var, float(r[col])) for r in t.itertuples(index=False)
             for var, col in (("pobreza_inf", 5), ("pobreza_sup", 6), ("pobreza_grupo", 7))]
    guardar(con, filas, f"{POBREZA_2018} (INEI, Mapa de pobreza monetaria distrital 2018)")


def stock_concesiones(concesiones, hasta):
    """[(ubigeos, año de petitorio, hectáreas, metálica)] → {(ubigeo, año): {variable: valor}}.

    Por año: concesiones nuevas (flujo) y vigentes acumuladas (stock). Si una concesión cae en varios distritos sus
    hectáreas se reparten por igual. shortcut: el catastro solo trae las vigentes o en trámite; las extinguidas
    faltan, así que el stock de años pasados queda corto. Mejorar con el histórico de INGEMMET si se consigue."""
    flujo = defaultdict(lambda: defaultdict(float))
    for ubigeos, anio, ha, metalica in concesiones:
        for u in ubigeos:
            d = flujo[(u, anio)]
            d["concesiones_nuevas"] += 1 / len(ubigeos)
            d["concesiones_nuevas_ha"] += ha / len(ubigeos)
            d["concesiones_metalicas_nuevas_ha"] += ha / len(ubigeos) if metalica else 0
    salida = {}
    for u in {u for u, _ in flujo}:
        acum = defaultdict(float)
        primero = min(a for v, a in flujo if v == u)
        for anio in range(primero, hasta + 1):
            nuevo = flujo.get((u, anio), {})
            for k, x in nuevo.items():
                acum[k.replace("_nuevas", "")] += x
            salida[(u, anio)] = {**{k: round(x, 2) for k, x in nuevo.items()}, **{k: round(x, 2) for k, x in acum.items()}}
    return salida


def catastro(con, desde=2000):
    import truststore
    truststore.inject_into_ssl()
    filas = arcgis(CATASTRO, "DEMAGIS,FEC_DENU,HECTAGIS,SUSTANCIA", lote=2000)
    concesiones = []
    for f in filas:
        ubigeos = sorted(set(re.findall(r"\d{6}", f["DEMAGIS"] or "")))
        if ubigeos and f["FEC_DENU"]:
            anio = (EPOCA + timedelta(milliseconds=f["FEC_DENU"])).year  # hay petitorios anteriores a 1970
            concesiones.append((ubigeos, anio, f["HECTAGIS"] or 0, f["SUSTANCIA"] == "M"))
    stock = stock_concesiones(concesiones, date.today().year)
    guardar(con, [(u, a, k, x) for (u, a), d in stock.items() if a >= desde for k, x in d.items()],
            f"{CATASTRO} (INGEMMET, catastro minero; {len(filas)} concesiones vigentes o en trámite)")


def pasivos(con):
    """Pasivos ambientales mineros por distrito (inventario del MINEM en GEOCATMIN). Foto: anio 0."""
    n, sin = defaultdict(int), 0
    for f in arcgis(PASIVOS, "region,provincia,distrito"):
        f = {k.lower(): v for k, v in f.items()}
        u, prec = resolver(region=f["region"], provincia=f["provincia"], distrito=f["distrito"], pista=f["region"])
        if prec == "distrito":
            n[u] += 1
        else:
            sin += 1
    print(f"  pasivos sin distrito: {sin}")
    guardar(con, [(u, 0, "pasivos_mineros", float(x)) for u, x in n.items()], f"{PASIVOS} (MINEM, inventario de PAM)")


def oefa(con):
    """Operaciones extractivas por distrito, de las capas públicas de OEFA. Foto: anio 0.
    unidades_mineras: unidades fiscalizables cuyo centro cae en el distrito; lote_explotacion / lote_exploracion /
    oleoducto_norperuano: 1 si la capa toca el distrito."""
    import geopandas as gpd
    distritos = gpd.read_file(GEOJSON)[["ubigeo", "geometry"]]
    capas = {"unidades_mineras": f"{OEFA}/SERV_MINERIA_MFICAM_INTERV/MapServer/0",
             "lote_explotacion": f"{OEFA}/SERV_HID_MFICAM_INTERV/MapServer/1",
             "lote_exploracion": f"{OEFA}/SERV_HID_MFICAM_INTERV/MapServer/2",
             "oleoducto_norperuano": f"{OEFA}/SERV_HID_MFICAM_INTERV/MapServer/4"}
    for var, capa in capas.items():
        g = gpd.GeoDataFrame.from_features(arcgis(capa, "OBJECTID", geometria=True, lote=200), crs=4326)
        g = g[g.geometry.notna() & ~g.geometry.is_empty]
        if var == "unidades_mineras":  # el centro, para no contar una mina en todos los distritos que roza
            g = g.set_geometry(g.to_crs(32718).geometry.centroid.to_crs(4326))
            cruce = gpd.sjoin(g, distritos, predicate="within").groupby("ubigeo").size()
        else:
            cruce = gpd.sjoin(distritos, g, predicate="intersects").groupby("ubigeo").size().clip(upper=1)
        guardar(con, [(u, 0, var, float(x)) for u, x in cruce.items()], f"{capa} (OEFA, {len(g)} elementos)")


def resultados_electorales(t):
    """Mesas de la ONPE (una fila por mesa y lista) → {ubigeo: {variable: valor}} de la elección distrital.

    margen_victoria: (1.º - 2.º) / votos válidos; listas: con al menos un voto; nep_listas: número efectivo de
    listas (1 / Σ participación²); voto_ganador: participación del ganador; participacion: emitidos / electores."""
    t = t[t["TIPO_ELECCION"].str.contains("DISTRITAL", na=False)]
    mesa = t.groupby(["UBIGEO", "MESA"]).agg(electores=("ELECTORES_HABILES", "max"), validos=("VOTOS_OBTENIDOS", "sum"),
                                             otros=("otros", "max"))  # max: hay filas partidas en 0
    mesa["emitidos"] = mesa["validos"] + mesa["otros"]
    part = mesa.groupby("UBIGEO")[["electores", "emitidos"]].sum()
    votos = t.groupby(["UBIGEO", "AGRUPACION_POLITICA"])["VOTOS_OBTENIDOS"].sum()
    salida = {}
    for u, v in votos[votos > 0].groupby(level=0):
        s = v.sort_values(ascending=False).to_numpy() / v.sum()
        salida[u] = {"margen_victoria": round(s[0] - (s[1] if len(s) > 1 else 0), 4), "listas": float(len(s)),
                     "nep_listas": round(1 / (s ** 2).sum(), 3), "voto_ganador": round(s[0], 4),
                     "participacion": round(part.emitidos[u] / part.electores[u], 4) if part.electores[u] else None}
    return salida


def ubigeo_inei(departamento, provincia, distrito):
    """La ONPE usa el ubigeo de RENIEC: se traduce por nombre. Si el nombre no calza tal cual (guiones, nombres
    truncados, otra grafía) se toma el distrito más parecido de la misma provincia. shortcut: 5-7 distritos por
    elección quedan fuera (renombrados, p. ej. Mariscal Gamarra, Hualla, o que cambiaron de provincia, como Putumayo);
    agregar un alias en lugares.ALIAS si alguno importa para el modelo."""
    import difflib
    u, prec = resolver(region=departamento, provincia=provincia, distrito=distrito, pista=departamento)
    if prec != "provincia":
        return u if prec == "distrito" else None
    nombres = {norm(n).replace(" ", ""): c for c, n in catalogo()[3].items() if len(c) == 6 and c.startswith(u)}
    cerca = difflib.get_close_matches(norm(distrito).replace(" ", ""), nombres, n=1, cutoff=0.8)
    return nombres[cerca[0]] if cerca else None


def onpe(con):
    """Política local por distrito en cada elección municipal (año de la elección, en octubre/noviembre)."""
    import pandas as pd
    filas = []
    for anio, sufijo in ELECCIONES.items():
        url = ONPE.format(anio=anio, sufijo=sufijo)
        crudo = requests.get(url, headers=UA, timeout=600).content
        if sufijo.endswith("zip"):
            with zipfile.ZipFile(io.BytesIO(crudo)) as z:
                crudo = z.read(z.namelist()[0])
        utf8 = crudo.count(b"\xc3") > crudo.count(b"\xd1")  # 2022 viene en UTF-8; los demás en Latin-1
        t = pd.read_csv(io.BytesIO(crudo), sep=";", quoting=3, dtype={0: str},  # hay comillas sueltas
                        encoding="utf-8" if utf8 else "latin-1", encoding_errors="replace",
                        on_bad_lines="skip")  # 2022 trae 6 líneas cortadas de 542 813
        t = t.rename(columns={t.columns[0]: "UBIGEO", "VOTOS_IMPUGNADOS": "VOTOS_IMPUG"})  # el 1.º trae BOM
        lugares = t.drop_duplicates("UBIGEO")
        mapa = {r: ubigeo_inei(d, p, x) for r, d, p, x in
                zip(lugares.UBIGEO, lugares.DEPARTAMENTO, lugares.PROVINCIA, lugares.DISTRITO)}
        t["UBIGEO"] = t["UBIGEO"].map(mapa)
        for c in ("VOTOS_OBTENIDOS", "ELECTORES_HABILES", "VOTOS_BLANCOS", "VOTOS_NULOS", "VOTOS_IMPUG"):
            t[c] = pd.to_numeric(t[c], errors="coerce").fillna(0)
        t["otros"] = t[["VOTOS_BLANCOS", "VOTOS_NULOS", "VOTOS_IMPUG"]].sum(axis=1)
        res = resultados_electorales(t[t["UBIGEO"].notna()])
        sin = sorted(f"{d}/{p}/{x}" for (r, u), d, p, x in zip(mapa.items(), lugares.DEPARTAMENTO, lugares.PROVINCIA,
                                                                 lugares.DISTRITO) if u is None)
        print(f"  {anio}: {len(res)} distritos; sin traducir {len(sin)}: {sin[:6]}")
        filas += [(u, anio, k, x) for u, d in res.items() for k, x in d.items()]
    guardar(con, filas, "https://www.datosabiertos.gob.pe (ONPE, resultados por mesa ERM municipal distrital "
                        "2006-2022)")


def porcentaje_cubierto(distritos, capa):
    """Fracción del área de cada distrito cubierta por la capa (polígonos), en una proyección de áreas iguales."""
    import geopandas as gpd
    d = distritos.to_crs("ESRI:102033")
    c = gpd.GeoDataFrame(geometry=[capa.to_crs("ESRI:102033").union_all()], crs="ESRI:102033")
    inter = gpd.overlay(d, c, how="intersection")
    return (inter.set_index("ubigeo").area / d.set_index("ubigeo").area).dropna().clip(upper=1)


def comunidades(con):
    """Comunidades campesinas y nativas (territorios) y reservas para pueblos en aislamiento, de la Base de Datos de
    Pueblos Indígenas (BDPI) del Ministerio de Cultura. Foto: anio 0."""
    import json
    import geopandas as gpd
    distritos = gpd.read_file(GEOJSON)[["ubigeo", "geometry"]]
    filas = []
    for capa, nombre_capa in ((2, "comunidades"), (5, "reserva_indigena")):
        r = requests.get(BDPI, params={"ipInput": json.dumps({"id_capa": capa, "codubigeo": ""})}, headers=UA,
                         timeout=600).json()
        g = gpd.GeoDataFrame.from_features(r["mensaje"], crs=4326)
        g = g[g.geometry.notna()]
        g["geometry"] = g.geometry.make_valid()  # ~140 territorios vienen con geometría mal formada
        cubierto = porcentaje_cubierto(distritos, g)
        filas += [(u, 0, f"{nombre_capa}_pct_territorio", round(float(x), 4)) for u, x in cubierto.items() if x > 0]
        if capa == 2:  # cuántas comunidades: por el centro del territorio
            centro = g.set_geometry(g.to_crs(32718).geometry.centroid.to_crs(4326))
            n = gpd.sjoin(centro, distritos, predicate="within").groupby("ubigeo").size()
            filas += [(u, 0, "comunidades", float(x)) for u, x in n.items()]
        print(f"  BDPI capa {capa}: {len(g)} polígonos")
    guardar(con, filas, f"{BDPI} (Ministerio de Cultura, BDPI: capa 2 comunidades campesinas y nativas, capa 5 "
                        "reservas indígenas)")


RESERVADA = f"{GEOCATMIN}/SERV_AREA_RESERVADA/MapServer"
CARTERA = f"{GEOCATMIN}/SERV_CARTERA_PROYECTOS_MINEROS/MapServer"


def ambiente(con):
    """Áreas naturales protegidas y sus zonas de amortiguamiento (SERNANP, en GEOCATMIN), cartera de proyectos
    mineros 2023 y método de las minas en operación (MINEM). Foto: anio 0.
    shortcut: la cartera es la de 2023 y se usa para todos los años; los EIA/DIA de GEOCATMIN acaban en 2016
    (luego pasaron al SENACE) y no se usan. Si el SENACE publica su registro con fechas, entra como serie."""
    import geopandas as gpd
    distritos = gpd.read_file(GEOJSON)[["ubigeo", "geometry"]]
    filas = []
    for capa, var in ((13, "anp_pct_territorio"), (12, "amortiguamiento_pct_territorio")):
        g = gpd.GeoDataFrame.from_features(arcgis(f"{RESERVADA}/{capa}", "nombre", geometria=True, lote=50), crs=4326)
        g["geometry"] = g.geometry.make_valid()
        filas += [(u, 0, var, round(float(x), 4)) for u, x in porcentaje_cubierto(distritos, g[g.geometry.notna()]).items()
                  if x > 0]
        print(f"  {var}: {len(g)} polígonos")
    puntos = lambda capa, campos: gpd.sjoin(gpd.GeoDataFrame.from_features(
        arcgis(f"{CARTERA}/{capa}", campos, geometria=True), crs=4326), distritos, predicate="within")
    p = puntos(1, "nom_proy,est_proy")
    filas += [(u, 0, "proyectos_cartera", float(n)) for u, n in p.groupby("ubigeo").size().items()]
    m = puntos(0, "proyecto,metodo_de")
    for metodo, var in (("SUPERFICIAL", "minas_tajo_abierto"), ("SUBTERR", "minas_subterraneas")):
        n = m[m.metodo_de.fillna("").str.upper().str.contains(metodo)].groupby("ubigeo").size()
        filas += [(u, 0, var, float(x)) for u, x in n.items()]
    guardar(con, filas, f"{RESERVADA} capas 12-13 (SERNANP); {CARTERA} capas 0-1 (MINEM, cartera 2023 y minas)")


SENACE = ("https://geosenace.senace.gob.pe/arcgis/rest/services/INTEROPERABILIDAD/"
          "peru_senace_007_certificaciones_ambientales/MapServer/0")


def senace(con):
    """Certificaciones ambientales aprobadas (SENACE y las que heredó de los sectores, 1995-2026) de minería,
    hidrocarburos y electricidad, ubicadas en su distrito por coordenadas → tabla senace_certificacion. El modelo
    cuenta las aprobadas por año: un EIA nuevo es el gatillo clásico de conflicto."""
    import geopandas as gpd
    import pandas as pd
    d = pd.DataFrame(arcgis(SENACE, "EXPEDIENTE,ACTIVIDAD,NOM_PROY,IGA_TIPO,TIT_PROY,FECHA_RD,LONGITUD,LATITUD"))
    d = d[d.ACTIVIDAD.isin(["Minería", "Hidrocarburos", "Electricidad"]) & d.LONGITUD.notna() & d.FECHA_RD.notna()]
    fecha = pd.to_datetime(d.FECHA_RD, unit="ms")
    g = gpd.GeoDataFrame(d.assign(anio=fecha.dt.year, mes=fecha.dt.month),
                         geometry=gpd.points_from_xy(d.LONGITUD, d.LATITUD), crs=4326)
    g = gpd.sjoin(g, gpd.read_file(GEOJSON)[["ubigeo", "geometry"]], predicate="within")
    g = g.rename(columns={"EXPEDIENTE": "expediente", "ACTIVIDAD": "actividad", "NOM_PROY": "proyecto",
                          "IGA_TIPO": "tipo", "TIT_PROY": "titular"})
    g[["ubigeo", "anio", "mes", "expediente", "actividad", "tipo", "proyecto", "titular"]].to_sql(
        "senace_certificacion", con, if_exists="replace", index=False)
    con.commit()
    print(f"  {len(g)} certificaciones extractivas en {g.ubigeo.nunique()} distritos ({SENACE})")


ANA = "https://geosnirh.ana.gob.pe/server/rest/services/ONRH"
ESTRES = {"Sin presión": 0, "Estrés hídrico ocasional": 1, "Estrés hídrico medio": 2, "Escasez de agua crónica": 3,
          "Escasez hídrica absoluta": 4}


def ana(con):
    """Autoridad Nacional del Agua (SNIRH): conflictos hídricos que sigue la ANA (zona de conflicto, zona crítica y
    conflicto potencial) por distrito, y estrés hídrico (0-4, disponibilidad per cápita) de la unidad hidrográfica
    del centro del distrito. Foto: anio 0.
    shortcut: las capas de la ANA son la situación actual, sin fechas; se usan para todos los años."""
    import geopandas as gpd
    import pandas as pd
    distritos = gpd.read_file(GEOJSON)[["ubigeo", "geometry"]]
    puntos = pd.concat([gpd.GeoDataFrame.from_features(arcgis(f"{ANA}/{s}/MapServer/0", "OBJECTID", geometria=True),
                                                       crs=4326) for s in ("Zona_de_Conflicto", "Zona_Critica",
                                                                           "Conflicto_Potencial")])
    n = gpd.sjoin(puntos, distritos, predicate="within").groupby("ubigeo").size()
    filas = [(u, 0, "conflictos_hidricos_ana", float(x)) for u, x in n.items()]
    uh = gpd.GeoDataFrame.from_features(arcgis(f"{ANA}/Disponibilidad_Per_Capita_por_Unidad_Hidrografica/MapServer/0",
                                               "DESCRIPCION", geometria=True, lote=20), crs=4326)
    centro = distritos.set_geometry(distritos.to_crs(32718).geometry.centroid.to_crs(4326))
    j = gpd.sjoin(centro, uh[uh.DESCRIPCION.isin(ESTRES)], predicate="within").drop_duplicates("ubigeo")
    filas += [(u, 0, "estres_hidrico", float(ESTRES[d])) for u, d in zip(j.ubigeo, j.DESCRIPCION)]
    print(f"  {len(puntos)} conflictos hídricos en {len(n)} distritos; estrés hídrico en {len(j)} distritos")
    guardar(con, filas, f"{ANA} (ANA, SNIRH: Zona_de_Conflicto, Zona_Critica, Conflicto_Potencial, "
                        "Disponibilidad_Per_Capita_por_Unidad_Hidrografica)")


OEFA_DENUNCIAS = "https://pifa.oefa.gob.pe/server_gis/rest/services/Metadatos/Denuncias_Ambientales/MapServer/0"
EMERGENCIAS = "https://geosnirh.ana.gob.pe/server/rest/services/P%C3%BAblico/EventosEmergenciasHidricas/MapServer/107"


def oefa_denuncias(con):
    """Denuncias ambientales ante el OEFA contra minería, hidrocarburos y electricidad, total por distrito. Solo se
    guarda el conteo: el texto de la denuncia nombra a personas.
    shortcut: el OEFA publica 2018-2024; como serie caería a cero en 2025-2026, así que entra como foto (anio 0).
    Pasar a serie mensual cuando publique los años que faltan."""
    import geopandas as gpd
    import pandas as pd
    d = pd.DataFrame(arcgis(OEFA_DENUNCIAS, "NOM_ACTIVIDAD,COOR_X,COOR_Y"))
    d = d[d.NOM_ACTIVIDAD.isin(["Minería", "Hidrocarburos", "Electricidad"])]
    # COOR_X trae la latitud y COOR_Y la longitud (vienen cruzadas).
    lat, lon = pd.to_numeric(d.COOR_X, errors="coerce"), pd.to_numeric(d.COOR_Y, errors="coerce")
    g = gpd.GeoDataFrame(d, geometry=gpd.points_from_xy(lon, lat), crs=4326)
    n = gpd.sjoin(g[lat.notna().to_numpy()], gpd.read_file(GEOJSON)[["ubigeo", "geometry"]],
                  predicate="within").groupby("ubigeo").size()
    print(f"  {len(d)} denuncias extractivas, {n.sum()} ubicadas en {len(n)} distritos")
    guardar(con, [(u, 0, "denuncias_oefa_extractivas", float(x)) for u, x in n.items()],
            f"{OEFA_DENUNCIAS} (OEFA, denuncias ambientales 2018-2024: minería, hidrocarburos, electricidad)")


def emergencias(con):
    """Emergencias por lluvias, huaicos, inundaciones, sequías y heladas (reportes del INDECI recogidos por la ANA en
    su visor de emergencias hídricas), con fecha y punto → tabla emergencia(ubigeo, anio, mes, tipo)."""
    import geopandas as gpd
    import pandas as pd
    g = gpd.GeoDataFrame.from_features(arcgis(EMERGENCIAS, "TipoEvento,FechaHora", geometria=True), crs=4326)
    fecha = pd.to_datetime(g.FechaHora, format="%d/%m/%Y %H:%M", errors="coerce")
    g = g.assign(anio=fecha.dt.year, mes=fecha.dt.month, tipo=g.TipoEvento)[fecha.notna() & g.geometry.notna()]
    g = gpd.sjoin(g, gpd.read_file(GEOJSON)[["ubigeo", "geometry"]], predicate="within")
    g[["ubigeo", "anio", "mes", "tipo"]].to_sql("emergencia", con, if_exists="replace", index=False)
    con.commit()
    print(f"  {len(g)} emergencias en {g.ubigeo.nunique()} distritos, {int(g.anio.min())}-{int(g.anio.max())} "
          f"({EMERGENCIAS})")


ACLED = DATOS / "crudos" / "acled" / "acled_peru.csv"
# las notas de ACLED están en inglés; se excluyen los reclamos de mineros informales y los laborales (como en modelo.py)
ACLED_EXTRACTIVO = re.compile(r"\bmin(?:e|es|ing|ers?)\b|\boil\b|petro|hydrocarbon|\bgas (?:field|pipeline)|camisea|"
                              r"pipeline|las bambas|tia maria|antamina|conga|yanacocha|quellaveco|\bdams?\b|"
                              r"hydroelectric|\bcanon\b|royalt", re.I)
ACLED_NO = re.compile(r"informal|artisanal (?!fish)|reinfo|formali[sz]ation|small-scale|wages?|unions?|labou?r", re.I)


def acled(con):
    """Eventos de ACLED en el Perú 2018-2025 (protestas, disturbios y violencia), con fecha y punto → tabla
    acled_evento(ubigeo, anio, mes, tipo, subtipo, extractivo). Sirve para validar la alerta con una fuente
    independiente. El CSV se baja a mano del Data Export Tool (requiere cuenta). No se guardan las notas ni los
    actores (pueden nombrar personas)."""
    import geopandas as gpd
    import pandas as pd
    d = pd.read_csv(ACLED)
    fecha = pd.to_datetime(d.event_date)
    texto = d.notes.fillna("") + " " + d.actor1.fillna("") + " " + d.assoc_actor_1.fillna("")
    d = d.assign(anio=fecha.dt.year, mes=fecha.dt.month, tipo=d.event_type, subtipo=d.sub_event_type,
                 extractivo=texto.str.contains(ACLED_EXTRACTIVO) & ~texto.str.contains(ACLED_NO))
    g = gpd.GeoDataFrame(d, geometry=gpd.points_from_xy(d.longitude, d.latitude), crs=4326)
    g = gpd.sjoin(g, gpd.read_file(GEOJSON)[["ubigeo", "geometry"]], predicate="within")
    g[["ubigeo", "anio", "mes", "tipo", "subtipo", "extractivo"]].to_sql("acled_evento", con, if_exists="replace",
                                                                        index=False)
    con.commit()
    print(f"  {len(g)} de {len(d)} eventos en {g.ubigeo.nunique()} distritos, {g.extractivo.sum()} extractivos, "
          f"{int(g.anio.min())}-{int(g.anio.max())} (ACLED, acleddata.com)")


GEOBOSQUES = DATOS / "crudos" / "geobosques" / "Bosque_y_perdida_de_bosques_por_Distrito_al_2025.xlsx"


def geobosques(con):
    """Pérdida de bosque húmedo amazónico por distrito y año 2001-2025 (MINAM, GEOBOSQUES). El Excel se baja a mano
    de geobosques.minam.gob.pe/geobosque/view/descargas.php ("... por distritos (Excel)"): el sitio bloquea las
    descargas automáticas."""
    import pandas as pd
    x = pd.read_excel(GEOBOSQUES, header=None, skiprows=8, dtype={3: str})
    x = x[x[3].str.fullmatch(r"\d{6}", na=False)]
    anios = {**{c: 2001 + c - 5 for c in range(5, 29)}, 32: 2025}  # columnas 5-28: 2001-2024; 32: total 2025
    filas = [(u, a, "perdida_bosque_ha", round(float(v), 2)) for _, r in x.iterrows() for c, a in anios.items()
             for u, v in [(r[3], r[c])] if pd.notna(v)]
    filas += [(r[3], 0, "bosque_2025_ha", round(float(r[34]), 2)) for _, r in x.iterrows() if pd.notna(r[34])]
    guardar(con, filas, "https://geobosques.minam.gob.pe/geobosque/view/descargas.php (MINAM, GEOBOSQUES: bosque y "
                        "pérdida de bosque 2001-2025 por distritos)")


RENAMU = "https://proyectos.inei.gob.pe/iinei/srienaho/descarga/STATA/902-Modulo1814.zip"  # RENAMU 2023


def renamu(con):
    """Registro Nacional de Municipalidades 2023 (INEI): rondas campesinas, oficina ambiental, atención de denuncias
    ambientales, formas de participación ciudadana y personal municipal. Foto: anio 0.
    shortcut: un solo año (2023) para todos los meses; cada año tiene otro código de encuesta en el INEI."""
    import pandas as pd
    carpeta = DATOS / "crudos" / "renamu"
    carpeta.mkdir(parents=True, exist_ok=True)
    zipf = carpeta / "902-Modulo1814-STATA.zip"
    if not zipf.exists():
        zipf.write_bytes(requests.get(RENAMU, headers=UA, timeout=600).content)
    with zipfile.ZipFile(zipf) as z:
        dta = next(n for n in z.namelist() if n.endswith(".dta"))
        participa = [f"P100_{i}" for i in range(1, 11)]
        d = pd.read_stata(io.BytesIO(z.read(dta)), columns=["Ubigeo", "P79_2", "P96", "P99_8", "P19D_T", *participa],
                          convert_categoricals=False)
    d = d.assign(ronda_campesina=d.P79_2.eq(1), oficina_ambiental=d.P96.eq(1), atiende_denuncias_ambientales=d.P99_8 > 0,
                 participacion_formas=(d[participa].fillna(0) > 0).sum(axis=1), personal_municipal=d.P19D_T)
    filas = [(str(r.Ubigeo), 0, v, float(getattr(r, v))) for r in d.itertuples() for v in
             ("ronda_campesina", "oficina_ambiental", "atiende_denuncias_ambientales", "participacion_formas",
              "personal_municipal") if pd.notna(getattr(r, v))]
    guardar(con, filas, f"{RENAMU} (INEI, RENAMU 2023: P79_2, P96, P99_8, P100_1-10, P19D_T)")


def vias(con):
    """Red vial nacional (MTC, en GEOCATMIN): km de vía nacional por distrito y los corredores logísticos que lo
    atraviesan (tabla distrito_corredor, para la alerta por corredor)."""
    import geopandas as gpd
    import pandas as pd
    distritos = gpd.read_file(GEOJSON)[["ubigeo", "geometry"]]
    g = gpd.GeoDataFrame.from_features(arcgis(VIA_NACIONAL, "ccodruta_4,ccodcorlog", geometria=True, lote=500), crs=4326)
    tramos = gpd.overlay(g[g.geometry.notna()], distritos, how="intersection", keep_geom_type=True)
    tramos["km"] = tramos.to_crs("ESRI:102033").length / 1000
    km = tramos.groupby("ubigeo").km.sum()
    guardar(con, [(u, 0, "via_nacional_km", round(float(x), 2)) for u, x in km.items()],
            f"{VIA_NACIONAL} (MTC, red vial nacional; {len(g)} tramos)")
    # Código del MTC: C01…C20 corredores logísticos, AL… vías alimentadoras. Los corredores con nombre propio que
    # importan para la minería se definen por su ruta (el MTC los cuenta como alimentadores).
    tramos["corredor"] = tramos.ccodcorlog.str.strip()
    propios = pd.concat([tramos[tramos.ccodruta_4.isin(rutas)].assign(corredor=n) for n, rutas in CORREDORES.items()])
    corr = (pd.concat([tramos[tramos.corredor.str.match(r"^(C|AL)\d+$")], propios])
            .groupby(["ubigeo", "corredor"]).agg(rutas=("ccodruta_4", lambda s: ", ".join(sorted(set(s)))),
                                                 km=("km", "sum")).reset_index())
    corr.to_sql("distrito_corredor", con, if_exists="replace", index=False)
    con.commit()
    print(f"  corredores logísticos: {corr.corredor.nunique()} en {corr.ubigeo.nunique()} distritos")


REDATAM = "https://censos2017.inei.gob.pe/bininei/RpWebStats.exe/AreaList?"
NO_INDIGENA = {"Castellano", "Portugués", "Otra lengua extranjera", "Lengua de señas peruanas", "No escucha, ni habla",
               "No sabe / No responde"}
CENSO = {  # variable: (ITEM, VARIABLE de REDATAM, categorías del numerador según las columnas)
    # PENCARE (concepto encuesta) reproduce el 20,7 % rural oficial; PAREA (censal) da 17,6 %.
    "rural": ("AREAPOB", "Poblacio.PENCARE", lambda c: ["Rural encuesta"]),
    "lengua_indigena": ("AREAPOB", "Poblacio.C5P11", lambda c: [x for x in c if x not in NO_INDIGENA]),
    "autoidentificacion_indigena": ("AREAPOB", "Poblacio.C5P25", lambda c: [
        "Quechua", "Aimara", "Nativo o indígena de la amazonía", "Parte de otro pueblo indígena u originario"]),
    "sin_agua_red": ("AREAVIV", "Vivienda.C2P6", lambda c: [x for x in c if not x.startswith("Red pública")]),
    "sin_electricidad": ("AREAVIV", "Vivienda.C2P11", lambda c: ["No tiene alumbrado eléctrico"]),
}


def redatam(sesion, item, variable):
    """Una tabla 'Lista de áreas' del REDATAM del Censo 2017 por distrito: filas = ubigeo, columnas = categorías.
    Es un POST que devuelve un iframe con el archivo temporal del resultado, que se baja aparte."""
    import time
    import lxml.html
    import pandas as pd
    form = dict(MAIN="WebServerMain.inl", BASE="CPV2017DI", LANG="esp", CODIGO="XXUSUARIOXX", ITEM=item, MODE="RUN",
                inputTitle="", VARIABLE=variable, OUTPUT="Distrito", WEIGHT="", SELECTION="ALL", INLINESELECTION="",
                FORMAT="HTML", TOTCOL="on", UNIVERSE="", FILTER="", TEXT_FILTER="", Submit="Ejecutar")
    r = sesion.post(REDATAM, data=form, timeout=600)
    r.raise_for_status()
    url = re.search(r'src="([^"]*~tmp[^"]*\.htm[^"]*)"', r.text).group(1).replace("&amp;", "&")
    time.sleep(2)
    r = sesion.get(url, timeout=600)
    r.raise_for_status()
    filas = [[td.text_content().strip() for td in tr.findall("td")]
             for tr in lxml.html.fromstring(r.content.decode("utf-8")).iter("tr")]
    cab = next(i for i, f in enumerate(filas) if "Código" in f)
    j = filas[cab].index("Código")
    cats = [c for c in filas[cab][j + 2:] if c]
    datos = {f[j]: [int(re.sub(r"\D", "", v) or 0) for v in f[j + 2:j + 2 + len(cats)]]
             for f in filas[cab + 1:] if len(f) > j and re.fullmatch(r"\d{6}", f[j])}
    return pd.DataFrame.from_dict(datos, orient="index", columns=cats)


def censo(con):
    """Censo 2017 (INEI, REDATAM): ruralidad, lengua materna e identidad indígena, servicios. Año 2017."""
    import time
    sesion, filas = requests.Session(), []
    sesion.headers.update(UA)
    for var, (item, variable, numerador) in CENSO.items():
        t = redatam(sesion, item, variable)
        n, d = t[numerador(t.columns)].sum(axis=1), t.sum(axis=1)
        filas += [(u, 2017, var, round(float(x), 4)) for u, x in (n / d).items()]
        if var == "rural":
            filas += [(u, 2017, "poblacion_censada", float(x)) for u, x in d.items()]
        print(f"  {var}: {len(t)} distritos, nacional {n.sum() / d.sum():.1%}")
        time.sleep(5)
    guardar(con, filas, f"{REDATAM} (INEI, Censos Nacionales 2017, REDATAM CPV2017DI)")


PASOS = {"pnud": pnud, "pobreza": pobreza, "catastro": catastro, "pasivos": pasivos, "oefa": oefa, "onpe": onpe,
         "comunidades": comunidades, "vias": vias, "censo": censo, "ambiente": ambiente, "senace": senace, "ana": ana, "oefa_denuncias": oefa_denuncias, "emergencias": emergencias, "geobosques": geobosques, "renamu": renamu, "acled": acled}

if __name__ == "__main__":
    ap = argparse.ArgumentParser(prog="python -m tremor.distritos")
    ap.add_argument("paso", choices=[*PASOS, "todo"])
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    con = conectar()
    for nombre, paso in PASOS.items():
        if a.paso in (nombre, "todo"):
            print(nombre)
            paso(con)
    (DATOS / "exportes").mkdir(parents=True, exist_ok=True)
    con.execute("SELECT 1 FROM distrito_variable LIMIT 1")  # falla si nunca se cargó nada
    import pandas as pd
    pd.read_sql("SELECT ubigeo, anio, variable, valor, fuente FROM distrito_variable ORDER BY ubigeo, variable, anio",
                con).to_csv(DATOS / "exportes" / "distrito_variable.csv", index=False)
