"""Tarjeta en imagen para el aviso de Telegram, al estilo de los boletines de monitoreo (mapa a la izquierda, ficha a
la derecha): la zona de la unidad con el distrito del aviso pintado, un Perú chico para ubicarse, la cifra, qué puede
pasar, qué hacer y, si es riesgo, la escala de nivel. Sin red ni navegador: matplotlib y datos/distritos.geojson.

    python -m tremor.tarjeta   # dibuja una de prueba en datos/exportes/tarjeta_prueba.png
"""
import io
import json
import textwrap
from functools import lru_cache

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import patheffects  # noqa: E402
from matplotlib.collections import PolyCollection  # noqa: E402
from matplotlib.patches import Polygon, Rectangle  # noqa: E402

from tremor.db import DATOS  # noqa: E402

NIVELES = [("Bajo", 0.10, "#f1d9c6"), ("Medio", 0.25, "#e3a67c"), ("Alto", 0.50, "#c8642f"), ("Crítico", 1.01, "#8a3213")]
TINTA, GRIS, ROJO = "#1c2629", "#5b6668", "#c0281f"


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


def _centro(anillo):
    return sum(x for x, _ in anillo) / len(anillo), sum(y for _, y in anillo) / len(anillo)


def tarjeta(titulo, cifra, sub, puede, hacer, zona, foco, unidad=(), p=None, leyenda="Distrito del aviso"):
    """PNG (bytes) de 1200×675. cifra: "49%" o "16 nov"; sub: dos líneas junto a la cifra; zona: distritos del mapa;
    foco: distritos del aviso (los pintados); unidad: distritos de la operación; p: probabilidad,
    para el color y la escala de nivel (None en una protesta)."""
    formas, nombres = _formas()
    color = nivel(p)[1] if p is not None else ROJO
    fig = plt.figure(figsize=(12, 6.75), dpi=100, facecolor="white")
    mapa = fig.add_axes([0.02, 0.12, 0.50, 0.84]); mapa.set_axis_off(); mapa.set_aspect("equal")
    xs, ys = [], []
    for u in zona:
        for anillo in formas.get(u, []):
            pinta = u in foco
            mapa.add_patch(Polygon(anillo, closed=True, facecolor=color if pinta else "#eef0ee", alpha=0.9 if pinta else 1,
                                   edgecolor=TINTA if u in unidad else "#9aa5a3", linewidth=2.4 if u in unidad else 0.6,
                                   zorder=3 if u in unidad else 2))
            xs += [x for x, _ in anillo]; ys += [y for _, y in anillo]
        if u in formas and (u in unidad or (u in foco and len(foco) == 1) or (len(foco) <= 1 and len(zona) <= 12)):
            x, y = _centro(formas[u][0])
            es = u in foco
            mapa.text(x, y, "Su unidad" if u in unidad and not es else nombres[u], ha="center", va="center", zorder=6,
                      fontsize=10.5 if es or u in unidad else 7.5, fontweight="bold" if es or u in unidad else "normal",
                      color="white" if es and (p is None or p >= 0.25) else TINTA if u in unidad else GRIS,
                      path_effects=None if es else [patheffects.withStroke(linewidth=3, foreground="white")])
    if xs:
        mx, my = (max(xs) - min(xs)) * 0.05, (max(ys) - min(ys)) * 0.05
        mapa.set_xlim(min(xs) - mx, max(xs) + mx); mapa.set_ylim(min(ys) - my, max(ys) + my)
        # fondo: el resto de distritos, para que la zona no flote en blanco
        mapa.add_collection(PolyCollection([a for u, an in formas.items() if u not in zona for a in an],
                                           facecolor="#f4f5f4", edgecolor="white", linewidth=0.5, zorder=1))
        # Perú chico, con un recuadro donde está la zona
        peru = fig.add_axes([0.40, 0.70, 0.12, 0.26]); peru.set_axis_off(); peru.set_aspect("equal")
        peru.add_collection(PolyCollection([a for an in formas.values() for a in an], facecolor="#dfe3e1", edgecolor="none"))
        peru.set_xlim(-81.4, -68.6); peru.set_ylim(-18.4, -0.03)
        peru.add_patch(Rectangle((min(xs) - 0.3, min(ys) - 0.3), max(xs) - min(xs) + 0.6, max(ys) - min(ys) + 0.6,
                                 facecolor="none", edgecolor=color, linewidth=1.8))
    # pie del mapa
    fig.patches.append(Rectangle((0.03, 0.075), 0.016, 0.024, transform=fig.transFigure, facecolor=color, edgecolor="none"))
    fig.text(0.05, 0.08, leyenda, fontsize=9, color=GRIS)
    fig.patches.append(Rectangle((0.17, 0.075), 0.016, 0.024, transform=fig.transFigure, facecolor="none", edgecolor=TINTA, linewidth=2))
    fig.text(0.19, 0.08, "Distritos de su unidad", fontsize=9, color=GRIS)
    if p is not None:
        x0 = 0.03
        for n, tope, c in NIVELES:
            fig.patches.append(Rectangle((x0, 0.025), 0.11, 0.03, transform=fig.transFigure, facecolor=c, edgecolor="white"))
            fig.text(x0 + 0.055, 0.04, n, ha="center", va="center", fontsize=8.5, color="white" if tope > 0.25 else TINTA, fontweight="bold")
            x0 += 0.11
        topes = [0] + [t for _, t, _ in NIVELES]
        i = next(k for k in range(4) if p < topes[k + 1])
        fig.text(0.03 + 0.11 * (i + (p - topes[i]) / (topes[i + 1] - topes[i])), 0.0, "▲", ha="center", fontsize=9, color=TINTA)
    # ficha a la derecha
    fig.patches.append(Rectangle((0.54, 0.03), 0.44, 0.94, transform=fig.transFigure, facecolor="#f6f4f1", edgecolor="none"))
    y = 0.92
    fig.text(0.56, y, "TREMOR  ·  Riesgo social en operaciones", fontsize=9.5, color=GRIS, fontweight="bold"); y -= 0.075
    for linea in textwrap.wrap(titulo, 34)[:4]:
        fig.text(0.56, y, linea, fontsize=17, color=TINTA, fontweight="bold"); y -= 0.06
    y -= 0.02
    fig.text(0.56, y - 0.05, cifra, fontsize=32, color=color, fontweight="bold")
    for k, linea in enumerate(sub[:2]):
        fig.text(0.735, y - 0.012 - 0.038 * k, linea, fontsize=12 if k == 0 else 10, color=TINTA if k == 0 else GRIS,
                 fontweight="bold" if k == 0 else "normal")
    y -= 0.13
    for cab, items in (("¿Qué puede pasar?", puede), ("Qué hacer", hacer)):
        fig.text(0.56, y, cab, fontsize=11.5, color=TINTA, fontweight="bold"); y -= 0.045
        for it in items:
            for k, linea in enumerate(textwrap.wrap(it, 62)):
                fig.text(0.565, y, ("•  " if k == 0 else "    ") + linea, fontsize=9.5, color=TINTA); y -= 0.036
        y -= 0.02
    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor="white")
    plt.close(fig)
    return buf.getvalue()


if __name__ == "__main__":
    png = tarjeta("Sube el riesgo de conflicto cerca de su unidad Acumulación Cailloma", "49%",
                  ["Nivel alto", "Octubre a diciembre de 2026"],
                  ["Paro, bloqueo o toma contra una operación minera en Coporaque (Espinar, Cusco) o sus vecinos.",
                   "11 medidas de fuerza en el último año y 3 conflictos activos ante la Defensoría."],
                  ["Reforzar el seguimiento de la zona y el diálogo con las comunidades vecinas."],
                  ["080803", "080801", "080804", "040505"], {"080803"}, ["040505"], p=0.49)
    (DATOS / "exportes" / "tarjeta_prueba.png").write_bytes(png)
