"""Base de protestas de la EGPP PUCP → tabla egpp_evento y perfil de conflictividad por distrito.

Fuente: Arce, M. (2024). Base de Protestas Sociales del Perú; actualización EGPP PUCP, dic. 2025.
Contrato: specs/002-prensa-egpp/contracts/cli.md. No se guarda Comentar_t (nombres de dirigentes).
"""
import argparse
import re
import sys

import pandas as pd

from tremor.db import DATOS, conectar

EXTRACTIVO = re.compile(r"miner|\bminas?\b|petrol|\blotes?\s*\d|hidrocarb|\bgas\b|gasoducto|oleoducto|hidroel"
                        r"|represa|derrame|contamina|relave|concesi|extracci", re.I)
COMUNIDAD = {"Comunidades campesinas", "Comunidades nativas", "Rondas campesinas", "Frentes de defensa", "Pobladores",
             "Agricultores", "Pueblos indígenas", "Pobladores AAHH", "Ganaderos", "Autoridades"}
EMPRESA = {"Empresas Privadas", "Empresas Estatales"}

# Operaciones conocidas: alias → nombre canónico (research R7). El orden importa: lo específico primero.
OPERACIONES = [(re.compile(p, re.I), n) for p, n in [
    (r"t[ií]a mar[ií]a", "Tía María"), (r"\bconga\b", "Conga"), (r"las bambas|\bmmg\b", "Las Bambas"),
    (r"antamina", "Antamina"), (r"yanacocha", "Yanacocha"), (r"tintaya|antapaccay|xstrata|glencore", "Tintaya-Antapaccay"),
    (r"r[ií]o blanco|majaz", "Río Blanco"), (r"cuajone", "Cuajone"), (r"toquepala", "Toquepala"),
    (r"quellaveco", "Quellaveco"), (r"cerro verde", "Cerro Verde"), (r"camisea", "Camisea"),
    (r"lote\s*192|lote\s*1-?ab", "Lote 192"), (r"lote\s*8\b", "Lote 8"), (r"lote\s*95", "Lote 95"),
    (r"oleoducto|petroper", "Petroperú-Oleoducto"), (r"pluspetrol", "Pluspetrol"), (r"shougang|hierro per|marcona", "Shougang"),
    (r"bear creek|santa ana", "Santa Ana"), (r"doe run|la oroya", "La Oroya"), (r"centromin", "Centromin"), (r"toromocho|chinalco", "Toromocho"),
    (r"constancia|hudbay", "Constancia"), (r"michiquillay", "Michiquillay"), (r"ca[ñn]ariaco", "Cañariaco"),
    (r"coroccohuayco", "Coroccohuayco"), (r"southern", "Southern"), (r"buenaventura", "Buenaventura"),
    (r"repsol|la pampilla", "Repsol"), (r"\bcasapalca\b", "Casapalca"), (r"raura", "Raura"),
]]
_NOMBRE = re.compile(r"(?i:proyecto|mina|minera|compañía minera|empresa minera|unidad minera)\s+(?:(?i:minero)\s+)?"
                     r"([A-ZÁÉÍÓÚÑ][\wáéíóúñ-]+(?:\s+[A-ZÁÉÍÓÚÑ][\wáéíóúñ-]+)?)")

_NO_NOMBRE = {"Primer", "Municipalidades", "Municipalidad", "Gobierno", "Estado", "El", "La", "Los", "Las", "Del", "En",
              "Ministerio", "Distrital", "Provincial", "Regional", "Nacional", "Estatal", "Comunidad",
              "Demandan", "Exigen", "Piden", "Arma", "Día", "No", "Tres", "Segundo", "Tercer", "Arequipeño"}


def operacion(*textos) -> str | None:
    t = " ".join(str(x) for x in textos if isinstance(x, str))
    for pat, nombre in OPERACIONES:
        if pat.search(t):
            return nombre
    m = _NOMBRE.search(t)
    return m[1] if m and m[1].split()[0] not in _NO_NOMBRE else None


def tipo_conflicto(actor, reclamo, sector, adversario, *textos) -> str:
    t = " ".join(str(x) for x in textos if isinstance(x, str))
    if actor in ("Mineros", "Trabajadores petroleros") and reclamo == "Laborales":
        return "laboral_minero"
    senal = bool(EXTRACTIVO.search(t))
    if reclamo in ("Ambientales", "Territoriales") and (senal or adversario in EMPRESA):
        return "socioambiental_extractivo"
    if (actor in COMUNIDAD or sector == "Comunidades tradicionales") and senal:
        return "socioambiental_extractivo"
    return "otro"


def cargar(con, ruta, version="2025-12") -> int:
    df = pd.read_excel(ruta)
    filas = []
    for r in df.to_dict("records"):
        g = lambda c: None if pd.isna(r.get(c)) else r.get(c)
        dist = int(r["Distrito_id"])
        if dist == 1101:  # único caso con código mal formado: Ica, Ica
            dist = 110101
        ubigeo, precision = (f"{dist:06d}", "distrito") if dist != 160405 else ("1604", "provincia")
        textos = (g("Reclamo_t"), g("Comentar_t"), g("Institución_1"), g("Institución_2"))
        filas.append((
            int(r["ID"]), pd.Timestamp(r["Fecha"]).date().isoformat(), ubigeo, precision, int(ubigeo.endswith("01")),
            g("Periódico"), g("Sector_1"), g("Actor_1"), g("Actor_t"),
            g("Acción_1"), g("Acción_2"), g("Acción_3"), g("Acción_4"), g("Acción_t"),
            g("Adversario"), g("Institución_1"), g("Institución_2"), g("Reclamo"), g("Sub_Reclamo"), g("Reclamo_t"),
            g("Número_Participantes"), g("Duración_Horas"), g("Número_Heridos"), g("Número_Muertos"),
            g("Número_Detenidos"), g("Fuerza_Estatal"),
            tipo_conflicto(g("Actor_1"), g("Reclamo"), g("Sector_1"), g("Adversario"), *textos),
            operacion(*textos) if g("Adversario") in EMPRESA or EXTRACTIVO.search(" ".join(t for t in textos if t)) else None,
            None, version))
    con.execute("DELETE FROM egpp_evento")
    con.executemany(f"INSERT INTO egpp_evento VALUES ({','.join('?' * 30)})", filas)
    # Repetidos: misma fecha, lugar, actor, acción y reclamo; se conserva el de menor id (FR-004e).
    con.execute("""UPDATE egpp_evento SET duplicado_de = (SELECT MIN(b.id) FROM egpp_evento b
        WHERE b.fecha = egpp_evento.fecha AND b.ubigeo = egpp_evento.ubigeo AND b.actor IS egpp_evento.actor
          AND b.accion_1 IS egpp_evento.accion_1 AND b.reclamo_t IS egpp_evento.reclamo_t AND b.id < egpp_evento.id)""")
    con.commit()
    return len(filas)


def _top(s, n=3):
    vc = s.dropna().value_counts().head(n)
    return "; ".join(f"{k} ({v})" for k, v in vc.items()) or None


def perfil(con) -> pd.DataFrame:
    e = pd.read_sql("SELECT * FROM egpp_evento WHERE duplicado_de IS NULL", con)
    if e.empty:
        raise SystemExit("La base no tiene eventos de la EGPP: corre primero `python -m tremor.egpp cargar`.")
    e["anio"] = e.fecha.str[:4].astype(int)
    e["bloqueo"] = e[["accion_1", "accion_2", "accion_3", "accion_4"]].fillna("").agg(" ".join, axis=1).str.contains("Bloqueo")
    e["con_violencia"] = (e.heridos.fillna(0) > 0) | (e.muertos.fillna(0) > 0) | (e.fuerza_estatal == 1)
    filas = []
    for u, g in e.groupby("ubigeo"):
        rc = g.reclamo.value_counts()
        filas.append({
            "ubigeo": u, "eventos": len(g), "eventos_2015_2025": int((g.anio >= 2015).sum()),
            "primer_anio": g.anio.min(), "ultimo_anio": g.anio.max(),
            "socioambiental": int((g.tipo_conflicto == "socioambiental_extractivo").sum()),
            "laboral_minero": int((g.tipo_conflicto == "laboral_minero").sum()),
            **{k.lower(): int(rc.get(k, 0)) for k in ("Ambientales", "Territoriales", "Laborales", "Políticos",
                                                     "Económicos", "Servicios")},
            "top_subreclamos": _top(g.sub_reclamo), "top_actores": _top(g.actor),
            "pct_bloqueo": round(g.bloqueo.mean(), 3), "pct_heridos": round((g.heridos.fillna(0) > 0).mean(), 3),
            "pct_muertos": round((g.muertos.fillna(0) > 0).mean(), 3),
            "pct_represion": round((g.fuerza_estatal == 1).mean(), 3),
            "contra_empresa": int(g.adversario.isin(EMPRESA).sum()), "operaciones": _top(g.operacion),
            "capital_por_defecto": int(g.capital_por_defecto.iloc[0]),
        })
    p = pd.DataFrame(filas)
    from tremor.lugares import catalogo
    nom = catalogo()[3]
    p.insert(1, "region", p.ubigeo.str[:2].map(nom)); p.insert(2, "provincia", p.ubigeo.str[:4].map(nom))
    p.insert(3, "distrito", p.ubigeo.map(lambda u: nom.get(u) if len(u) == 6 else None))
    p = p.rename(columns={"políticos": "politicos", "económicos": "economicos"})
    p.to_sql("perfil_distrito", con, if_exists="replace", index=False)
    anual = e.groupby(["ubigeo", "anio"]).agg(
        eventos=("id", "size"), socioambiental=("tipo_conflicto", lambda s: (s == "socioambiental_extractivo").sum()),
        laboral_minero=("tipo_conflicto", lambda s: (s == "laboral_minero").sum()), con_violencia=("con_violencia", "sum"),
    ).reset_index()
    anual.to_sql("perfil_distrito_anio", con, if_exists="replace", index=False)
    (DATOS / "exportes").mkdir(parents=True, exist_ok=True)
    p.to_csv(DATOS / "exportes" / "perfil_distrito.csv", index=False)
    anual.to_csv(DATOS / "exportes" / "perfil_distrito_anio.csv", index=False)
    return p


def ranking(con, tipo=None, n=20, sin_capitales=False):
    col = {"socioambiental_extractivo": "socioambiental", "laboral_minero": "laboral_minero"}.get(tipo, "eventos")
    q = f"SELECT region, provincia, distrito, {col} AS n, operaciones, pct_muertos FROM perfil_distrito"
    if sin_capitales:
        q += " WHERE capital_por_defecto = 0"
    return pd.read_sql(q + f" ORDER BY n DESC LIMIT {int(n)}", con)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m tremor.egpp")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("cargar"); c.add_argument("ruta")
    sub.add_parser("perfil")
    r = sub.add_parser("ranking"); r.add_argument("--tipo"); r.add_argument("--n", type=int, default=20)
    r.add_argument("--sin-capitales", action="store_true")
    a = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")
    con = conectar()
    if a.cmd == "cargar":
        n = cargar(con, a.ruta)
        d, = con.execute("SELECT COUNT(*) FROM egpp_evento WHERE duplicado_de IS NOT NULL").fetchone()
        print(f"EGPP: {n} eventos cargados, {d} marcados como repetidos.")
    elif a.cmd == "perfil":
        p = perfil(con)
        print(f"Perfil: {len(p)} lugares → datos/exportes/perfil_distrito.csv")
    else:
        print(ranking(con, a.tipo, a.n, a.sin_capitales).to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
