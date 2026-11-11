"""Datos reales para el video (src/datos.json): contorno del Perú, operaciones y la ruta de Bateas, ya proyectados
a un lienzo de 1000 de ancho. Correr desde la raíz del repo: python video/datos.py"""
import json, math
from shapely.geometry import shape
from shapely.ops import unary_union

g = json.load(open("datos/distritos.geojson", encoding="utf-8"))["features"]
peru = unary_union([shape(f["geometry"]).buffer(0.01) for f in g]).simplify(0.06)
peru = max(getattr(peru, "geoms", [peru]), key=lambda p: p.area)
x0, y0, x1, y1 = peru.bounds
K = math.cos(math.radians((y0 + y1) / 2))
esc = 1000 / ((x1 - x0) * K)
xy = lambda lon, lat: [round((lon - x0) * K * esc, 1), round((y1 - lat) * esc, 1)]

ops = json.load(open("docs/operaciones.json", encoding="utf-8"))["features"]
puntos = sorted({tuple(xy(*shape(f["geometry"]).centroid.coords[0])) for f in ops if f["properties"]["tipo"] == "mineria"})
caminos = json.load(open("docs/caminos.json", encoding="utf-8"))["Bateas"]
out = {"alto": round((y1 - y0) * esc), "peru": [xy(*p) for p in peru.exterior.coords],
       "operaciones": puntos[::2],
       "ruta": {k: [xy(*p) for p in v] for k, v in caminos.items()}}
json.dump(out, open("video/src/datos.json", "w", encoding="utf-8"), ensure_ascii=False)
print(len(out["peru"]), len(out["operaciones"]), {k: len(v) for k, v in out["ruta"].items()}, out["alto"])
