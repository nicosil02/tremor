"""Agrupar notas en eventos (FR-014/015) y medir la señal contra la Defensoría y la EGPP (FR-016/017)."""
import re
from collections import Counter
from datetime import date, timedelta
from statistics import median

from tremor.egpp import EXTRACTIVO
from tremor.lugares import catalogo, norm, resolver
from tremor.prensa.codificar import VERSION

FAMILIA = {"Paro": "para", "Huelga": "para", "Bloqueo de vías": "para", "Huelga de hambre": "hambre",
           "Marcha": "calle", "Plantón": "calle", "Mitin": "calle", "Vigilia": "calle", "Pasacalle / caravana": "calle",
           "Cacerolazo": "calle", "Protesta simbolica": "calle", "Toma de local": "toma", "Invasión": "toma"}
LARGAS = {"Paro", "Huelga", "Huelga de hambre"}


def _f(s):
    return date.fromisoformat(s[:10]) if s else None


def _lugar_compatible(a, b):
    if not a or not b:
        return False
    n = min(len(a), len(b), 4)
    return a[:n] == b[:n]


def mismo_evento(x, y) -> bool:
    if not _lugar_compatible(x["ubigeo"], y["ubigeo"]):
        return False
    fx, fy = FAMILIA.get(x["accion"], x["accion"]), FAMILIA.get(y["accion"], y["accion"])
    if fx and fy and fx != fy:
        return False
    if x["sector"] and y["sector"] and x["sector"] != y["sector"]:
        return False
    margen = 3 if {x["accion"], y["accion"]} & LARGAS else 1
    return abs((x["fecha"] - y["fecha"]).days) <= margen


def _moda(vals):
    vals = [v for v in vals if v]
    return Counter(vals).most_common(1)[0][0] if vals else None


def agrupar(con) -> int:
    filas = [dict(r) for r in con.execute("""SELECT c.*, n.publicado, n.medio FROM codificacion c JOIN nota n ON n.id = c.nota_id
        WHERE c.version = ? AND c.es_protesta = 1 AND c.ubigeo IS NOT NULL""", (VERSION,))]
    for r in filas:
        r["fecha"] = _f(r["fecha_evento"]) or _f(r["publicado"])
    padre = list(range(len(filas)))

    def raiz(i):
        while padre[i] != i:
            padre[i] = padre[padre[i]]; i = padre[i]
        return i
    por_dep = {}
    for i, r in enumerate(filas):
        por_dep.setdefault(r["ubigeo"][:2], []).append(i)
    for idx in por_dep.values():  # ponytail: O(n²) por departamento; indexar por fecha si pasa de miles por día
        for a in range(len(idx)):
            for b in range(a + 1, len(idx)):
                if mismo_evento(filas[idx[a]], filas[idx[b]]):
                    padre[raiz(idx[a])] = raiz(idx[b])
    grupos = {}
    for i in range(len(filas)):
        grupos.setdefault(raiz(i), []).append(filas[i])
    con.execute("DELETE FROM evento_prensa"); con.execute("DELETE FROM evento_nota")
    for eid, g in enumerate(grupos.values(), 1):
        g.sort(key=lambda r: r["publicado"] or "")
        estados = [r["estado"] for r in g]
        estado = "suspendida" if estados[-1] == "suspendida" else "ocurrida" if "ocurrida" in estados else "anunciada"
        anuncios = [_f(r["publicado"]) for r in g if r["estado"] == "anunciada" and r["publicado"]]
        fecha = _moda(r["fecha_evento"] for r in g) or g[0]["publicado"][:10]
        ubigeo = max((r["ubigeo"] for r in g), key=lambda u: (len(u), sum(x["ubigeo"] == u for x in g)))
        con.execute("INSERT INTO evento_prensa VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
            eid, estado, min(anuncios).isoformat() if anuncios else None, fecha, ubigeo,
            {2: "departamento", 4: "provincia", 6: "distrito"}[len(ubigeo)],
            _moda(r["accion"] for r in g), _moda(r["actor"] for r in g), _moda(r["reclamo"] for r in g),
            _moda(r["tipo_conflicto"] for r in g), _moda(r["empresa"] for r in g), _moda(r["operacion"] for r in g),
            len(g), len({r["medio"] for r in g})))
        con.executemany("INSERT OR IGNORE INTO evento_nota VALUES (?, ?)", [(eid, r["nota_id"]) for r in g])
    con.commit()
    return len(grupos)


# --- Defensoría: lugar → ubigeo y fecha → ISO -------------------------------------------------------------

MESES = "enero febrero marzo abril mayo junio julio agosto setiembre octubre noviembre diciembre".split()


def fecha_defensoria(texto, anio, mes):
    f = str(texto or "").lower().replace("septiembre", "setiembre")
    if m := re.match(r"(\d{1,2})/(\d{1,2})/(\d{2,4})", f):
        y = int(m[3]) + (2000 if int(m[3]) < 100 else 0)
        try:
            return date(y, int(m[2]), int(m[1]))
        except ValueError:
            return None
    if (m := re.search(r"(\d{1,2}) de (\w+)", f)) and m[2] in MESES:
        mm = MESES.index(m[2]) + 1
        try:
            return date(anio - (mm > mes), mm, int(m[1]))
        except ValueError:
            return None
    return None


def ubicar_texto(texto):
    """'Espinar, Cusco' / 'Lima Metropolitana' / 'Trujillo' → (código, precisión)."""
    regiones = catalogo()[0]
    partes = [p.strip() for p in re.split(r"[,;/()–-]| y ", texto or "") if p.strip()]
    region = next((p for p in partes if norm(p) in regiones), None)
    mejor = (None, None)
    for p in partes:
        if p is region:
            continue
        for intento in (dict(distrito=p), dict(provincia=p)):
            u, prec = resolver(region=region, pista=region, **intento)
            if u and len(u) > len(mejor[0] or ""):
                mejor = (u, prec)
    return mejor if mejor[0] else resolver(region=region)


def ubicar_defensoria(con) -> int:
    filas = con.execute("SELECT reporte_num, n, lugar, actores FROM accion_protesta WHERE ubigeo IS NULL").fetchall()
    n = 0
    for num, i, lugar, actores in filas:
        u, _ = ubicar_texto(lugar)
        if u:
            con.execute("UPDATE accion_protesta SET ubigeo = ?, departamento = ? WHERE reporte_num = ? AND n = ?",
                        (u, catalogo()[3].get(u[:2]), num, i)); n += 1
    con.commit()
    return n


# --- Validación ---------------------------------------------------------------------------------------------

def _kappa(pares):
    pares = [(a, b) for a, b in pares if a and b]
    if not pares:
        return None
    n = len(pares); po = sum(a == b for a, b in pares) / n
    ca, cb = Counter(a for a, _ in pares), Counter(b for _, b in pares)
    pe = sum(ca[k] * cb[k] for k in ca) / n / n
    return round((po - pe) / (1 - pe), 2) if pe < 1 else 1.0


def _eventos(con, desde, hasta):
    ev = [dict(r) for r in con.execute("SELECT * FROM evento_prensa WHERE fecha_evento BETWEEN ? AND ?",
                                         ((desde - timedelta(3)).isoformat(), (hasta + timedelta(3)).isoformat()))]
    for e in ev:
        e["fecha"] = _f(e["fecha_evento"])
    return ev


def _match(ev, ubigeo, fecha):
    return [e for e in ev if _lugar_compatible(e["ubigeo"], ubigeo) and abs((e["fecha"] - fecha).days) <= 1]


def validar(con, mes: str) -> str:
    anio, m = map(int, mes.split("-"))
    desde = date(anio, m, 1); hasta = (date(anio + (m == 12), m % 12 + 1, 1) - timedelta(1))
    ev = _eventos(con, desde, hasta)
    out = [f"Eventos de prensa {mes}: {sum(desde <= e['fecha'] <= hasta for e in ev)}"]
    acc = []
    for r in con.execute("""SELECT a.*, r.anio, r.mes FROM accion_protesta a JOIN reporte r ON r.num = a.reporte_num
            WHERE a.ubigeo IS NOT NULL AND r.anio * 100 + r.mes BETWEEN ? AND ?""", (anio * 100 + m, anio * 100 + m + 1)):
        f = fecha_defensoria(r["fecha"], r["anio"], r["mes"])
        if f and desde <= f <= hasta:
            acc.append((r, f))
    if acc:
        det = [(r, f, _match(ev, r["ubigeo"], f)) for r, f in acc]
        hit = [x for x in det if x[2]]
        socio = [x for x in det if EXTRACTIVO.search(x[0]["demanda"] or "")]
        ant = [(f - _f(min(e["fecha_anuncio"] for e in es if e["fecha_anuncio"]))).days for r, f, es in hit
               if any(e["fecha_anuncio"] for e in es)]
        ant = [d for d in ant if d > 0]
        out.append(f"Defensoría {mes}: {len(acc)} acciones con lugar; detectadas por prensa {len(hit) / len(acc):.0%}"
                   f" (socioambientales {sum(bool(x[2]) for x in socio)}/{len(socio)})")
        out.append(f"  anunciadas antes: {len(ant)} de {len(hit)} detectadas"
                   + (f", anticipación mediana {median(ant):.0f} días" if ant else ""))
        por_dep = Counter(r["departamento"] for r, f, es in det); hit_dep = Counter(r["departamento"] for r, f, es in hit)
        out.append("  por departamento: " + "; ".join(f"{d} {hit_dep[d]}/{n}" for d, n in por_dep.most_common(8)))
    eg = [dict(r) for r in con.execute("SELECT * FROM egpp_evento WHERE duplicado_de IS NULL AND fecha BETWEEN ? AND ?",
                                         (desde.isoformat(), hasta.isoformat()))]
    if eg:
        pares = []
        for e in eg:
            ms = _match(ev, e["ubigeo"], _f(e["fecha"]))
            if ms:
                pares.append((e, ms[0]))
        out.append(f"EGPP {mes}: {len(eg)} eventos; encontrados en prensa {len(pares) / len(eg):.0%}; kappa acción "
                   f"{_kappa([(e['accion_1'], p['accion']) for e, p in pares])}, reclamo "
                   f"{_kappa([(e['reclamo'], p['reclamo']) for e, p in pares])}, distrito "
                   f"{_kappa([(e['ubigeo'], p['ubigeo']) for e, p in pares])}")
    return "\n".join(out)
