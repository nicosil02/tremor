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
    return img, z, x0, y0


def tarjeta(titulo, cifra, sub, zona, foco, unidad=(), p=None, leyenda="Distrito del aviso"):
    """PNG (bytes) de 1080×1080. cifra: "49%" o "16 nov"; sub: dos líneas junto a la cifra (nivel y periodo, o estado
    y lugar); zona: distritos que encuadran el mapa; foco: distritos del aviso (pintados); unidad: los de la operación;
    p: probabilidad, para el color y la escala (None en una protesta)."""
    formas, nombres = _formas()
    color = nivel(p)[1] if p is not None else ROJO
    fig = plt.figure(figsize=(W / 100, H / 100), dpi=100, facecolor="white")

    # arriba: marca, título, cifra y nivel
    fig.text(48 / W, 1 - 52 / H, "TREMOR  ·  ALERTA DE CONFLICTO SOCIAL", fontproperties=FUENTE[600], fontsize=15, color=GRIS)
    lineas = textwrap.wrap(textwrap.shorten(titulo, 126, placeholder="…"), 42)[:3]
    for k, linea in enumerate(lineas):
        fig.text(48 / W, 1 - (100 + 40 * k) / H, linea, fontproperties=FUENTE[800], fontsize=27, color=TINTA, va="top")
    yc = 1 - (100 + 40 * len(lineas) + 48) / H
    fig.text(48 / W, yc, cifra, fontproperties=FUENTE[800], fontsize=40, color=color, va="center")
    xs = 48 + 31 * len(cifra) + 36
    fig.text(xs / W, yc + 0.014, sub[0], fontproperties=FUENTE[800], fontsize=21, color=TINTA, va="center")
    if len(sub) > 1:
        fig.text(xs / W, yc - 0.022, sub[1], fontproperties=FUENTE[400], fontsize=17, color=GRIS, va="center")

    # mapa real
    mx, mw = 0, W
    my = 100 + 40 * len(lineas) + 48 + 62  # el mapa empieza donde termina la cabecera
    mh = H - my - 100
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
        halo = [patheffects.withStroke(linewidth=5, foreground="white")]
        rotulos = ([u for u in foco if u in formas] if len(foco) <= 2 else []) + [u for u in unidad if u in formas and u not in foco][:3]
        for u in rotulos:
            ps = [q for a in formas[u] for q in a_px(a)]
            x, y = sum(q[0] for q in ps) / len(ps), sum(q[1] for q in ps) / len(ps)
            texto = nombres[u] if u in foco else f"Su unidad\n({nombres[u]})"
            mapa.text(x, y, texto, ha="center", va="center", zorder=6, fontproperties=FUENTE[800] if u in foco else FUENTE[600],
                      fontsize=19 if u in foco else 15, color=TINTA, path_effects=halo, linespacing=1.1)
        mapa.set_xlim(0, mw); mapa.set_ylim(mh, 0)
        mapa.text(mw - 8, mh - 8, "© colaboradores de OpenStreetMap", ha="right", va="bottom", fontsize=9, color=GRIS, zorder=7,
                  path_effects=[patheffects.withStroke(linewidth=3, foreground="white")])

    # abajo: leyenda y escala de nivel
    yb = 1 - (my + mh + 50) / H
    fig.patches.append(Rectangle((48 / W, yb - 0.011), 0.026, 0.022, transform=fig.transFigure, facecolor=color, alpha=0.6,
                                 edgecolor=color, linewidth=2))
    fig.text(84 / W, yb, leyenda, fontproperties=FUENTE[400], fontsize=16, color=TINTA, va="center")
    if unidad:
        fig.lines.append(plt.Line2D([330 / W, 358 / W], [yb, yb], transform=fig.transFigure, color=TINTA, linewidth=2.6,
                                    linestyle=(0, (5, 3))))
        fig.text(368 / W, yb, "Su unidad", fontproperties=FUENTE[400], fontsize=16, color=TINTA, va="center")
    if p is not None:
        x0, ancho = 560 / W, 110 / W
        for n, tope, c in NIVELES:
            actual = n == nivel(p)[0]
            fig.patches.append(Rectangle((x0, yb - 0.017), ancho, 0.034, transform=fig.transFigure, facecolor=c,
                                         edgecolor=TINTA if actual else "white", linewidth=3 if actual else 1))
            fig.text(x0 + ancho / 2, yb, n, ha="center", va="center", fontproperties=FUENTE[800 if actual else 400], fontsize=15,
                     color="white" if tope > 0.25 else TINTA)
            x0 += ancho
    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor="white")
    plt.close(fig)
    return buf.getvalue()


if __name__ == "__main__":
    png = tarjeta("Sube el riesgo de conflicto cerca de su unidad Acumulación Cailloma", "49%",
                  ["Nivel alto", "Octubre a diciembre de 2026"],
                  ["080803", "080801", "080804", "040505"], {"080803"}, ["040505"], p=0.49)
    (DATOS / "exportes" / "tarjeta_prueba.png").write_bytes(png)
