"""Comunidades campesinas y nativas alrededor de las operaciones, para el mapa: su territorio (BDPI, Ministerio de
Cultura) y, si la Defensoría tiene un conflicto abierto con su nombre, el estado de ese conflicto.

    python -m tremor.comunidades      # escribe docs/comunidades.json (lee docs/web.json para las zonas y los casos)

La BDPI no tiene todas las comunidades (en Challhuahuacho faltan Fuerabamba y Chuicuni): los casos que no se
encuentran se buscan en el mapa por su nombre (capa de lugares de OpenStreetMap), en la página.
"""
import json
import re
import sys

from tremor.db import RAIZ
from tremor.lugares import norm

PREFIJO = re.compile(r"(?i)^(comunidad(es)? (campesinas?|nativas?)|comunidad(es)?|cc\.?|c\.c\.|cn|c\.n\.)\s+(de(l)?\s+)?")


def comunidad_de_caso(nombre: str) -> str | None:
    """'CC Chuicuni - Las Bambas' → 'chuicuni'; 'Comunidad Campesina de Maure – Penal…' → 'maure'. Los casos que no
    nombran una comunidad (frentes, distritos, empresas) → None."""
    if not PREFIJO.match(nombre):
        return None
    resto = PREFIJO.sub("", nombre)
    return norm(re.split(r"\s+[-–]\s+|-", resto)[0]).strip() or None


def main():
    import geopandas as gpd
    import pandas as pd
    sys.stdout.reconfigure(encoding="utf-8")
    w = json.loads((RAIZ / "docs" / "web.json").read_text(encoding="utf-8"))
    zona = set(w["vecinos"]) | {u for v in w["vecinos"].values() for u in v}
    d = gpd.read_file(RAIZ / "datos" / "distritos.geojson")[["ubigeo", "geometry"]]
    d = d[d.ubigeo.isin(zona)]
    raw = json.loads((RAIZ / "datos" / "crudos" / "bdpi" / "capa2.json").read_text(encoding="utf-8"))["mensaje"]
    g = gpd.GeoDataFrame.from_features(raw, crs=4326)
    g = g[g.geometry.notna()]
    g["geometry"] = g.geometry.make_valid()
    centro = g.set_geometry(g.to_crs(32718).geometry.centroid.to_crs(4326))
    j = gpd.sjoin(centro[["geometry"]], d, predicate="within")
    g = g.loc[j.index].assign(ubigeo=j.ubigeo.values)
    casos = pd.DataFrame(w["casos"])
    casos["com"] = casos.nombre.map(comunidad_de_caso)
    casos = casos.dropna(subset=["com"])
    por = {(r.com, str(r.ubigeo)[:2]): r for r in casos.itertuples()}  # mismo nombre y departamento
    filas = []
    for r in g.itertuples():
        c = por.get((norm(r.nombre).strip(), r.ubigeo[:2]))
        filas.append({"n": r.nombre.title(), "u": r.ubigeo, "caso": getattr(c, "nombre", None),
                      "estado": getattr(c, "estado", None), "dialogo": getattr(c, "dialogo", None)})
    s = gpd.GeoDataFrame(filas, geometry=g.geometry.simplify(0.0015).values, crs=4326)
    texto = re.sub(r"(\d+\.\d{4})\d+", r"\1", s.to_json(drop_id=True))
    (RAIZ / "docs" / "comunidades.json").write_text(texto, encoding="utf-8")
    print(f"{len(s)} comunidades en zonas con operación ({len(texto) // 1024} KB); con conflicto abierto en la "
          f"Defensoría: {s.caso.notna().sum()} de {len(casos)} casos que nombran una comunidad")


if __name__ == "__main__":
    main()
