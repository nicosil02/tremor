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
        con.execute("UPDATE operacion SET empresa = ?, etapa = ? WHERE unidad = ?", (f.empresa, f.etapa, f.unidad))
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


CPIM = RAIZ / "datos" / "crudos" / "minem_cartera" / "cpim-2026.pdf"  # Cartera de Proyectos de Inversión Minera (MINEM); la más reciente que haya
ETAPAS = ("INGENIERÍA DE DETALLE", "PRE-FACTIBILIDAD", "FACTIBILIDAD", "CONSTRUCCIÓN", "EJECUTANDO", "EJECUCIÓN")


GOBPE = "https://www.gob.pe"
NAVEGADOR = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}  # gob.pe responde 418 sin navegador


def bajar_cartera(carpeta=CPIM.parent):
    """La última edición de la Cartera de Proyectos de Inversión Minera (MINEM, en gob.pe), si aún no está.
    Sale una vez al año; la búsqueda de gob.pe lista todas las ediciones."""
    import re
    import requests
    r = requests.get(f"{GOBPE}/busquedas", params={"term": "cartera de proyectos de inversion minera",
                     "institucion": "minem"}, headers=NAVEGADOR, timeout=60)
    ediciones = sorted(set(re.findall(r"/institucion/minem/informes-publicaciones/\d+-cartera-de-proyectos-de-inversion-minera-(\d{4})", r.text)))
    if not ediciones:
        return None
    anio = ediciones[-1]
    destino = carpeta / f"cpim-{anio}.pdf"
    if destino.exists():
        return destino
    pagina = re.search(rf"/institucion/minem/informes-publicaciones/\d+-cartera-de-proyectos-de-inversion-minera-{anio}", r.text).group(0)
    p = requests.get(GOBPE + pagina, headers=NAVEGADOR, timeout=60)
    pdf = re.search(r"https://cdn\.www\.gob\.pe/[^\"]+\.pdf[^\"]*", p.text).group(0)
    carpeta.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(requests.get(pdf, headers=NAVEGADOR, timeout=300).content)
    print(f"  cartera minera {anio} bajada de gob.pe")
    return destino


CONTRATO = ("Te doy un decreto supremo del Perú que modifica el contrato de un lote de hidrocarburos. Di qué empresa queda "
            "como operadora del lote y qué empresas tienen participación. Si el decreto no cambia al operador, "
            'operador = null. Responde JSON {"lote": "<Lote N>", "operador": "<razón social o null>", '
            '"socios": "<empresa y % separados por coma>"}.')


def contratos(con, dias=60):
    """Cambios de titular en lotes de hidrocarburos publicados en El Peruano (normas del sector Energía y Minas): OEFA
    tarda meses en registrarlos. Cada decreto se guarda en contrato_lote; si se puede leer su texto, el LLM saca el
    operador nuevo (una vez por decreto, queda en caché) y se aplica a la tabla operacion."""
    import html
    import re
    import time
    from datetime import date, timedelta
    import requests
    from tremor.gobierno import PERUANO, TARJETA
    from tremor.llm import chat_json, SinCuota, RespuestaInvalida
    from tremor.territorio import UA
    con.execute("""CREATE TABLE IF NOT EXISTS contrato_lote (id TEXT PRIMARY KEY, fecha TEXT, lote TEXT, titulo TEXT,
                   operador TEXT, socios TEXT, leido INTEGER DEFAULT 0)""")
    hoy = date.today()
    for q in ("contrato de licencia lote", "contrato de servicios lote", "posición contractual lote"):
        r = None
        for espera in (1, 10, 30):  # el servidor corta el SSL si se le pide seguido
            time.sleep(espera)
            try:
                r = requests.get(PERUANO, headers=UA, timeout=120, params=dict(query=q, tipoPublicacion="NL", ci="ONLY",
                                 fechaIni=(hoy - timedelta(dias)).strftime("%Y%m%d"), fechaFin=hoy.strftime("%Y%m%d")))
                break
            except requests.RequestException:
                r = None
        if r is None:
            continue
        for ente, i, t in TARJETA.findall(r.content.decode("utf-8", "replace")):
            t = html.unescape(t).strip()
            lote = re.search(r"\bLote\s+([\w-]+)", t)
            if lote and ("ENERG" in ente or "PERUPETRO" in ente) and "ontrato" in t:
                con.execute("INSERT OR IGNORE INTO contrato_lote (id, fecha, lote, titulo) VALUES (?, ?, ?, ?)",
                            (i, None, f"Lote {lote.group(1)}", t))
        time.sleep(5)  # el servidor corta la conexión si se le pide seguido
    for i, lote, titulo in con.execute("SELECT id, lote, titulo FROM contrato_lote WHERE leido = 0").fetchall():
        try:
            r = requests.get(f"{PERUANO}dispositivo/NL/{i}", headers=UA, timeout=120)
            texto = html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", r.content.decode("utf-8", "replace"))))
            fecha = re.search(r"Fecha de publicaci[oó]n: (\d\d/\d\d/20\d\d)", texto)
            k = max(texto.find("DECRETA:"), texto.find("DECRETA :"), 3000)  # los considerandos que citan la cesión y los artículos
            out = chat_json(con, CONTRATO, f"{titulo}. {texto[k - 3000:k + 3000]}", "contrato-lote-1")
        except (requests.RequestException, SinCuota, RespuestaInvalida):
            time.sleep(10)
            continue  # queda para la próxima corrida; en el informe el lote sale como "contrato modificado"
        con.execute("UPDATE contrato_lote SET fecha = ?, operador = ?, socios = ?, leido = 1 WHERE id = ?",
                    (fecha and fecha.group(1), out.get("operador"), out.get("socios"), i))
        time.sleep(5)
    for lote, operador, socios, titulo, leido in con.execute(
            "SELECT lote, operador, socios, titulo, leido FROM contrato_lote ORDER BY id").fetchall():
        unidad = f"{lote} %"
        if operador:
            con.execute("UPDATE operacion SET empresa = ?, etapa = ? WHERE unidad = ? OR unidad LIKE ?",
                        (operador.upper(), f"operador según El Peruano; socios: {socios}" if socios else "operador según El Peruano", lote, unidad))
        elif not leido:
            con.execute("UPDATE operacion SET etapa = ? WHERE (unidad = ? OR unidad LIKE ?) AND etapa = 'operación'",
                        ("contrato modificado (El Peruano), titular por confirmar", lote, unidad))
    con.commit()


def cartera_minem(pdf=None):
    """Las 66 fichas de la cartera minera del MINEM: proyecto, titular, lugar, etapa, inicio y puesta en marcha.
    Cada ficha es una página en columnas: rótulo a la izquierda y valor a su derecha, a la misma altura."""
    import re
    import pymupdf
    from tremor.lugares import resolver
    pdf = pdf or max(CPIM.parent.glob("cpim-*.pdf"))
    filas = []
    for p in pymupdf.open(pdf):
        bl = [(l["bbox"][0], l["bbox"][1], " ".join("".join(s["text"] for s in l["spans"]).split()))
              for bk in p.get_text("dict")["blocks"] for l in bk.get("lines", [])]
        if not any(t == "Titular Minero" for _, _, t in bl):
            continue
        def campo(rotulo):
            r = next(((x, y) for x, y, t in bl if t == rotulo), None)
            if not r:
                return None
            v = sorted((y, t) for x, y, t in bl if r[0] + 90 < x < r[0] + 260 and -8 < y - r[1] < 14 and t)
            return " ".join(t for _, t in v) or None
        titulo = next((t for x, y, t in bl if y < 60 and t.isupper() and len(t) > 3), "")
        r = next(((x, y) for x, y, t in bl if t == "Etapa de avance"), None)  # el valor va debajo: CONCEPTUAL, FACTIBILIDAD...
        etapa = next((t for x, y, t in sorted(bl, key=lambda b: b[1]) if r and abs(x - r[0]) < 200 and 0 < y - r[1] < 30 and t), None)
        deps, provs, dists = (re.split(r"\s*/\s*|\s+y\s+", campo(c) or "") for c in ("Departamento", "Provincia", "Distrito"))
        inicio, _, fin = (campo("Inicio/ﬁn de ejecución") or "").partition(" / ")
        for k, dist in enumerate(dists):
            ub, _ = resolver(deps[min(k, len(deps) - 1)], provs[min(k, len(provs) - 1)], dist, None)
            filas.append({"empresa": campo("Titular Minero"), "unidad": titulo.title(), "ubigeo": ub, "etapa_minem": etapa,
                          "inicio": inicio.strip(), "puesta_en_marcha": campo("Puesta en marcha operativa"),
                          "subtipo": campo("Subtipo de Proyecto"), "capex": campo("Inversión CAPEX")})
    return pd.DataFrame(filas)


def proyectos(con, desde=2021):
    """Lo que aún no opera pero se está por construir, que también puede encender un conflicto:
    la cartera de proyectos mineros del MINEM (GEOCATMIN, edición 2023, con etapa) y los proyectos nuevos con
    estudio ambiental aprobado por el SENACE desde `desde` (minería, hidrocarburos y electricidad).
    La cartera 2026 viene del PDF del MINEM (datos/crudos/minem_cartera, se baja a mano de gob.pe); sin él, la de 2023."""
    import geopandas as gpd
    from tremor.distritos import CARTERA
    distritos = gpd.read_file(GEOJSON)[["ubigeo", "geometry"]]
    try:
        bajar_cartera()
    except Exception as e:  # sin red o gob.pe cambió: se sigue con la que haya
        print(f"  cartera minera: no se pudo revisar gob.pe ({e.__class__.__name__})")
    if any(CPIM.parent.glob("cpim-*.pdf")):  # la cartera 2026 del MINEM (PDF, jun 2026), con etapa, inicio y puesta en marcha
        c = cartera_minem().dropna(subset=["ubigeo"])
        fase = c.etapa_minem.fillna("etapa sin dato").str.lower().replace({"ejecución": "en construcción", "ejecutando": "en construcción"})
        cuando = [f", operaría en {p}" if p and p[:2] == "20" else "" for p in c.puesta_en_marcha.fillna("")]
        a = pd.DataFrame({"empresa": c.empresa, "unidad": c.unidad, "tipo": "proyecto", "ubigeo": c.ubigeo,
                          "etapa": ["proyecto, " + f + w + f" (cartera MINEM {max(CPIM.parent.glob('cpim-*.pdf')).stem[-4:]})" for f, w in zip(fase, cuando)],
                          "nuevo": c.subtipo.fillna("").str.startswith("Nuevo")})
    else:  # respaldo: la cartera 2023 del GEOCATMIN
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
    contratos(con)  # decretos de El Peruano
    corregir(con)   # y lo verificado a mano (operadores.csv) manda
    # El mismo proyecto puede venir de la cartera, del SENACE y de OEFA (Tía María): mismo distrito y las palabras
    # de un nombre contenidas en las del otro ("Yumpag" y "Yumpag - Carama"). Si OEFA ya lo fiscaliza, no se
    # duplica: se anota en su fila que está en la cartera (sin afirmar la etapa: la cartera es de 2023).
    VACIAS = {"proyecto", "exploracion", "minera", "de", "del", "la", "el", "unidad", "y", "-"}
    pal = lambda u: {w for w in norm(u).replace("-", " ").split() if w not in VACIAS}
    igual = lambda x, y: bool(x and y) and (x <= y or y <= x)
    oefa = [(e, u, str(ub), pal(u)) for e, u, ub in con.execute("SELECT empresa, unidad, ubigeo FROM operacion")]
    t, ya = [], set()
    for f in pd.concat([a, b]).itertuples(index=False):
        p = pal(f.unidad)
        cand = [(q == p, ub == str(f.ubigeo), -len(q ^ p), e, u) for e, u, ub, q in oefa  # misma provincia basta: la
                if ub[:4] == str(f.ubigeo)[:4] and igual(p, q)]                                # cartera da a veces solo la provincia
        hay = max(cand)[3:] if cand else None  # "Michiquillay" es la unidad de Southern, no los pasivos de Activos Mineros
        if hay or f.unidad in ya:
            ya.add(f.unidad)
            if not hay:
                continue
            if getattr(f, "nuevo", True) is True and "cartera" in f.etapa:  # una ampliación no vuelve proyecto a la mina
                con.execute("UPDATE operacion SET etapa = ? WHERE empresa = ? AND unidad = ? AND etapa = 'operación'",
                            (f"unidad OEFA; proyecto {f.unidad}: " + f.etapa.replace("proyecto, ", ""), *hay))
        elif not any(str(g.ubigeo)[:4] == str(f.ubigeo)[:4] and igual(p, pal(g.unidad)) for g in t):
            t.append(f)
    pd.DataFrame(t).drop(columns="nuevo", errors="ignore").to_sql("operacion", con, if_exists="append", index=False)
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
