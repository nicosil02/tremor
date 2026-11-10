"""Tarjeta en imagen para el aviso de Telegram, al estilo de las alertas de monitoreo: arriba el título, la cifra y el
nivel en letra grande (se lee en el celular); abajo un mapa real (calles, ríos y pueblos de OpenStreetMap, teselas de
la OSMF) con el distrito del aviso pintado y su unidad marcada. El detalle va en el texto del mensaje, no en la imagen.

    python -m tremor.tarjeta   # dibuja una de prueba en datos/exportes/tarjeta_prueba.png
"""
import io
import json
import math
import textwrap
from functools import lru_cache
from pathlib import Path

import matplotlib
import requests

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import patheffects  # noqa: E402
from matplotlib.font_manager import FontProperties  # noqa: E402
from matplotlib.patches import Polygon, Rectangle  # noqa: E402
from PIL import Image  # noqa: E402  (viene con matplotlib)

from tremor.db import DATOS  # noqa: E402

NIVELES = [("Bajo", 0.10, "#f1d9c6"), ("Medio", 0.25, "#e3a67c"), ("Alto", 0.50, "#c8642f"), ("Crítico", 1.01, "#8a3213")]
TINTA, GRIS, ROJO = "#1c2629", "#5b6668", "#c0281f"
FUENTE = {w: FontProperties(fname=Path(__file__).parent / "fuentes" / f"Archivo-{w}.ttf") for w in (400, 600, 800)}  # la de la app
# teselas estándar de OpenStreetMap: uso liviano permitido con User-Agent propio y atribución; se guardan en caché
TESELA = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
LADO = 256
W, H = 1080, 1080  # cuadrada: en el celular se ve grande


def nivel(p):
    return next((n, c) for n, tope, c in NIVELES if p < tope)


@lru_cache(1)
def _formas():
    g = json.load(open(DATOS / "distritos.geojson", encoding="utf-8"))
    formas, nombres = {}, {}
    for f in g["features"]:
        geo, pr = f["geometry"], f["properties"]
        formas[pr["ubigeo"]] = [geo["coordinates"][0]] if geo["type"] == "Polygon" else [p[0] for p in geo["coordinates"]]
        nombres[pr["ubigeo"]] = pr["distrito"].title()
    return formas, nombres


def _px(lon, lat, z):
    """Web Mercator: grados → píxel global a zoom z (teselas de 512)."""
    n = LADO * 2 ** z
    s = math.sin(math.radians(lat))
    return (lon + 180) / 360 * n, (0.5 - math.log((1 + s) / (1 - s)) / (4 * math.pi)) * n


@lru_cache(512)
def _tesela(z, x, y):
    cache = DATOS / "cache" / "teselas" / f"{z}_{x}_{y}.png"
    if cache.exists():
        return Image.open(cache).convert("RGB")
    r = requests.get(TESELA.format(z=z, x=x, y=y), timeout=30,
                     headers={"User-Agent": "Tremor/1.0 (alertas de conflicto social; github.com/nicosil02/tremor)"})
    r.raise_for_status()
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_bytes(r.content)
    return Image.open(io.BytesIO(r.content)).convert("RGB")


def _fondo(lon0, lat0, lon1, lat1, w, h):
    """Mapa real que contiene la caja: (imagen w×h, z, x0, y0 en píxel global)."""
    for z in range(12, 4, -1):  # el zoom más cercano en que la caja entra con margen
        ax, ay = _px(lon0, lat1, z); bx, by = _px(lon1, lat0, z)
        if bx - ax <= w * 0.82 and by - ay <= h * 0.82:
            break
    cx, cy = (ax + bx) / 2, (ay + by) / 2
    x0, y0 = int(cx - w / 2), int(cy - h / 2)
    img = Image.new("RGB", (w, h), "#f2efe9")
    try:
        for tx in range(x0 // LADO, (x0 + w) // LADO + 1):
            for ty in range(y0 // LADO, (y0 + h) // LADO + 1):
                if 0 <= ty < 2 ** z:
                    img.paste(_tesela(z, tx % 2 ** z, ty), (tx * LADO - x0, ty * LADO - y0))
    except requests.RequestException:
        pass  # sin red: queda el fondo liso y los distritos encima
    gris = Image.merge("RGB", [img.convert("L")] * 3)  # fondo en gris claro: solo resalta lo del aviso
    return Image.blend(gris, Image.new("RGB", (w, h), "white"), 0.45), z, x0, y0


def tarjeta(titulo, cifra, sub, zona, foco, unidad=(), p=None, leyenda="Distrito del aviso"):
    """PNG (bytes) de 1080×1080. cifra: "49%" o "16 nov"; sub: dos líneas junto a la cifra (nivel y periodo, o estado
    y lugar); zona: distritos que encuadran el mapa; foco: distritos del aviso (pintados); unidad: los de la operación;
    p: probabilidad, para el color y la escala (None en una protesta)."""
    formas, nombres = _formas()
    color = nivel(p)[1] if p is not None else ROJO
    fig = plt.figure(figsize=(W / 100, H / 100), dpi=100, facecolor="white")

    # arriba: marca, título, cifra y nivel
    fig.text(44 / W, 1 - 50 / H, "TREMOR · ALERTA", fontproperties=FUENTE[800], fontsize=20, color=GRIS)
    lineas = textwrap.wrap(textwrap.shorten(titulo, 96, placeholder="…"), 32)[:3]
    for k, linea in enumerate(lineas):
        fig.text(44 / W, 1 - (88 + 52 * k) / H, linea, fontproperties=FUENTE[800], fontsize=36, color=TINTA, va="top")
    yc = 1 - (88 + 52 * len(lineas) + 58) / H
    t = fig.text(44 / W, yc, cifra, fontproperties=FUENTE[800], fontsize=54, color=color, va="center")
    xs = t.get_window_extent(fig.canvas.get_renderer()).x1 + 28  # el ancho real de "49%" o "16 nov"
    fig.text(xs / W, yc + 0.018, sub[0], fontproperties=FUENTE[800], fontsize=28, color=TINTA, va="center")
    if len(sub) > 1:
        fig.text(xs / W, yc - 0.024, sub[1], fontproperties=FUENTE[400], fontsize=24, color=GRIS, va="center")

    # mapa real
    mx, mw = 0, W
    my = 88 + 52 * len(lineas) + 58 + 74  # el mapa empieza donde termina la cabecera
    mh = H - my - 96
    mapa = fig.add_axes([mx / W, 1 - (my + mh) / H, mw / W, mh / H]); mapa.set_axis_off()
    puntos = [(x, y) for u in zona for a in formas.get(u, []) for x, y in a]
    if puntos:
        lon = [x for x, _ in puntos]; lat = [y for _, y in puntos]
        img, z, x0, y0 = _fondo(min(lon), min(lat), max(lon), max(lat), mw, mh)
        mapa.imshow(img, extent=(0, mw, mh, 0), zorder=0)
        a_px = lambda anillo: [(px - x0, py - y0) for px, py in (_px(x, y, z) for x, y in anillo)]
        for u in zona:
            for anillo in formas.get(u, []):
                if u in foco:
                    mapa.add_patch(Polygon(a_px(anillo), closed=True, facecolor=color, alpha=0.35, edgecolor="none", zorder=2))
                    mapa.add_patch(Polygon(a_px(anillo), closed=True, facecolor="none", edgecolor=color, linewidth=3, zorder=3))
                if u in unidad:
                    mapa.add_patch(Polygon(a_px(anillo), closed=True, facecolor="none", edgecolor=TINTA, linewidth=2.6,
                                           linestyle=(0, (5, 3)), zorder=4))
        mapa.set_xlim(0, mw); mapa.set_ylim(mh, 0)
        mapa.text(mw - 8, mh - 8, "© colaboradores de OpenStreetMap", ha="right", va="bottom", fontsize=11, color=GRIS, zorder=7,
                  path_effects=[patheffects.withStroke(linewidth=3, foreground="white")])

    # abajo: leyenda con los nombres (en el mapa se montaban sobre los distritos); el nivel ya está arriba
    yb, x = 1 - (my + mh + 48) / H, 44 / W
    r = fig.canvas.get_renderer()
    nom = lambda us: ", ".join(dict.fromkeys(nombres[u] for u in us if u in nombres))
    dibujada = [u for u in unidad if u in zona and u not in foco]
    items = [("caja", leyenda + (f": {nom(foco)}" if 0 < len(foco) <= 2 else ""))]
    if dibujada:
        items.append(("raya", f"Su unidad: {nom(dibujada[:2])}"))
    for tipo, texto in items:
        if tipo == "caja":
            fig.patches.append(Rectangle((x, yb - 0.014), 0.032, 0.028, transform=fig.transFigure, facecolor=color, alpha=0.6,
                                         edgecolor=color, linewidth=2))
        else:
            fig.lines.append(plt.Line2D([x, x + 0.032], [yb, yb], transform=fig.transFigure, color=TINTA, linewidth=3,
                                        linestyle=(0, (5, 3))))
        t = fig.text(x + 0.044, yb, textwrap.shorten(texto, 40, placeholder="…"), fontproperties=FUENTE[600], fontsize=22,
                     color=TINTA, va="center")
        x = t.get_window_extent(r).x1 / W + 0.04
    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor="white")
    plt.close(fig)
    return buf.getvalue()


if __name__ == "__main__":
    png = tarjeta("Sube el riesgo de conflicto cerca de su unidad Acumulación Cailloma", "49%",
                  ["Nivel alto", "Octubre a diciembre de 2026"],
                  ["080803", "080801", "080804", "040505"], {"080803"}, ["040505"], p=0.49)
    (DATOS / "exportes" / "tarjeta_prueba.png").write_bytes(png)
