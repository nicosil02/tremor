"""Datos de la página (docs/index.html): un solo JSON con la alerta, las operaciones por empresa, cómo le habría ido
a cada zona en 2024+, las señales en vivo y las métricas; y los límites distritales simplificados.

    python -m tremor.web            # escribe datos/exportes/web.json (viaja en la rama `datos`) y docs/distritos.json
"""
import functools
import json
import re
import sys
from datetime import date, timedelta

import pandas as pd

from tremor.db import DATOS, RAIZ, conectar

DOCS = RAIZ / "docs"
ALERTA = ["ubigeo", "lugar", "prob", "prob_extractivo", "prob_crisis", "prob_zona", "prob_zona_extractivo", "prob_1m",
          "prob_extractivo_1m", "puesto", "puesto_extractivo", "puesto_zona", "puesto_zona_extractivo", "razones", "razones_extractivo",
          "razones_zona", "razones_zona_extractivo", "prob_zona_1m", "normal_zona_1m", "cambio_zona_1m",
          "razones_cambio_1m", "normal_zona_ext", "cambio_zona_ext", "razones_cambio_ext", "razones_zona_1m", "prob_brote", "razones_brote", "zona_tranquila", "ventana_1m", "nivel_actual", "operacion_extractiva", "corredores",
          "alerta_inmediata", "senal_prensa", "enlace_prensa", "animo_proyectos"]


def tabla(con, sql):
    try:
        return pd.read_sql(sql, con)
    except Exception:  # tabla que aún no existe (p. ej. modelo_prediccion antes de la primera corrida)
        return pd.DataFrame()


def registros(df):
    return json.loads(df.to_json(orient="records", force_ascii=False, double_precision=4))


def datos(con):
    a = tabla(con, "SELECT * FROM alerta")
    a = a[[c for c in ALERTA if c in a.columns]]
    pr = tabla(con, "SELECT objetivo, modelo, ubigeo, m, pct, y FROM modelo_prediccion")
    zonas = {}
    for (u, o), d in (pr.groupby(["ubigeo", "objetivo"]) if len(pr) else []):
        d = d.sort_values("m")
        mejor = d[d.modelo != "ingenuo"]
        ing = d[d.modelo == "ingenuo"].set_index("m").pct.reindex(mejor.m)
        zonas.setdefault(u, {})[o] = {"m0": int(mejor.m.iloc[0]), "y": mejor.y.astype(int).tolist(),
                                      "pct": mejor.pct.round(3).tolist(), "ingenuo": ing.round(3).tolist()}
    desde = (date.today() - timedelta(days=45)).isoformat()
    ev = tabla(con, "SELECT * FROM (SELECT e.*, n.enlace, n.medio, n.titular, ROW_NUMBER() OVER (PARTITION BY e.id ORDER BY "
                    "(n.enlace LIKE '%news.google%') + (n.medio IN ('Facebook', 'Instagram', 'YouTube', 'TikTok', 'X')), "
                    "-length(COALESCE(n.resumen, '')), n.publicado) AS k "
                    "FROM evento_prensa e JOIN evento_nota en ON en.evento_id = e.id JOIN nota n ON n.id = en.nota_id "
                    f"WHERE COALESCE(e.fecha_evento, e.fecha_anuncio) >= '{desde}') WHERE k = 1 "
                    "ORDER BY COALESCE(fecha_evento, fecha_anuncio) DESC").drop(columns="k")
    if len(ev):  # lo que dice el cuerpo de las notas: quién se suma, quién se retira, si se suspendió, si es transporte urbano
        texto = dict(con.execute("""SELECT en.evento_id, group_concat(n.titular || '. ' || coalesce(n.resumen, ''), ' ')
                                    FROM evento_nota en JOIN nota n ON n.id = en.nota_id GROUP BY 1"""))
        leido = [leer(texto.get(i, "")) for i in ev.id]
        for k in ("adhieren", "retiran", "suspendido", "urbano", "puntos", "plazo"):
            ev[k] = [x[k] for x in leido]
        ev["fecha_evento"] = [dia_dicho(t, f) for t, f in zip(ev.titular, ev.fecha_evento)]
        ev = pd.DataFrame(juntar(ev.to_dict("records")))
        # el LLM a veces marca "ocurrida" lo que la nota anuncia: si la fecha aún no llega, es un anuncio
        hoy = (pd.Timestamp.now(tz="America/Lima")).strftime("%Y-%m-%d")
        ev.loc[ev.fecha_evento.astype(str) > hoy, "estado"] = "anunciada"
    met = tabla(con, "SELECT objetivo, modelo, metrica, valor FROM modelo_metrica WHERE metrica IN ('precision_top20', "
                     "'precision_top20_li', 'precision_top20_ls', 'captura_top10pct', 'tasa_base')")
    ventana = tabla(con, "SELECT ventana, mes_base FROM alerta LIMIT 1")
    val = tabla(con, "SELECT objetivo, modelo, valor FROM modelo_metrica WHERE metrica = 'validacion_top20'")
    mejor = val.loc[val.groupby("objetivo").valor.idxmax()].set_index("objetivo").modelo.to_dict() if len(val) else {}
    return {"creado": date.today().isoformat(),
            "ventana": ventana.ventana.iloc[0] if len(ventana) else None,
            "mes_base": ventana.mes_base.iloc[0] if len(ventana) else None,
            "alerta": registros(a),
            "operaciones": registros(tabla(con, "SELECT empresa, unidad, tipo, ubigeo, etapa FROM operacion")),
            "zonas": zonas,
            "eventos": registros(ev),
            "sutran": sutran(con),
            "rutas": rutas_distrito(con),
            "radios": radios_provincia(),
            "animo": registros(tabla(con, "SELECT proyecto, menciones_7d, base_7d, alza, pct_negativo, aviso, provincias "
                                          "FROM animo WHERE menciones_7d > 0 ORDER BY menciones_7d DESC")),
            "metricas": registros(met), "mejor": mejor,
            "respaldo": registros(tabla(con, "SELECT * FROM modelo_respaldo")),
            "cobertura": cobertura(con),
            "vecinos": vecinos(con),
            "casos": casos_zona(con),
            "calibracion": calibracion(con),
            "menciones": menciones(con),
            "focos": focos(con)}


def _norm(s):
    import unicodedata
    return unicodedata.normalize("NFKD", s.lower()).encode("ascii", "ignore").decode()


@functools.lru_cache
def _lugares():
    """nombre normalizado → ubigeos de provincia (4) y distrito (6); nombres cortos o repetidos en más de 2 sitios, fuera."""
    import csv
    prov, dist = {}, {}
    for r in csv.DictReader(open(RAIZ / "tremor" / "ubigeo.csv", encoding="utf-8")):
        prov.setdefault(_norm(r["provincia"]), set()).add(r["ubigeo"][:4])
        dist.setdefault(_norm(r["distrito"]), set()).add(r["ubigeo"])
    # "Barranca" es provincia de Lima y también distrito en Loreto: manda la provincia
    idx = {k: v for k, v in dist.items() if len(v) <= 2} | prov
    return {k: sorted(v) for k, v in idx.items() if len(k) >= 4}


SUMA = re.compile(r"se suma|sumar[aá]n|sumarse|acatar|respald|adhie|adhes|plegar|participar|bases? de|gremios? de")
NO = re.compile(r"no (se )?(suma|acata|participa|pleg)|deslig|se retira|desist|no acatar|no se plegar")
SUSPENDE = re.compile(r"(suspend|levant|desconvoc|posterg|aplaz|cancel)\w*\s+(el |la |su |del )?(paro|huelga|bloqueo|medida|paralizaci)")
CARGA = re.compile(r"carga pesada|transporte de carga|transportistas de carga")  # "carga pesada y mototaxistas" sigue siendo carga
CORTA = re.compile(r"bloque|quema de llantas|cortaron|cerraron|tomaron|piquete")
DONDE = re.compile(r"carretera|v[ií]as?\b|puente|ingreso|salida|km\b|kil[oó]metro|avenida|\bav\.|[oó]valo|jir[oó]n|plaza|cruce|desv[ií]o|panamericana|interoce[aá]nica")
DIAS = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]


def puntos(texto, n=3):
    """Las frases que dicen dónde se corta o se cortó el paso (vías, puentes, ingresos), sin repetirse."""
    out = []
    for f in re.split(r"(?<=[.;!?])\s+|\n", texto or ""):
        f = " ".join(f.split())
        if 25 < len(f) < 260 and CORTA.search(f.lower()) and DONDE.search(f.lower()) and not any(f[:60] == o[:60] for o in out):
            out.append(f)
    return out[:n]


MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "setiembre", "octubre", "noviembre", "diciembre"]
PLAZO = re.compile(r"plazo|ultim[aá]tum|de lo contrario|caso contrario|de no (ser )?atend")


def plazo(texto, hoy=None):
    """La fecha que vence un plazo ("dio plazo hasta el jueves 12 de noviembre para que el ministro llegue, de lo
    contrario paro regional"): ese día puede empezar la medida aunque nadie la haya convocado todavía."""
    hoy, out = hoy or date.today(), None
    for f in re.split(r"(?<=[.;!?])\s+|\n", (texto or "").lower()):
        if not PLAZO.search(f):
            continue
        for d, m in re.findall(r"(\d{1,2}) de (" + "|".join(MESES) + "|septiembre)", f):
            mes = 9 if m == "septiembre" else MESES.index(m) + 1
            try:
                x = date(hoy.year, mes, int(d))
            except ValueError:
                continue
            x = x.replace(year=hoy.year + 1) if (hoy - x).days > 180 else x
            out = max(out or x, x)
    return out.isoformat() if out else None


def familia(accion):
    a = (accion or "").lower()
    return "paro" if re.search(r"paro|huelga", a) else "bloqueo" if "bloque" in a else "marcha" if re.search(r"march|moviliz", a) else a


def juntar(evs):
    """Una protesta contada una vez: el mismo día, el mismo reclamo y un lugar dentro del otro (Huánuco, la provincia y el
    departamento), con la misma medida o el mismo actor, son un solo evento. Queda el de más notas, con el lugar más preciso."""
    out = []
    for e in sorted(evs, key=lambda e: -(e.get("n_notas") or 0)):
        u = str(e["ubigeo"])
        par = next((o for o in out if o["fecha_evento"] == e["fecha_evento"] and o["reclamo"] == e["reclamo"] and u != "00"
                    and (u.startswith(str(o["ubigeo"])) or str(o["ubigeo"]).startswith(u))
                    and (familia(o["accion"]) == familia(e["accion"]) or o["actor"] == e["actor"])), None)
        if par is None:
            out.append(dict(e)); continue
        if len(u) > len(str(par["ubigeo"])):
            par["ubigeo"] = e["ubigeo"]
        par["n_notas"] = (par.get("n_notas") or 0) + (e.get("n_notas") or 0)
        for k in ("adhieren", "retiran", "puntos"):
            par[k] = list(dict.fromkeys((par.get(k) or []) + (e.get(k) or [])))
        par["suspendido"] = bool(par.get("suspendido")) or bool(e.get("suspendido"))
        par["plazo"] = max([x for x in (par.get("plazo"), e.get("plazo")) if isinstance(x, str)], default=None)
    visto = set()  # el mismo plazo citado por varias protestas del departamento: un solo aviso, en la de más notas
    for e in out:
        k = (e.get("plazo"), str(e["ubigeo"])[:2])
        if isinstance(k[0], str):
            e["plazo"] = None if k in visto else k[0]; visto.add(k)
    return sorted(out, key=lambda e: str(e.get("fecha_evento") or e.get("fecha_anuncio") or ""), reverse=True)


def dia_dicho(titular, fecha):
    """Si el titular dice "martes 20" y la fecha no cae martes, la nota es vieja (Google la reindexó): se toma el último
    mes, hasta tres atrás, en que el 20 fue martes."""
    m = re.search(r"\b(lunes|martes|mi[eé]rcoles|jueves|viernes|s[aá]bado|domingo)\s+(\d{1,2})\b", (titular or "").lower())
    if not m or not fecha:
        return fecha
    dia = DIAS.index(m.group(1).replace("é", "e").replace("á", "a"))
    f = date.fromisoformat(str(fecha)[:10])
    for k in range(4):
        y, mes = (f.year, f.month - k) if f.month > k else (f.year - 1, f.month - k + 12)
        try:
            d = date(y, mes, int(m.group(2)))
        except ValueError:
            continue
        if d.weekday() == dia:
            return d.isoformat()
    return fecha


URBANO = re.compile(r"extorsi|transporte (publico|urbano)|combis?\b|colectiver|mototaxi|choferes asesinad|asesinatos? de chofer")


def leer(texto):
    """Reglas sobre el cuerpo de las notas de un evento: lugares que anuncian sumarse o retirarse (por oración),
    si la medida se suspendió y si es transporte urbano (no frena la carga)."""
    t, idx = _norm(texto), _lugares()
    adh, ret = set(), set()
    for o in re.split(r"[.;\n]", t):
        destino = ret if NO.search(o) else adh if SUMA.search(o) else None
        if destino is not None:
            destino.update(u for k, us in idx.items() if re.search(rf"\b{re.escape(k)}\b", o) for u in us)
    return {"adhieren": sorted(adh - ret), "retiran": sorted(ret), "suspendido": bool(SUSPENDE.search(t)), "urbano": bool(URBANO.search(t)) and not CARGA.search(t), "puntos": puntos(texto), "plazo": plazo(texto)}


def focos(con, n=5):
    """Dónde protestó antes cada actor en cada departamento (EGPP, solo eventos con distrito conocido, no la capital
    por defecto). Sirve cuando una nota dice solo "paro en Arequipa": los transportistas de carga de Arequipa
    bloquearon 6 veces en La Joya, así que ese tramo es el más probable. {"04|Transportistas de carga": [[ubigeo, veces], ...]}"""
    out = {}
    for d, actor, u, k in con.execute("""SELECT substr(ubigeo, 1, 2), actor, ubigeo, count(*) FROM egpp_evento
            WHERE capital_por_defecto = 0 AND length(ubigeo) = 6 AND actor IS NOT NULL GROUP BY 1, 2, 3 ORDER BY 4 DESC"""):
        xs = out.setdefault(f"{d}|{actor}", [])
        if len(xs) < n:
            xs.append([u, k])
    return out


def menciones(con):
    """Lo que dijeron radio y medios de cada proyecto en los últimos 30 días: titular, quién, cuándo, el tono y un
    fragmento. Una por titular (la misma nota llega por el feed del medio y por Google News: se queda el enlace directo)."""
    desde = (date.today() - timedelta(days=30)).isoformat()
    con.execute("CREATE TABLE IF NOT EXISTS nota_tema (nota_id TEXT PRIMARY KEY, tema TEXT, p_tema REAL, tono INTEGER, p_tono REAL)")
    # tema y tono del transformer (tremor.clasifica); si la nota aún no pasó por él, el tono del léxico
    m = tabla(con, "SELECT m.proyecto, m.fecha, m.medio, m.origen, COALESCE(t.tono, m.tono) AS tono, t.tema, n.titular, n.resumen, n.enlace "
                   "FROM mencion m JOIN nota n ON n.id = m.nota_id LEFT JOIN nota_tema t ON t.nota_id = m.nota_id "
                   f"WHERE m.fecha >= '{desde}' ORDER BY m.fecha DESC")
    if not len(m):
        return []
    m["google"] = m.enlace.str.contains("news.google")
    m = m.sort_values(["google", "fecha"], ascending=[True, False]).drop_duplicates(["proyecto", "titular"]).sort_values("fecha", ascending=False)
    m["resumen"] = m.resumen.fillna("").str.split(r'"use strict"|The post |\[…\]', regex=True).str[0].str.strip().str.slice(0, 300)
    return registros(m.drop(columns="google"))


def calibracion(con):
    """Qué tan cierto es el porcentaje: en 2024-2026, por tramo de lo que dijo el modelo, en qué parte de las veces
    hubo de verdad conflicto contra la operación en la zona (la página lo muestra junto a la cifra)."""
    d = tabla(con, "SELECT puntaje, y FROM modelo_prediccion WHERE objetivo = 'z_extractivo' AND modelo = 'ensamble' AND y IS NOT NULL")
    if not len(d):
        return []
    cortes = [0, 0.1, 0.25, 0.35, 0.5, 1]
    g = d.groupby(pd.cut(d.puntaje, cortes, include_lowest=True), observed=True).y.agg(["size", "mean"])
    return [{"desde": i.left if i.left > 0 else 0, "hasta": i.right, "n": int(r["size"]), "hubo": round(r["mean"], 3)} for i, r in g.iterrows()]


def sutran(con):
    """Bloqueos vigentes por protesta, con lo que dicen los medios de cada uno (tremor.sutran.contexto)."""
    con.execute("CREATE TABLE IF NOT EXISTS sutran_contexto (id TEXT PRIMARY KEY, contexto TEXT, fuentes TEXT, actualizado TEXT NOT NULL)")
    s = registros(tabla(con, """SELECT s.titulo, s.motivo, s.estado_via, s.region, s.provincia, s.distrito, s.ubigeo, s.via, s.km,
                                       s.fecha_evento, s.lat, s.lng, c.contexto, c.fuentes
                                FROM sutran_alerta s LEFT JOIN sutran_contexto c USING (id)
                                WHERE s.motivo = 'humano' AND (s.vigente_hasta IS NULL OR s.vigente_hasta >= date('now'))
                                ORDER BY s.fecha_evento DESC"""))
    for x in s:
        x["fuentes"] = json.loads(x["fuentes"] or "[]")
    return s


def radios_provincia():
    """Las radios que Tremor escucha en cada provincia (tremor/radios.csv), para nombrarlas en las alertas."""
    import csv
    from pathlib import Path
    out = {}
    with open(Path(__file__).with_name("radios.csv"), encoding="utf-8") as f:
        for r in csv.DictReader(f):
            out.setdefault(r["ubigeo_provincia"], []).append(" ".join(r["medio"].split()))
    return out


def rutas_distrito(con):
    """Las rutas nacionales (código MTC) que cruzan cada distrito: por ahí sale y entra la carga de sus operaciones.
    Con esto la página dice qué operaciones toca una vía bloqueada. El trazo va en docs/rutas.geojson."""
    out = {}
    for u, rs in con.execute("SELECT ubigeo, rutas FROM distrito_corredor"):
        out.setdefault(u, set()).update(r.strip() for r in rs.split(","))
    return {u: sorted(r) for u, r in out.items()}


def casos_zona(con):
    """Conflictos de la Defensoría vigentes en el último reporte, en distritos con operación, sus vecinos o su
    provincia: quién reclama (el nombre del caso, que nombra a la comunidad o al frente), qué pide, en qué estado
    está y si hay diálogo. No se publican los actores ni los hechos del mes: pueden nombrar personas."""
    c = tabla(con, """SELECT c.id, c.nombre, c.tipo, c.ubigeo, cm.estado, cm.dialogo, cm.fase, cm.con_hechos,
                             substr(COALESCE(cm.descripcion, c.descripcion), 1, 320) AS reclamo, r.anio, r.mes
                      FROM caso c JOIN caso_mes cm ON cm.caso_id = c.id JOIN reporte r ON r.num = cm.reporte_num
                      WHERE cm.reporte_num = (SELECT MAX(num) FROM reporte) AND cm.estado IN ('activo', 'latente')""")
    c["reclamo"] = [None if not isinstance(x, str) or x.strip() == n.strip() else x for x, n in zip(c.reclamo, c.nombre)]
    c["resumen"] = resumir(con, c)
    # con quién es (tremor.contexto): empresa y unidad enlazadas a la base, quién reclama, tema; y lo de prensa
    for t_, cols in [("caso_vinculo", "caso_id, quien_reclama, contra_empresa, unidad, tema, empresa_op, unidad_op, ubigeo_op"),
                     ("caso_contexto", "caso_id, resumen AS resumen_prensa, fuentes")]:
        try:
            c = c.merge(tabla(con, f"SELECT {cols} FROM {t_}").rename(columns={"caso_id": "id"}), on="id", how="left")
        except Exception:  # tabla aún no creada
            pass
    if "resumen_prensa" in c:
        c["resumen"] = c.resumen.fillna(c.pop("resumen_prensa"))
        c["fuentes"] = [json.loads(x) if isinstance(x, str) else [] for x in c.fuentes]
    c["medios"] = medios_recientes(con, c.nombre)
    return registros(c.drop(columns="id"))


PREFIJO = re.compile(r"^(comunidad(es)? (campesinas?|nativas?)|comunidad(es)?|cc\.?|c\.c\.|cn|c\.n\.)\s+(de(l)?\s+)?", re.I)


GENERICAS = {"minera", "minería", "mineria", "empresa", "compañía", "proyecto", "ilegal", "informal", "unidad", "comunidad", "campesina"}
CONFLICTO = r"conflict|protest|\bparo\b|bloque|comunidad|minera|di[aá]logo|\bmesa\b|reclam|denunci"


def medios_recientes(con, nombres, dias=60):
    """Lo último que dijeron radio y medios de cada conflicto: la Defensoría publica con uno o dos meses de rezago, y
    un caso "en diálogo" en su reporte puede haberse roto ayer. Se busca el nombre de la comunidad (o el del caso
    hasta el guion) en titulares y resúmenes de los últimos 60 días."""
    desde = (date.today() - timedelta(days=dias)).isoformat()
    n = tabla(con, f"SELECT medio, substr(publicado, 1, 10) AS fecha, titular, resumen, enlace FROM nota WHERE publicado >= '{desde}' "
                   "AND COALESCE(filtro, '') != 'medio_extranjero' ORDER BY publicado DESC")
    texto = (n.titular.fillna("") + " " + n.resumen.fillna("")).str.lower()
    out = []
    for nom in nombres:
        partes = [x.strip().lower() for x in re.split(r"\s*[-–]\s*", PREFIJO.sub("", nom or ""))]
        clave = partes[0]
        if len(clave) < 5:
            out.append([]); continue
        # el nombre solo engaña ("Independencia" trae notas del papa): con contraparte ("Raura"), la nota la nombra
        # también; sin ella, la nota tiene que hablar de conflicto, minería o la comunidad
        palabras = [w.strip("()") for w in (partes[1].split() if len(partes) > 1 else [])]
        otra = max((w for w in palabras if len(w) >= 4 and w not in GENERICAS), key=len, default=None)
        tiene = texto.str.contains(r"\b" + re.escape(clave) + r"\b", regex=True)
        tiene &= texto.str.contains(re.escape(otra)) if otra else texto.str.contains(CONFLICTO)
        m = n[tiene].drop_duplicates("titular").head(2)
        out.append(m[["medio", "fecha", "titular", "enlace"]].to_dict("records"))
    return out


RESUMIR = ("Resume cada conflicto social en UNA oración de máximo 22 palabras, en castellano formal: quién reclama "
           "(por rol o comunidad, nunca nombres de personas) y qué pide. Sin fechas ni siglas sin explicar. "
           'Responde JSON {"r": [{"i": <id>, "s": "<oración>"}]}.')


def resumir(con, c):
    """Una oración por caso, del texto completo de la Defensoría (no del recorte). Caché en llm_cache; sin cupo, None."""
    from tremor.llm import chat_json, SinCuota, RespuestaInvalida
    desc = dict(con.execute("""SELECT c.id, COALESCE(cm.descripcion, c.descripcion) FROM caso c JOIN caso_mes cm ON cm.caso_id = c.id
                               WHERE cm.reporte_num = (SELECT MAX(num) FROM reporte)""").fetchall())
    ids = [i for i in c.id if desc.get(i)]
    out = {}
    for k in range(0, len(ids), 3):
        lote = "\n".join(f"[{i}] {desc[i][:900]}" for i in ids[k:k + 3])
        try:
            out |= {int(x["i"]): x["s"] for x in chat_json(con, RESUMIR, lote, "resumen-caso-1").get("r", []) if x.get("s")}
        except SinCuota as e:
            print("  resumen de casos sin cupo:", str(e)[:90])
            break
        except (RespuestaInvalida, ValueError, KeyError, TypeError) as e:  # un lote mal formado: se queda sin resumen
            print("  resumen de casos, lote omitido:", str(e)[:90])
    return [out.get(i) for i in c.id]


def vecinos(con):
    """Para cada distrito con operación, los distritos que limitan con él: su zona de influencia (como en el modelo)."""
    import geopandas as gpd
    from tremor.modelo import DATOS
    ops = set(tabla(con, "SELECT DISTINCT ubigeo FROM operacion").ubigeo)
    g = gpd.read_file(DATOS / "distritos.geojson")[["ubigeo", "geometry"]].to_crs(32718)
    par = gpd.sjoin(g[g.ubigeo.isin(ops)].assign(geometry=lambda d: d.buffer(300)), g, predicate="intersects")
    par = par[par.ubigeo_left != par.ubigeo_right]
    return par.groupby("ubigeo_left").ubigeo_right.apply(sorted).to_dict()


def cobertura(con):
    """Por año, qué parte de las protestas ve cada fuente y cuántas no vio ninguna (solo agregados)."""
    from tremor.fusion import cobertura as c
    f = tabla(con, "SELECT * FROM protesta_fusion")
    return registros(c(f)) if len(f) else []


def geo():
    """Distritos simplificados (~1 MB) con su ubigeo; la geometría no cambia, va en docs/."""
    from shapely.geometry import MultiPolygon, mapping, shape
    from shapely.geometry.polygon import orient
    g = json.loads((DATOS / "distritos.geojson").read_text(encoding="utf-8"))

    def horario(geom):  # d3 pide el anillo exterior en sentido horario; si no, pinta el resto del mundo
        partes = geom.geoms if isinstance(geom, MultiPolygon) else [geom]
        partes = [orient(q, sign=-1.0) for q in partes if q.geom_type == "Polygon" and not q.is_empty]
        return MultiPolygon(partes) if len(partes) > 1 else partes[0]

    feats = [{"type": "Feature", "properties": {"u": f["properties"]["ubigeo"]},
              "geometry": mapping(horario(shape(f["geometry"]).simplify(0.004, preserve_topology=True)))}
             for f in g["features"]]
    texto = json.dumps({"type": "FeatureCollection", "features": feats}, separators=(",", ":"))
    import re
    return re.sub(r"(\d+\.\d{3})\d+", r"\1", texto)  # 3 decimales: ~100 m, de sobra para un mapa del país


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    con = conectar()
    (DATOS / "exportes").mkdir(parents=True, exist_ok=True)
    salida = DATOS / "exportes" / "web.json"
    salida.write_text(json.dumps(datos(con), ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    DOCS.mkdir(exist_ok=True)
    if "--geo" in sys.argv or not (DOCS / "distritos.json").exists():
        (DOCS / "distritos.json").write_text(geo(), encoding="utf-8")
    print(f"{salida} ({salida.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
