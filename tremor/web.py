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
          "razones_cambio_1m", "razones_zona_1m", "prob_brote", "razones_brote", "zona_tranquila", "ventana_1m", "nivel_actual", "operacion_extractiva", "corredores",
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
            "operaciones": registros(tabla(con, "SELECT empresa, unidad, tipo, ubigeo FROM operacion")),
            "zonas": zonas,
            "eventos": registros(ev),
            "sutran": registros(tabla(con, "SELECT titulo, motivo, estado_via, region, provincia, distrito, ubigeo, via, "
                                           "km, fecha_evento FROM sutran_alerta WHERE motivo = 'humano' AND (vigente_hasta IS NULL OR "
                                           "vigente_hasta >= date('now')) ORDER BY fecha_evento DESC")),
            "animo": registros(tabla(con, "SELECT proyecto, menciones_7d, base_7d, alza, pct_negativo, aviso, provincias "
                                          "FROM animo WHERE menciones_7d > 0 ORDER BY menciones_7d DESC")),
            "metricas": registros(met), "mejor": mejor,
            "respaldo": registros(tabla(con, "SELECT * FROM modelo_respaldo")),
            "cobertura": cobertura(con)}


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
