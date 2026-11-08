"""Vista por empresa: sus operaciones (OEFA) y la alerta de la zona de cada una.

    python -m tremor.empresas cargar          # tabla operacion(empresa, unidad, tipo, ubigeo) desde OEFA
    python -m tremor.empresas "las bambas"    # la alerta de cada operación y cómo le habría ido en 2024+
"""
import sys

import pandas as pd

from tremor.db import RAIZ, conectar
from tremor.distritos import GEOJSON, OEFA, arcgis
from tremor.lugares import norm

CAPAS = {"mineria": f"{OEFA}/SERV_MINERIA_MFICAM_INTERV/MapServer/0",
         "hidrocarburos": f"{OEFA}/SERV_HID_MFICAM_INTERV/MapServer/1"}


def cargar(con):
    """Una fila por unidad fiscalizable y distrito. Minas: el distrito del centro de la unidad (como `oefa`);
    lotes en explotación: todos los distritos que tocan."""
    import geopandas as gpd
    distritos = gpd.read_file(GEOJSON)[["ubigeo", "geometry"]]
    filas, huellas = [], []
    for tipo, capa in CAPAS.items():
        g = gpd.GeoDataFrame.from_features(arcgis(capa, "OBJECTID,ADMINISTRADO,UNIDAD_FISCALIZABLE", geometria=True,
                                                  lote=200), crs=4326)
        g = g[g.geometry.notna() & ~g.geometry.is_empty]
        g["geometry"] = g.geometry.make_valid()
        g = g.dissolve(by=["ADMINISTRADO", "UNIDAD_FISCALIZABLE"]).reset_index()
        huellas.append(g.assign(tipo=tipo, geometry=g.geometry.simplify(0.0005))[
            ["ADMINISTRADO", "UNIDAD_FISCALIZABLE", "tipo", "geometry"]])
        if tipo == "mineria":
            g = g.set_geometry(g.to_crs(32718).geometry.centroid.to_crs(4326))
            cruce = gpd.sjoin(g, distritos, predicate="within")
        else:
            cruce = gpd.sjoin(g, distritos, predicate="intersects")
        filas.append(pd.DataFrame({"empresa": cruce.ADMINISTRADO.str.strip(), "unidad": cruce.UNIDAD_FISCALIZABLE.str.strip(),
                                   "tipo": tipo, "ubigeo": cruce.ubigeo}))
    t = pd.concat(filas).drop_duplicates()
    t.to_sql("operacion", con, if_exists="replace", index=False)
    con.commit()
    print(f"{len(t)} operaciones-distrito de {t.empresa.nunique()} empresas (OEFA)")
    h = pd.concat(huellas).rename(columns={"ADMINISTRADO": "empresa", "UNIDAD_FISCALIZABLE": "unidad"})
    h["empresa"], h["unidad"] = h.empresa.str.strip(), h.unidad.str.strip()
    import re
    texto = gpd.GeoDataFrame(h, crs=4326).to_json(drop_id=True)
    (RAIZ / "docs" / "operaciones.json").write_text(re.sub(r"(\d+\.\d{4})\d+", r"\1", texto), encoding="utf-8")  # huella de cada unidad, para el mapa


def vista(con, texto):
    """Operaciones de las empresas cuyo nombre (o el de la unidad) contiene `texto`, con la alerta de su zona."""
    op = pd.read_sql("SELECT * FROM operacion", con)
    t = norm(texto)
    op = op[[t in norm(f"{e} {u}") for e, u in zip(op.empresa, op.unidad)]]
    al = pd.read_sql("SELECT ubigeo, lugar, prob_zona, prob_zona_extractivo, razones_zona_extractivo, puesto_zona, "
                     "puesto_zona_extractivo, alerta_inmediata, senal_prensa, animo_proyectos, ventana FROM alerta", con)
    v = op.merge(al, on="ubigeo", how="left")
    return v.sort_values("prob_zona_extractivo", ascending=False)


def historial(con, texto, top=0.10):
    """Cómo le habría ido a la empresa en la prueba (2024+): en cada mes, la zona de cada operación queda "en alerta"
    si está en el `top` de zonas con operación. Cuenta los meses con medida de fuerza en los 3 siguientes
    (eventos), cuántos tuvo en alerta antes (vistos) y cuántas alertas acertaron. Modelo frente a la regla ingenua."""
    ubigeos = set(vista(con, texto).ubigeo)
    pr = pd.read_sql("SELECT * FROM modelo_prediccion", con)
    pr = pr[pr.ubigeo.isin(ubigeos)].assign(alerta=lambda d: d.pct <= top)
    g = pr.groupby(["objetivo", "modelo"]).apply(lambda d: pd.Series({
        "zonas": d.ubigeo.nunique(), "meses_zona": len(d), "eventos": int(d.y.sum()),
        "vistos": int((d.y.astype(bool) & d.alerta).sum()), "alertas": int(d.alerta.sum())}), include_groups=False)
    g["pct_vistos"] = (g.vistos / g.eventos.clip(lower=1)).round(2)
    g["acierto_alertas"] = (g.vistos / g.alertas.clip(lower=1)).round(2)
    return g.reset_index()


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    con = conectar()
    if sys.argv[1:] == ["cargar"]:
        return cargar(con)
    texto = " ".join(sys.argv[1:])
    v = vista(con, texto)
    with pd.option_context("display.width", 250, "display.max_colwidth", 70):
        print(v[["empresa", "unidad", "lugar", "prob_zona", "prob_zona_extractivo", "puesto_zona_extractivo",
                 "alerta_inmediata", "razones_zona_extractivo"]].to_string(index=False))
        print(historial(con, texto).to_string(index=False))


if __name__ == "__main__":
    main()
