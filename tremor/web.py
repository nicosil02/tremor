"""Datos de la página (docs/index.html): un solo JSON con la alerta, las operaciones por empresa, cómo le habría ido
a cada zona en 2024+, las señales en vivo y las métricas; y los límites distritales simplificados.

    python -m tremor.web            # escribe datos/exportes/web.json (viaja en la rama `datos`) y docs/distritos.json
"""
import json
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
    ev = tabla(con, "SELECT e.*, MIN(n.enlace) AS enlace, MIN(n.medio) AS medio, MIN(n.titular) AS titular "
                    "FROM evento_prensa e JOIN evento_nota en ON en.evento_id = e.id JOIN nota n ON n.id = en.nota_id "
                    f"WHERE COALESCE(e.fecha_evento, e.fecha_anuncio) >= '{desde}' GROUP BY e.id "
                    "ORDER BY COALESCE(e.fecha_evento, e.fecha_anuncio) DESC")
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
            "menciones": menciones(con)}


def menciones(con):
    """Lo que dijeron radio y medios de cada proyecto en los últimos 30 días: titular, quién, cuándo, el tono y un
    fragmento. Una por titular (la misma nota llega por el feed del medio y por Google News: se queda el enlace directo)."""
    desde = (date.today() - timedelta(days=30)).isoformat()
    m = tabla(con, "SELECT m.proyecto, m.fecha, m.medio, m.origen, m.tono, n.titular, n.resumen, n.enlace FROM mencion m "
                   f"JOIN nota n ON n.id = m.nota_id WHERE m.fecha >= '{desde}' ORDER BY m.fecha DESC")
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
    return registros(c.drop(columns="id"))


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
