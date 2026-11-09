"""Vista por empresa: sus operaciones (OEFA) y la alerta de la zona de cada una.

    python -m tremor.empresas cargar          # tabla operacion(empresa, unidad, tipo, ubigeo, etapa): OEFA + proyectos
    python -m tremor.empresas proyectos       # solo titulares corregidos y proyectos (MINEM, SENACE)
    python -m tremor.empresas "las bambas"    # la alerta de cada operación y cómo le habría ido en 2024+
"""
import sys

import pandas as pd

from tremor.db import RAIZ, conectar
from tremor.distritos import GEOJSON, OEFA, arcgis
from tremor.lugares import norm

HID = f"{OEFA}/SERV_HID_MFICAM_INTERV/MapServer"
CAPAS = [("mineria", f"{OEFA}/SERV_MINERIA_MFICAM_INTERV/MapServer/0", "operación"),
         ("hidrocarburos", f"{HID}/1", "operación"),                       # lotes en explotación
         ("hidrocarburos", f"{HID}/4", "operación"),                       # Oleoducto Norperuano
         ("hidrocarburos", f"{HID}/2", "lote en exploración (OEFA)")]       # aún no producen


def cargar(con):
    """Una fila por unidad fiscalizable y distrito. Minas: el distrito del centro de la unidad (como `oefa`);
    lotes en explotación: todos los distritos que tocan."""
    import geopandas as gpd
    distritos = gpd.read_file(GEOJSON)[["ubigeo", "geometry"]]
    filas, huellas = [], []
    for tipo, capa, etapa in CAPAS:
        g = gpd.GeoDataFrame.from_features(arcgis(capa, "OBJECTID,ADMINISTRADO,UNIDAD_FISCALIZABLE", geometria=True,
                                                  lote=200), crs=4326)
        g = g[g.geometry.notna() & ~g.geometry.is_empty]
        g["geometry"] = g.geometry.make_valid()
        g = g.dissolve(by=["ADMINISTRADO", "UNIDAD_FISCALIZABLE"]).reset_index()
        huellas.append(g.assign(tipo=tipo, geometry=g.geometry.simplify(0.0005))[
            ["ADMINISTRADO", "UNIDAD_FISCALIZABLE", "tipo", "geometry"]])
        if tipo == "mineria":
            g = g.set_geometry(g.to_crs(32718).geometry.representative_point().to_crs(4326))  # el centroide de una unidad en varias partes puede caer fuera (Coriminas salía en Musga)
            cruce = gpd.sjoin(g, distritos, predicate="within")
        else:
            cruce = gpd.sjoin(g, distritos, predicate="intersects")
        filas.append(pd.DataFrame({"empresa": cruce.ADMINISTRADO.str.strip(), "unidad": cruce.UNIDAD_FISCALIZABLE.str.strip(),
                                   "tipo": tipo, "ubigeo": cruce.ubigeo, "etapa": etapa}))
    t = pd.concat(filas).drop_duplicates(["empresa", "unidad", "ubigeo"])
    t = t[~((t.etapa != "operación") & t.empresa.str.contains("LIQUIDACI", case=False))]  # lotes de empresas que se van
    t.to_sql("operacion", con, if_exists="replace", index=False)
    con.commit()
    print(f"{len(t)} operaciones-distrito de {t.empresa.nunique()} empresas (OEFA)")
    proyectos(con)
    h = pd.concat(huellas).rename(columns={"ADMINISTRADO": "empresa", "UNIDAD_FISCALIZABLE": "unidad"})
    h["empresa"], h["unidad"] = h.empresa.str.strip(), h.unidad.str.strip()
    import re
    texto = gpd.GeoDataFrame(h, crs=4326).to_json(drop_id=True)
    (RAIZ / "docs" / "operaciones.json").write_text(re.sub(r"(\d+\.\d{4})\d+", r"\1", texto), encoding="utf-8")  # huella de cada unidad, para el mapa


OPERADORES = RAIZ / "tremor" / "operadores.csv"


def corregir(con):
    """OEFA tarda en registrar los cambios de titular (el Lote 192 sigue a nombre de Pluspetrol, que lo dejó en 2015).
    tremor/operadores.csv lleva el titular vigente, con su fuente; se revisa a mano cuando cambia un contrato."""
    for f in pd.read_csv(OPERADORES).itertuples():
        con.execute("UPDATE operacion SET empresa = ?, etapa = ? WHERE empresa IN (?, ?) AND unidad = ?",
                    (f.empresa, f.etapa, f.empresa_oefa, f.empresa, f.unidad))
    con.commit()


SENACE_NUEVOS = ("EIA-d", "EIA-sd")  # estudios de proyectos nuevos; MEIA, ITS y DIA modifican o son exploración menor


def limpiar_proyecto(s):
    """'EIA-SD DEL PROYECTO "PARQUE EÓLICO URANI Y SU INTERCONEXION AL SEIN"' → 'Parque Eólico Urani'."""
    import re
    q = ' "“”«»,'
    s = re.sub(r"^.*?\bPROYECTO\b\s*(?:DE\s+EXPLORACI[OÓ]N\s+MINERA\s*)?", "", s, flags=re.I).strip(q) or s
    s = re.sub(r"^ESTUDIO DE IMPACTO AMBIENTAL\w*\s*(SEMI)?DETALLADO\s*(DEL?\s*)?|^EIA[\s-]*S?D\s+", "", s, flags=re.I)
    s = re.sub(r"\s+Y SU (INTERCONEXI[OÓ]N|L[IÍ]NEA).*$|,\s*(AMPLIACIONES|SUBESTACIONES|SUSESTACIONES).*$", "", s.strip(q), flags=re.I)
    return re.sub(r"\s+", " ", s.strip(q)).title()


def proyectos(con, desde=2021):
    """Lo que aún no opera pero se está por construir, que también puede encender un conflicto:
    la cartera de proyectos mineros del MINEM (GEOCATMIN, edición 2023, con etapa) y los proyectos nuevos con
    estudio ambiental aprobado por el SENACE desde `desde` (minería, hidrocarburos y electricidad).
    ponytail: la cartera del GEOCATMIN es la de 2023; la de 2025 del MINEM está solo en PDF."""
    import geopandas as gpd
    from tremor.distritos import CARTERA
    distritos = gpd.read_file(GEOJSON)[["ubigeo", "geometry"]]
    c = gpd.GeoDataFrame.from_features(arcgis(f"{CARTERA}/1", "nom_proy,est_proy,emp_local,inicio_opr", geometria=True), crs=4326)
    c = gpd.sjoin(c[c.est_proy.fillna("") != "Mina"], distritos, predicate="within")
    a = pd.DataFrame({"empresa": c.emp_local.str.strip(), "unidad": c.nom_proy.str.strip(), "tipo": "proyecto",
                      "ubigeo": c.ubigeo, "etapa": "proyecto, " + c.est_proy.str.lower() + " (cartera MINEM 2023)"})
    s = pd.read_sql("SELECT ubigeo, anio, actividad, tipo, proyecto, titular FROM senace_certificacion "
                    f"WHERE anio >= {desde} AND tipo IN {SENACE_NUEVOS}", con)
    b = pd.DataFrame({"empresa": s.titular.str.strip(), "unidad": s.proyecto.map(limpiar_proyecto), "tipo": "proyecto",
                      "ubigeo": s.ubigeo, "etapa": [f"proyecto, EIA aprobado en {x} ({y.lower()})" for x, y in zip(s.anio, s.actividad)]})
    con.execute("DELETE FROM operacion WHERE tipo = 'proyecto'")
    con.execute("UPDATE operacion SET etapa = 'operación' WHERE tipo != 'proyecto' AND etapa NOT LIKE 'lote en%'")
    corregir(con)
    # El mismo proyecto puede venir de la cartera, del SENACE y de OEFA (Tía María): mismo distrito y las palabras
    # de un nombre contenidas en las del otro ("Yumpag" y "Yumpag - Carama"). Si OEFA ya lo fiscaliza, no se
    # duplica: se anota en su fila que está en la cartera (sin afirmar la etapa: la cartera es de 2023).
    VACIAS = {"proyecto", "exploracion", "minera", "de", "del", "la", "el", "unidad", "y", "-"}
    pal = lambda u: {w for w in norm(u).replace("-", " ").split() if w not in VACIAS}
    igual = lambda x, y: bool(x and y) and (x <= y or y <= x)
    oefa = [(e, u, str(ub), pal(u)) for e, u, ub in con.execute("SELECT empresa, unidad, ubigeo FROM operacion")]
    t = []
    for f in pd.concat([a, b]).itertuples(index=False):
        p = pal(f.unidad)
        cand = [(q == p, -len(q ^ p), e, u) for e, u, ub, q in oefa if ub == str(f.ubigeo) and igual(p, q)]
        hay = max(cand)[2:] if cand else None  # "Michiquillay" es la unidad de Southern, no los pasivos de Activos Mineros
        if hay:
            if "ampliacion" not in p and "cartera" in f.etapa:
                con.execute("UPDATE operacion SET etapa = ? WHERE empresa = ? AND unidad = ? AND etapa = 'operación'",
                            ("unidad OEFA; " + f.etapa.replace("proyecto, ", "en "), *hay))
        elif not any(str(g.ubigeo) == str(f.ubigeo) and igual(p, pal(g.unidad)) for g in t):
            t.append(f)
    pd.DataFrame(t).to_sql("operacion", con, if_exists="append", index=False)
    con.commit()
    print(f"{len(t)} proyectos-distrito nuevos ({len(a)} filas de la cartera MINEM, {len(b)} con EIA del SENACE desde {desde})")


def vista(con, texto):
    """Operaciones de las empresas cuyo nombre (o el de la unidad) contiene `texto`, con la alerta de su zona."""
    op = pd.read_sql("SELECT * FROM operacion", con)
    t = norm(texto)
    op = op[[t in norm(f"{e} {u}") for e, u in zip(op.empresa, op.unidad)]]
    al = pd.read_sql("SELECT ubigeo, lugar, prob_zona, prob_zona_extractivo, razones_zona_extractivo, puesto_zona, "
                     "puesto_zona_extractivo, alerta_inmediata, senal_prensa, animo_proyectos, ventana FROM alerta", con)
    v = op.merge(al, on="ubigeo", how="left")
    return v.sort_values("prob_zona_extractivo", ascending=False)


def historial(con, texto, top=0.10):
    """Cómo le habría ido a la empresa en la prueba (2024+): en cada mes, la zona de cada operación queda "en alerta"
    si está en el `top` de zonas con operación. Cuenta los meses con medida de fuerza en los 3 siguientes
    (eventos), cuántos tuvo en alerta antes (vistos) y cuántas alertas acertaron. Modelo frente a la regla ingenua."""
    ubigeos = set(vista(con, texto).ubigeo)
    pr = pd.read_sql("SELECT * FROM modelo_prediccion", con)
    pr = pr[pr.ubigeo.isin(ubigeos)].assign(alerta=lambda d: d.pct <= top)
    g = pr.groupby(["objetivo", "modelo"]).apply(lambda d: pd.Series({
        "zonas": d.ubigeo.nunique(), "meses_zona": len(d), "eventos": int(d.y.sum()),
        "vistos": int((d.y.astype(bool) & d.alerta).sum()), "alertas": int(d.alerta.sum())}), include_groups=False)
    g["pct_vistos"] = (g.vistos / g.eventos.clip(lower=1)).round(2)
    g["acierto_alertas"] = (g.vistos / g.alertas.clip(lower=1)).round(2)
    return g.reset_index()


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    con = conectar()
    if sys.argv[1:] == ["cargar"]:
        return cargar(con)
    if sys.argv[1:] == ["proyectos"]:  # sin volver a bajar OEFA
        return proyectos(con)
    texto = " ".join(sys.argv[1:])
    v = vista(con, texto)
    with pd.option_context("display.width", 250, "display.max_colwidth", 70):
        print(v[["empresa", "unidad", "lugar", "prob_zona", "prob_zona_extractivo", "puesto_zona_extractivo",
                 "alerta_inmediata", "razones_zona_extractivo"]].to_string(index=False))
        print(historial(con, texto).to_string(index=False))


if __name__ == "__main__":
    main()
