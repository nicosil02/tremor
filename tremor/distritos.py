"""Perfil distrital de todo el Perú: variables por ubigeo y año para el modelo (spec en specs/005-modelo).

Una sola tabla larga, `distrito_variable(ubigeo, anio, variable, valor, fuente)`. `anio` es el año del dato; 0 marca
una foto sin serie (p. ej. dónde hay una operación hoy). Fuentes verificadas el 7 nov 2026:
- PNUD: IDH distrital 2017-2024 y sus componentes; su capa trae también los límites INEI 2025 (`datos/distritos.geojson`).
- INEI: mapa de pobreza distrital 2018 (intervalo de confianza al 95 %).
- INGEMMET (GEOCATMIN): catastro minero (concesiones con fecha de petitorio) y pasivos ambientales mineros.
- OEFA (PIFA): unidades mineras fiscalizadas, lotes de hidrocarburos y el Oleoducto Norperuano.

`python -m tremor.distritos {pnud,pobreza,catastro,pasivos,oefa,todo}`
"""
import argparse
import io
import re
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

import requests

from tremor.db import DATOS, ahora, conectar
from tremor.lugares import resolver
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
EPOCA = datetime(1970, 1, 1, tzinfo=timezone.utc)
ESQUEMA = """CREATE TABLE IF NOT EXISTS distrito_variable (
    ubigeo TEXT NOT NULL, anio INTEGER NOT NULL, variable TEXT NOT NULL, valor REAL, fuente TEXT,
    consultado TEXT NOT NULL, PRIMARY KEY (ubigeo, anio, variable))"""


def arcgis(capa, campos="*", geometria=False, lote=500):
    """Todas las filas de una capa ArcGIS REST: primero los ids y luego lotes por objectIds (GEOCATMIN no pagina
    con resultOffset). Con geometría devuelve GeoJSON en WGS84."""
    ids = requests.post(f"{capa}/query", data=dict(where="1=1", returnIdsOnly="true", f="json"), headers=UA,
                        timeout=300).json()["objectIds"] or []
    salida = []
    for i in range(0, len(ids), lote):
        r = requests.post(f"{capa}/query", headers=UA, timeout=300, data=dict(
            objectIds=",".join(map(str, sorted(ids)[i:i + lote])), outFields=campos, outSR=4326,
            returnGeometry=str(geometria).lower(), f="geojson" if geometria else "json")).json()
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


PASOS = {"pnud": pnud, "pobreza": pobreza, "catastro": catastro, "pasivos": pasivos, "oefa": oefa}

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
