"""Concesiones mineras de cada cliente y las comunidades cuyo territorio pisan.

Las concesiones salen del catastro que publica GEOPERÚ (geoservidor del MINAM, capa de INGEMMET), por titular. Se
cruzan con el territorio de las comunidades campesinas y nativas (docs/comunidades.json, de la BDPI): una comunidad
dentro de una concesión es con quien la empresa tendrá que tratar, tenga o no un conflicto abierto.

    python -m tremor.concesiones      # escribe docs/concesiones.json; correr al cambiar los clientes
"""
import json
import re
import sys
import time

import requests

from tremor.db import RAIZ

CAPA = "https://geoservidorperu.minam.gob.pe/arcgis/rest/services/Servicio_Oportunidades_Inversion/MapServer/25/query"
# El titular como lo escribe el catastro. "BUENAVENTURA" a secas trae a una persona de ese apellido y a otra empresa.
TITULAR = {"Buenaventura": "MINAS BUENAVENTURA"}


def concesiones(titular):
    """Polígonos (GeoJSON) de las concesiones cuyo titular contiene el texto."""
    fs = []
    while True:
        d = requests.get(CAPA, params={"where": f"TIT_CONCES LIKE '%{titular}%'", "outFields": "CONCESION,TIT_CONCES,D_ESTADO",
                                       "returnGeometry": "true", "outSR": 4326, "maxAllowableOffset": 0.0005, "f": "geojson",
                                       "resultOffset": len(fs), "resultRecordCount": 1000},
                         headers={"User-Agent": "tremor (investigacion PUCP)"}, timeout=180).json()
        lote = [f for f in d.get("features", []) if f.get("geometry")]
        fs += lote
        if len(d.get("features", [])) < 1000:
            return fs
        time.sleep(0.5)


def pisa(area, comunidades, minimo=0.01):
    """Comunidades con al menos 1% de su territorio dentro del área: [{n, u, caso, pct}], de más a menos."""
    from shapely.geometry import shape
    out = {}  # por nombre y distrito: la BDPI repite comunidades con el territorio en varias partes; queda la mayor
    for f in comunidades:
        g = shape(f["geometry"]).buffer(0)
        if g.area and g.intersects(area) and (p := g.intersection(area).area / g.area) >= minimo:
            k = (f["properties"]["n"], f["properties"]["u"])
            if p > out.get(k, {"pct": 0})["pct"]:
                out[k] = {"n": k[0], "u": k[1], "caso": f["properties"].get("caso"), "pct": round(p, 2)}
    return sorted(out.values(), key=lambda x: -x["pct"])


def main():
    from shapely.geometry import mapping, shape
    from shapely.ops import unary_union
    sys.stdout.reconfigure(encoding="utf-8")
    com = json.loads((RAIZ / "docs" / "comunidades.json").read_text(encoding="utf-8"))["features"]
    out = {}
    for cliente, c in json.loads((RAIZ / "docs" / "cadena.json").read_text(encoding="utf-8")).items():
        fs = concesiones(TITULAR.get(cliente, c["empresa"].upper()))
        if not fs:
            continue
        area = unary_union([shape(f["geometry"]).buffer(0) for f in fs])  # unidas: un solo contorno por bloque
        out[cliente] = {"n": len(fs), "titulares": sorted({f["properties"]["TIT_CONCES"] for f in fs}),
                        "pisa": pisa(area, com), "geo": mapping(area.simplify(0.0005))}
        print(f"{cliente}: {len(fs)} concesiones, {len(out[cliente]['pisa'])} comunidades dentro")
    texto = re.sub(r"(\d+\.\d{4})\d+", r"\1", json.dumps(out, ensure_ascii=False, separators=(",", ":")))
    (RAIZ / "docs" / "concesiones.json").write_text(texto, encoding="utf-8")
    print(f"docs/concesiones.json ({len(texto) // 1024} KB)")


if __name__ == "__main__":
    main()
