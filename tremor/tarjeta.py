"""Tarjeta en imagen para el aviso de Telegram, al estilo de las alertas de monitoreo: arriba el título, la cifra y el
nivel en letra grande (se lee en el celular); abajo un mapa real (calles, ríos y pueblos de OpenStreetMap, teselas de
la OSMF) que responde tres preguntas: dónde pasa (el distrito pintado), cuál es su unidad (su polígono real) y por qué
vía le llega (su ruta de salida, con el tramo afectado en el color del aviso). El detalle va en el texto del mensaje.

    python -m tremor.tarjeta   # dibuja una de prueba en datos/exportes/tarjeta_prueba.png
"""
import heapq
import io
import json
import math
import re
import textwrap
from functools import lru_cache
from pathlib import Path

import matplotlib
import numpy as np
import requests

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import patheffects  # noqa: E402
from matplotlib.font_manager import FontProperties  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Polygon, Rectangle  # noqa: E402
from matplotlib.path import Path as Trazo  # noqa: E402
from PIL import Image  # noqa: E402  (viene con matplotlib)

from tremor.db import DATOS, RAIZ  # noqa: E402

NIVELES = [("Bajo", 0.10, "#f1d9c6"), ("Medio", 0.25, "#e3a67c"), ("Alto", 0.50, "#c8642f"), ("Crítico", 1.01, "#8a3213")]
TINTA, GRIS, ROJO, RUTA = "#1c2629", "#5b6668", "#c0281f", "#69767a"
FUENTE = {w: FontProperties(fname=Path(__file__).parent / "fuentes" / f"Archivo-{w}.ttf") for w in (400, 600, 800)}  # la de la app
# teselas estándar de OpenStreetMap: uso liviano permitido con User-Agent propio y atribución; se guardan en caché
TESELA = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
LADO = 256
W, H = 1080, 1080  # cuadrada: en el celular se ve grande
BLANCO = [patheffects.withStroke(linewidth=5, foreground="white")]


def nivel(p):
    return next((n, c) for n, tope, c in NIVELES if p < tope)


def _anillos(geo):
    return [geo["coordinates"][0]] if geo["type"] == "Polygon" else [p[0] for p in geo["coordinates"]]


@lru_cache(1)
def _formas():
    g = json.load(open(DATOS / "distritos.geojson", encoding="utf-8"))
    formas, nombres = {}, {}
    for f in g["features"]:
        formas[f["properties"]["ubigeo"]] = _anillos(f["geometry"])
        nombres[f["properties"]["ubigeo"]] = f["properties"]["distrito"].title()
    return formas, nombres


@lru_cache(1)
def _operaciones():
    """[(empresa en minúsculas, unidad, anillos)] de docs/operaciones.json, sin pasivos (no despachan)."""
    g = json.load(open(RAIZ / "docs" / "operaciones.json", encoding="utf-8"))
    return [(f["properties"]["empresa"].lower(), f["properties"]["unidad"], _anillos(f["geometry"]))
            for f in g["features"] if not f["properties"]["unidad"].startswith("Pasivos")]


def red(trozos, une=0.02):
    """Grafo de la red vial: trozos [(código, [(lon, lat), …])] → (puntos, lados {i: [(j, largo, código)]}). La capa
    del MTC viene cortada en miles de trozos: el extremo de cada uno se une al punto más cercano de otro trozo si está a
    menos de `une` grados (así también se empalman las rutas en los cruces)."""
    P = np.array([q[:2] for _, t in trozos for q in t], float)
    dueno = np.repeat(np.arange(len(trozos)), [len(t) for _, t in trozos])
    lados = {i: [] for i in range(len(P))}

    def unir(i, j, codigo):
        d = float(np.hypot(*(P[i] - P[j])))
        lados[i].append((j, d, codigo)); lados[j].append((i, d, codigo))
    i = 0
    for codigo, t in trozos:
        for k in range(i, i + len(t) - 1):
            unir(k, k + 1, codigo)
        for e in (i, i + len(t) - 1):
            d = np.hypot(*(P - P[e]).T)
            d[dueno == dueno[e]] = np.inf
            if d.min() < une:
                unir(e, int(d.argmin()), None)
        i += len(t)
    return P, lados


@lru_cache(1)
def _red():
    """La red vial nacional (docs/rutas.geojson) como grafo."""
    trozos = []
    for f in json.load(open(RAIZ / "docs" / "rutas.geojson", encoding="utf-8"))["features"]:
        g = f["geometry"]
        trozos += [(f["properties"]["r"], t) for t in ([g["coordinates"]] if g["type"] == "LineString" else g["coordinates"])]
    return red(trozos)


def camino(grafo, desde, b, via=None, cerca=0.1, otra=2.5):
    """Puntos de la red desde el más cercano (por la red) de los puntos `desde` hasta b, todos (lon, lat). Cada km fuera
    de la vía `via` cuenta `otra` veces: sigue su ruta (PE-34A) y solo la deja para llegar (el puerto, un empalme).
    None si b o todos los de `desde` quedan a más de `cerca` grados de la red, o si no hay camino."""
    P, lados = grafo
    cerca_de = lambda q: (lambda d: (int(d.argmin()), d.min()))(np.hypot(*(P - q).T))
    ib, db = cerca_de(b)
    fuentes = {i for i, d in map(cerca_de, desde) if d <= cerca}
    if db > cerca or not fuentes:
        return None
    dist, previo, cola = {ib: 0.0}, {}, [(0.0, ib)]  # de b hacia atrás: se detiene en la primera fuente que alcanza
    while cola:
        d, n = heapq.heappop(cola)
        if n in fuentes:
            nodos = [n]
            while nodos[-1] != ib:
                nodos.append(previo[nodos[-1]])
            return [tuple(P[k]) for k in nodos]
        if d > dist[n]:
            continue
        for m, w, codigo in lados[n]:
            w *= 1 if codigo in (via, None) else otra
            if d + w < dist.get(m, np.inf):
                dist[m], previo[m] = d + w, n
                heapq.heappush(cola, (d + w, m))
    return None


def trazar(tramos):
    """Cada tramo de cadena.json como [(línea (lon, lat), ¿por la red?)], siguiendo su vía en rutas.geojson. El primero
    sale de su punto inicial; los demás, del punto de la ruta ya trazada más cercano por la red (la ruta tiene saltos:
    Callalli → Arequipa, y ramales: el plomo deja la vía al puerto). Lo que queda fuera de la red nacional (la mina suele
    estar a decenas de km, por trocha o vía departamental) va en recta y se dibuja punteado."""
    out, hecho = [], []
    for t in (t for t in tramos if t.get("puntos")):  # el puerto no trae puntos
        a, b = [(lon, lat) for lat, lon in t["puntos"]]
        if t.get("rieles"):  # el tren va por sus estaciones, no por la red vial
            out.append((t, [([(lon, lat) for lat, lon in t["rieles"]], False)]))
            continue
        c = camino(_red(), hecho or [a], b, t.get("via"))
        if c and sum(map(math.dist, c, c[1:])) > 3 * math.dist(c[0], b) + 0.2:
            c = None  # la red no los une por cerca (PE-10C cortada en el Marañón): da la vuelta por la costa
        if not c:
            q = min(hecho or [a], key=lambda x: math.dist(x, a))
            partes = ([([q, a], False)] if math.dist(q, a) > 0.01 else []) + [([a, b], False)]
        else:
            partes = [(c, True)] + ([([c[-1], b], False)] if math.dist(c[-1], b) > 0.02 else [])
            if not hecho and math.dist(a, c[0]) > 0.02:
                partes.insert(0, ([a, c[0]], False))
        hecho += [x for linea, _ in partes for x in linea]
        out.append((t, partes))
    return out


def caminos():
    """docs/caminos.json: cada tramo con su camino por la red vial ({cliente: {tramo: [[lon, lat], ...]}}), para que el
    camión de la app siga la carretera. Cada tramo sale de su propio punto. Correr al cambiar cadena.json."""
    out = {}
    for cliente, c in json.load(open(RAIZ / "docs" / "cadena.json", encoding="utf-8")).items():
        for t in c["tramos"]:
            for _, partes in trazar([t]):
                pts = [p for linea, _ in partes for p in linea]
                pts = [p for i, p in enumerate(pts) if i == 0 or math.dist(p, pts[i - 1]) > 0.005 or i == len(pts) - 1]
                out.setdefault(cliente, {})[t["nombre"]] = [[round(x, 4), round(y, 4)] for x, y in pts]
    (RAIZ / "docs" / "caminos.json").write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    return out


def destino(nombre):
    """'Puerto de Matarani, zinc' → 'Matarani'; 'Panamericana Sur al Callao, plomo' → 'Callao'."""
    return nombre.split(",")[0].rsplit(" de ", 1)[-1].rsplit(" al ", 1)[-1].rsplit(" a ", 1)[-1]


def _px(lon, lat, z):
    """Web Mercator: grados → píxel global a zoom z (teselas de 256)."""
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


def _fondo(lon0, lat0, lon1, lat1, w, h, aire=0.74):
    """Mapa real con la caja al `aire` del ancho o del alto: (imagen w×h, a_px). El zoom es fraccionario (se baja una
    imagen de teselas del zoom entero siguiente y se reduce), para que el encuadre no salte al doble."""
    ax, ay = _px(lon0, lat1, 0); bx, by = _px(lon1, lat0, 0)
    zf = min(math.log2(w * aire / max(bx - ax, 1e-9)), math.log2(h * aire / max(by - ay, 1e-9)), 12)
    z = max(3, math.ceil(zf))
    s = 2 ** (zf - z)  # ≤ 1: de píxel del zoom z a píxel de la tarjeta
    cx, cy = (ax + bx) / 2 * 2 ** z, (ay + by) / 2 * 2 ** z
    gw, gh = round(w / s), round(h / s)
    x0, y0 = int(cx - gw / 2), int(cy - gh / 2)
    img = Image.new("RGB", (gw, gh), "#f2efe9")
    try:
        for tx in range(x0 // LADO, (x0 + gw) // LADO + 1):
            for ty in range(y0 // LADO, (y0 + gh) // LADO + 1):
                if 0 <= ty < 2 ** z:
                    img.paste(_tesela(z, tx % 2 ** z, ty), (tx * LADO - x0, ty * LADO - y0))
    except requests.RequestException:
        pass  # sin red: queda el fondo liso y lo del aviso encima
    img = img.resize((w, h), Image.LANCZOS)
    gris = Image.merge("RGB", [img.convert("L")] * 3)  # fondo en gris claro: solo resalta lo del aviso
    a_px = lambda pts: [((X - x0) * s, (Y - y0) * s) for X, Y in (_px(x, y, z) for x, y in pts)]
    return Image.blend(gris, Image.new("RGB", (w, h), "white"), 0.5), a_px


def _rotulo(mapa, texto, xy, ocupado, estorbos, w, h):
    """Rótulo pequeño fuera de las formas, con línea guía: prueba posiciones alrededor de xy y se queda con la que no
    choca con otros rótulos ni con el borde, y pisa menos puntos de las formas (estorbos, en píxeles)."""
    t = mapa.text(0, 0, texto, fontproperties=FUENTE[800], fontsize=19, color=TINTA, ha="center", va="center", zorder=9,
                  path_effects=BLANCO)
    bb = t.get_window_extent(mapa.figure.canvas.get_renderer())
    tw, th = bb.width + 10, bb.height + 8
    mejor = None
    for r in (70, 110, 160):
        for ang in range(0, 360, 30):
            cx, cy = xy[0] + r * math.cos(math.radians(ang)) * 1.3, xy[1] - r * math.sin(math.radians(ang))
            caja = (cx - tw / 2, cy - th / 2, cx + tw / 2, cy + th / 2)
            fuera = caja[0] < 12 or caja[1] < 12 or caja[2] > w - 12 or caja[3] > h - 34
            choca = any(caja[0] < o[2] and o[0] < caja[2] and caja[1] < o[3] and o[1] < caja[3] for o in ocupado)
            pisa = int(((estorbos[:, 0] > caja[0] - 6) & (estorbos[:, 0] < caja[2] + 6) & (estorbos[:, 1] > caja[1] - 6)
                        & (estorbos[:, 1] < caja[3] + 6)).sum()) if len(estorbos) else 0
            nota = 1000 * (fuera + choca) + pisa + r / 50
            if mejor is None or nota < mejor[0]:
                mejor = (nota, cx, cy, caja)
    _, cx, cy, caja = mejor
    t.set_position((cx, cy))
    ocupado.append(caja)
    # la guía va del borde del rótulo al punto
    dx, dy = xy[0] - cx, xy[1] - cy
    k = min(tw / 2 / abs(dx) if dx else np.inf, th / 2 / abs(dy) if dy else np.inf)
    mapa.plot([cx + dx * k, xy[0]], [cy + dy * k, xy[1]], color=TINTA, linewidth=1.6, zorder=8, solid_capstyle="round")


def tarjeta(titulo, cifra, sub, zona, foco, unidad=(), p=None, leyenda="Distrito del aviso", ruta=(), cortes=(),
            empresa=None, punto=None):
    """PNG (bytes) de 1080×1080. cifra: "49%" o "16 nov"; sub: dos líneas junto a la cifra (nivel y periodo, o estado
    y lugar); zona: distritos que encuadran el mapa si no hay foco; foco: distritos del aviso (pintados); unidad: distritos de sus
    unidades; p: probabilidad, para el color (None en una protesta). ruta: sus tramos (docs/cadena.json); cortes: los
    nombres de los tramos afectados, que se pintan en el color del aviso y entran al encuadre con lo que va de la mina a
    ellos; empresa: como figura en operaciones.json, para dibujar el polígono de la unidad en vez del distrito; punto:
    (lat, lon) del corte, si se conoce."""
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

    # qué se dibuja: su ruta, sus unidades (polígono real) y lo que entra al encuadre
    trazos = trazar(ruta)
    cortes = [c for c in cortes if c in {t["nombre"] for t, _ in trazos}]  # un tramo sin puntos (tren) no se dibuja
    hasta = max([k for k, (t, _) in enumerate(trazos) if t["nombre"] in cortes], default=-1)
    distritos = [Trazo(a) for u in unidad for a in formas.get(u, [])]
    unidades = [(n, an) for e, n, an in (_operaciones() if empresa else []) if empresa.lower() in e
                and any(d.contains_point(np.mean(an[0], axis=0)) for d in distritos)]
    unidades.sort(key=lambda u: -np.ptp(np.array(u[1][0]), axis=0).prod())  # la más grande primero: da el nombre y el rótulo
    sin_forma = [u for u in unidad if u in zona and not any(Trazo(a).contains_point(np.mean(an[0], axis=0))
                                                           for _, an in unidades for a in formas.get(u, []))]
    puntos = [(x, y) for u in (foco or zona) for a in formas.get(u, []) for x, y in a]  # el encuadre: lo del aviso, no sus vecinos
    puntos += [q for _, an in unidades for a in an for q in a]
    puntos += [q for _, partes in trazos[:hasta + 1] for linea, _ in partes for q in linea]
    puntos += [(punto[1], punto[0])] if punto else []

    mx, mw = 0, W
    my = 88 + 52 * len(lineas) + 58 + 74  # el mapa empieza donde termina la cabecera
    items = ([("caja", leyenda + (f": {', '.join(dict.fromkeys(nombres[u] for u in foco if u in nombres))}" if 0 < len(foco) <= 2 else ""))]
             if foco else [])
    if cortes:
        items.append(("corte", leyenda if not foco else "Su ruta por la zona de riesgo" if p is not None
                      else "Tramo afectado de su ruta" if len(cortes) == 1 else "Tramos afectados de su ruta"))
    if len(cortes) < len(trazos):
        items.append(("ruta", "Su ruta de salida"))
    if unidades or sin_forma:
        nom = re.sub(r"\s+\d+(,\s*\d+)*(\s+y\s+\d+)?$", "", unidades[0][0].split(" - ")[0]) if unidades else nombres.get(sin_forma[0], "")  # sin "1, 2 y 3"
        items.append(("unidad", f"Su unidad: {nom}"))
    if punto:
        items.append(("punto", "Punto del corte"))
    filas = 1 if len(items) <= 2 else (len(items) + 1) // 2
    mh = H - my - (60 + 48 * filas)
    mapa = fig.add_axes([mx / W, 1 - (my + mh) / H, mw / W, mh / H]); mapa.set_axis_off()
    if puntos:
        lon = [x for x, _ in puntos]; lat = [y for _, y in puntos]
        img, a_px = _fondo(min(lon), min(lat), max(lon), max(lat), mw, mh)
        mapa.imshow(img, extent=(0, mw, mh, 0), zorder=0)
        estorbos = []
        for u in foco:
            for anillo in formas.get(u, []):
                xy = a_px(anillo); estorbos += xy
                mapa.add_patch(Polygon(xy, closed=True, facecolor=color, alpha=0.28, edgecolor="none", zorder=2))
                mapa.add_patch(Polygon(xy, closed=True, facecolor="none", edgecolor=color, linewidth=2.4, zorder=3))
        for u in sin_forma:  # unidad sin polígono en operaciones.json: su distrito, punteado
            for anillo in formas.get(u, []):
                mapa.add_patch(Polygon(a_px(anillo), closed=True, facecolor="none", edgecolor=TINTA, linewidth=2.4,
                                       linestyle=(0, (5, 3)), zorder=6))
        # la ruta: primero los tramos sanos en gris, encima los afectados en el color del aviso; todos con borde blanco
        for afectado in (False, True):
            for t, partes in trazos:
                if (t["nombre"] in cortes) != afectado:
                    continue
                for linea, por_red in partes:
                    xy = np.array(a_px(linea)); estorbos += list(xy)
                    mapa.plot(*xy.T, color=color if afectado else RUTA, linewidth=7 if afectado else 4.5,
                              linestyle="-" if por_red else (0, (1.2, 1.4)), solid_capstyle="round", solid_joinstyle="round",
                              dash_capstyle="round", zorder=4 + afectado,
                              path_effects=[patheffects.withStroke(linewidth=(11 if afectado else 8), foreground="white")])
        # sus unidades: el polígono real, en tinta; si queda muy chico para verse, además un rombo
        centros = []
        for _, an in unidades:
            xy = [np.array(a_px(anillo)) for anillo in an]
            for x in xy:
                estorbos += list(x)
                mapa.add_patch(Polygon(x, closed=True, facecolor=TINTA, alpha=0.75, edgecolor="white", linewidth=1.2, zorder=6))
            todo = np.vstack(xy)
            centros.append((todo.min(0) + todo.max(0)) / 2)
            if np.ptp(todo, axis=0).max() < 16:
                mapa.plot(*centros[-1], marker="D", markersize=13, color=TINTA, markeredgecolor="white", markeredgewidth=2, zorder=7)
        ocupado = [(mw - 330, mh - 34, mw, mh)]  # la atribución, abajo a la derecha
        estorbos = np.array(estorbos, float).reshape(-1, 2)
        if centros and 0 < centros[0][0] < mw and 0 < centros[0][1] < mh:
            _rotulo(mapa, "Su unidad", centros[0], ocupado, estorbos, mw, mh)
        # destinos de la carga (los tramos que dicen qué llevan: "Puerto de Matarani, zinc") que caen en el mapa
        for t, partes in trazos:
            x, y = a_px([partes[-1][0][-1]])[0]
            if "," in t["nombre"] and 0 < x < mw and 0 < y < mh:
                mapa.plot(x, y, marker="o", markersize=12, color="white", markeredgecolor=TINTA, markeredgewidth=3, zorder=7)
                _rotulo(mapa, destino(t["nombre"]), (x, y), ocupado, estorbos, mw, mh)
        if punto:
            x, y = a_px([(punto[1], punto[0])])[0]
            mapa.plot(x, y, marker="X", markersize=20, color=color, markeredgecolor="white", markeredgewidth=2.5, zorder=8)
        mapa.set_xlim(0, mw); mapa.set_ylim(mh, 0)
        mapa.text(mw - 8, mh - 8, "© colaboradores de OpenStreetMap", ha="right", va="bottom", fontsize=11, color=GRIS, zorder=9,
                  path_effects=[patheffects.withStroke(linewidth=3, foreground="white")])

    # abajo: leyenda (los nombres van aquí, no sobre el mapa); en dos columnas si son más de dos trazos
    r = fig.canvas.get_renderer()
    for k, (tipo, texto) in enumerate(items):
        col, fila = (k % 2, k // 2) if filas > 1 else (k, 0)
        x, yb = (44 + 490 * col) / W, 1 - (my + mh + 44 + 48 * fila) / H
        if tipo == "caja":
            fig.patches.append(Rectangle((x, yb - 0.013), 0.034, 0.026, transform=fig.transFigure, facecolor=color, alpha=0.45,
                                         edgecolor=color, linewidth=2))
        elif tipo == "unidad":
            fig.patches.append(Rectangle((x + 0.006, yb - 0.011), 0.022, 0.022, transform=fig.transFigure, facecolor=TINTA,
                                         alpha=0.85))
        elif tipo == "punto":
            fig.lines.append(Line2D([x + 0.017], [yb], transform=fig.transFigure, marker="X", markersize=18, color=color,
                                    markeredgecolor="white"))
        else:
            fig.lines.append(Line2D([x, x + 0.034], [yb, yb], transform=fig.transFigure, color=color if tipo == "corte" else RUTA,
                                    linewidth=7 if tipo == "corte" else 4.5, solid_capstyle="round"))
        t = fig.text(x + 0.046, yb, texto, fontproperties=FUENTE[600], fontsize=20, color=TINTA, va="center")
        while t.get_window_extent(r).x1 > (510 if col == 0 and k + 1 < len(items) else W - 24) and len(texto) > 8:  # que no pise la otra columna
            texto = texto[:-2].rstrip(" ,…") + "…"; t.set_text(texto)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor="white")
    plt.close(fig)
    return buf.getvalue()


if __name__ == "__main__":
    c = json.load(open(RAIZ / "docs" / "cadena.json", encoding="utf-8"))["Bateas"]["tramos"]
    png = tarjeta("Sube el riesgo de conflicto cerca de su unidad Acumulación Cailloma", "49%",
                  ["Nivel alto", "Octubre a diciembre de 2026"],
                  ["080803", "080801", "080804", "040505"], {"080803"}, ["040505"], p=0.49, ruta=c, empresa="minera bateas")
    (DATOS / "exportes" / "tarjeta_prueba.png").write_bytes(png)
