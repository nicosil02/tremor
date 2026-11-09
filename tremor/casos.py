"""Expediente de casos: ¿Tremor tenía en alerta la zona antes de cada medida de fuerza contra una operación?

Toma las medidas de fuerza extractivas de la Defensoría en el periodo de prueba (2024+, que el modelo no vio al
entrenar) y busca, en los 3 meses previos, el puesto de su zona entre todas las zonas con operación: modelo frente a
la regla ingenua ("donde hubo, habrá"). Escribe docs/casos.md. `python -m tremor.casos`."""
import json
import sys

import numpy as np
import pandas as pd

from tremor.db import RAIZ, conectar
from tremor.modelo import de_caso, extractivo, nivel_accion

TOPE = 0.05  # en alerta: entre el 5% de zonas con más riesgo


def casos(con) -> pd.DataFrame:
    d = pd.read_sql("""SELECT a.ubigeo, r.anio * 12 + r.mes - 1 AS m, a.medida, COALESCE(a.actores, '') AS actores,
                              COALESCE(a.demanda, '') AS texto FROM accion_protesta a JOIN reporte r ON r.num = a.reporte_num
                       WHERE length(a.ubigeo) = 6 AND r.anio >= 2024""", con)
    d = d[(np.array([extractivo(a, x) for a, x in zip(d.actores, d.texto)]) | de_caso(con, d)) & (d.medida.map(nivel_accion) >= 3)]
    vec = json.loads((RAIZ / "docs" / "web.json").read_text(encoding="utf-8"))["vecinos"]
    pr = pd.read_sql("SELECT ubigeo, m, modelo, pct FROM modelo_prediccion WHERE objetivo = 'z_extractivo'", con)
    zonas = {u: {u, *vec.get(u, [])} for u in pr.ubigeo.unique()}
    filas = []
    for r in d.drop_duplicates(["ubigeo", "m"]).itertuples():
        x = pr[pr.ubigeo.isin([u for u, z in zonas.items() if r.ubigeo in z]) & pr.m.between(r.m - 3, r.m - 1)]
        if x.empty:
            continue  # sin operación cerca o fuera del periodo de prueba
        mejor = x.groupby("modelo").pct.min()
        z = x[x.modelo != "ingenuo"].sort_values("pct").iloc[0]
        if r.ubigeo in set(x.ubigeo):  # si el distrito tiene operación propia, se nombra esa zona
            z = x[(x.modelo != "ingenuo") & (x.ubigeo == r.ubigeo)].sort_values("pct").iloc[0]
        filas.append({"ubigeo": r.ubigeo, "m": r.m, "medida": r.medida, "actores": r.actores, "zona": z.ubigeo,
                      "modelo": mejor.drop("ingenuo").min(), "ingenuo": mejor.get("ingenuo", np.nan),
                      "meses": x[x.ubigeo == z.ubigeo].query("modelo != 'ingenuo'").sort_values("m").pct.round(3).tolist()})
    return pd.DataFrame(filas)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    con = conectar()
    t = casos(con)
    u = pd.read_csv(RAIZ / "tremor" / "ubigeo.csv", dtype=str)
    lug = dict(zip(u.ubigeo, u.distrito.str.title() + ", " + u.provincia.str.title()))
    op = pd.read_sql("SELECT ubigeo, unidad, empresa, etapa FROM operacion WHERE tipo != 'proyecto'", con)
    # la operación que se nombra: en operación primero y de la empresa con más unidades (Antapaccay antes que una junior)
    op = op.assign(r=~op.etapa.str.startswith("operación"), t=-op.groupby("empresa").unidad.transform("size"))
    corta = lambda e: e.title().split(" Sociedad")[0].split(" S.A")[0].split(" Sucursal")[0].split(" Sa")[0]
    opde = {u: f"{g.unidad.iloc[0]} ({corta(g.empresa.iloc[0])})" for u, g in op.sort_values(["r", "t"]).groupby("ubigeo")}
    a, b = t.modelo <= TOPE, t.ingenuo <= TOPE
    mes = lambda m: f"{['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'set', 'oct', 'nov', 'dic'][m % 12]} {m // 12}"
    fila = lambda r: (f"| {mes(r.m)} | {lug.get(r.ubigeo, r.ubigeo)} | {r.medida[:60]} | {r.actores[:60]} | "
                      f"{opde.get(r.zona, r.zona)} | {pc(r.modelo)} | {pc(r.ingenuo)} |")
    pc = lambda x: f"{x:.1%}".replace(".", ",")
    cab = "| Mes | Distrito | Medida | Quiénes | Operación de la zona | Modelo, top | Regla, top |\n|---|---|---|---|---|---|---|"
    texto = f"""# Expediente de casos 2024-2026

Medidas de fuerza contra operaciones extractivas registradas por la Defensoría del Pueblo de enero de 2024 en adelante,
periodo que el modelo no vio al entrenar. Para cada una se mira el puesto de su zona entre todas las zonas con
operación en los tres meses previos. "En alerta" es estar en el {TOPE:.0%} de zonas con más riesgo. La regla de
comparación es "donde hubo conflicto, habrá".

- Casos: {len(t)}.
- El modelo tenía la zona en alerta antes de {a.mean():.0%} de los casos. La regla, antes de {b.mean():.0%}.
- Juntos avisan {(a | b).mean():.0%}. El modelo agrega {(a & ~b).sum()} casos que la regla no veía y la regla {(b & ~a).sum()} que el modelo no.
- Entre el 2% de zonas más altas, el modelo tenía {(t.modelo <= .02).mean():.0%} de los casos y la regla {(t.ingenuo <= .02).mean():.0%}.

## Los que el modelo vio y la regla no

{cab}
{chr(10).join(fila(r) for r in t[a & ~b].sort_values('modelo').itertuples())}

## Los que el modelo vio con más claridad (entre el 1% más alto)

{cab}
{chr(10).join(fila(r) for r in t[t.modelo <= .01].sort_values('m').itertuples())}

## Los que se le escaparon al modelo y la regla sí vio

{cab}
{chr(10).join(fila(r) for r in t[b & ~a].sort_values('ingenuo').itertuples())}

## Los que nadie vio

{cab}
{chr(10).join(fila(r) for r in t[~a & ~b].sort_values('modelo').itertuples())}
"""
    (RAIZ / "docs" / "casos.md").write_text(texto, encoding="utf-8")
    print(f"{len(t)} casos; modelo {a.mean():.0%}, regla {b.mean():.0%}, juntos {(a | b).mean():.0%} -> docs/casos.md")


if __name__ == "__main__":
    main()
