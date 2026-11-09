"""Una sola base de protestas desde todas las fuentes, y cuánto se les escapa a todas juntas.

Cada fuente ve una parte: la Defensoría lo que le llega a sus oficinas, la EGPP lo que sale en los diarios que lee,
ACLED lo que recoge de prensa y redes, la radio y la prensa local lo que pasa cerca, las empresas lo que les para la
operación. La unidad común es distrito × mes (ACLED solo trae el mes). Cada fila dice qué fuentes la vieron.

Con varias listas que se solapan se estima cuántas protestas no vio ninguna (estimación por sistemas múltiples, la
misma idea con que se estiman víctimas no registradas en conflictos). Supone que las fuentes son independientes;
si dos tienden a ver lo mismo (prensa grande y EGPP), subestima lo que falta. Se reporta como rango.

    python -m tremor.fusion            # escribe protesta_fusion y muestra la cobertura por año
"""
import itertools
import sys

import pandas as pd

from tremor.db import conectar

FUENTES = ("defensoria", "egpp", "acled", "prensa", "sutran", "bolsa")


def mes(fecha):
    f = str(fecha or "")
    return int(f[:4]) * 12 + int(f[5:7]) - 1 if len(f) >= 7 and f[:4].isdigit() and f[5:7].isdigit() else None


def leer(con) -> dict[str, pd.DataFrame]:
    q = lambda s: pd.read_sql(s, con)
    f = {"defensoria": q("SELECT a.ubigeo, r.anio * 12 + r.mes - 1 AS m FROM accion_protesta a "
                         "JOIN reporte r ON r.num = a.reporte_num"),
         "egpp": q("SELECT ubigeo, fecha FROM egpp_evento WHERE duplicado_de IS NULL AND capital_por_defecto = 0"),
         "prensa": q("SELECT ubigeo, COALESCE(fecha_evento, fecha_anuncio) AS fecha FROM evento_prensa "
                     "WHERE estado <> 'anunciada'"),
         "sutran": q("SELECT ubigeo, COALESCE(fecha_evento, visto_primero) AS fecha FROM sutran_alerta")}
    try:  # ACLED no se redistribuye: puede no estar en la base
        f["acled"] = q("SELECT ubigeo, anio * 12 + mes - 1 AS m FROM acled_evento WHERE tipo IN ('Protests', 'Riots')")
    except Exception:
        pass
    try:
        from tremor.bolsa import ubigeos_incidentes
        f["bolsa"] = ubigeos_incidentes(con)
    except Exception:
        pass
    for k, t in f.items():
        if "m" not in t:
            t["m"] = t.pop("fecha").map(mes)
        f[k] = t[t.ubigeo.astype(str).str.len().eq(6) & t.m.notna()].astype({"m": int})[["ubigeo", "m"]]
    return f


def fusion(fuentes: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """distrito × mes con una columna 0/1 por fuente."""
    t = pd.concat([d.drop_duplicates().assign(fuente=k) for k, d in fuentes.items()], ignore_index=True)
    return pd.crosstab([t.ubigeo, t.m], t.fuente).clip(upper=1).reset_index()


def no_vistas(f: pd.DataFrame, listas) -> tuple[float, float, float]:
    """Protestas que ninguna lista vio, entre las celdas que las `listas` cubren. Devuelve (mín, máx) entre el
    estimador de Chapman de cada par y, con 3 listas, el log-lineal sin interacción triple (el tercer valor, el central:
    admite que cada par de fuentes dependa entre sí)."""
    est = []
    for a, b in itertools.combinations(listas, 2):
        n1, n2, m = f[a].sum(), f[b].sum(), (f[a] & f[b]).sum()
        n = (n1 + 1) * (n2 + 1) / (m + 1) - 1  # Chapman: total estimado con dos listas
        est.append(n - f[list(listas)].max(axis=1).sum())  # menos lo que vio al menos una lista
    if len(listas) == 3:
        c = f.groupby(list(listas)).size()
        g = lambda *k: c.get(k, 0)
        den = g(1, 1, 0) * g(1, 0, 1) * g(0, 1, 1)
        if den:
            est.append(g(1, 0, 0) * g(0, 1, 0) * g(0, 0, 1) * g(1, 1, 1) / den)
    est = [max(e, 0) for e in est]
    return (min(est), max(est), est[-1]) if est else (float("nan"),) * 3


def cobertura(f: pd.DataFrame, listas=("defensoria", "egpp", "acled")) -> pd.DataFrame:
    """Por año: cuánto ve cada fuente de la unión y el rango de protestas que no vio ninguna."""
    filas = []
    for anio, g in f.groupby(f.m // 12):
        if not all(g[k].any() for k in listas):
            continue
        u = len(g)
        lo, hi, ll = no_vistas(g, listas)
        filas.append({"anio": anio, "vistas": u, **{k: round(g[k].mean(), 2) for k in f.columns if k in FUENTES},
                      "no_vistas": round(ll), "rango": f"{lo:.0f}–{hi:.0f}", "cobertura_union": round(u / (u + ll), 2)})
    return pd.DataFrame(filas)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    con = conectar()
    f = fusion(leer(con))
    f.to_sql("protesta_fusion", con, if_exists="replace", index=False)
    con.commit()
    print(f"{len(f)} distrito-mes con protesta; fuentes: " + ", ".join(f"{k} {f[k].sum()}" for k in FUENTES if k in f))
    print(cobertura(f).to_string(index=False))


if __name__ == "__main__":
    main()
