"""Modelo de alerta (specs/005-modelo): probabilidad de una medida de fuerza en cada distrito en los meses siguientes.

`python -m tremor.modelo` → tablas `nivel_mes`, `modelo_metrica` y `alerta` (y `datos/exportes/alerta.csv`).
"""
import re
import sys

import numpy as np
import pandas as pd

from tremor.db import DATOS, ahora, conectar
from tremor.lugares import catalogo, nombre, norm

# Defensoría publica con un mes de rezago: con horizonte 1 la alerta sería de un mes que ya pasó.
HORIZONTE = 3
OBJETIVOS = ("y_fuerza", "y_extractivo", "y_crisis", "z_fuerza", "z_extractivo", "z1_fuerza", "z1_brote")
# z1_…: un solo mes, el segundo después del último reporte (el primero que todavía se puede prevenir cuando sale el
# reporte). z1_fuerza: medida de fuerza en la zona ese mes (la alerta del mes).
# z1_brote: lo mismo pero solo en zonas sin medidas de fuerza en los 3 meses previos: el arranque, que no se adivina
# repitiendo la historia. Es la prueba honesta de si el modelo anticipa algo.
# Zonas de influencia (z_…): distrito con operación extractiva + los distritos que limitan con él. Se mide solo en
# esos distritos: es lo que le importa a una empresa (un bloqueo en su zona, sea cual sea el reclamo, o uno contra ella).
OPERACION = ("unidades_mineras", "lote_explotacion", "oleoducto_norperuano", "minas_tajo_abierto",
             "minas_subterraneas", "proyectos_cartera")
INICIO = 2010 * 12  # primer mes del panel (enero 2010); la historia previa solo alimenta los rezagos
PRUEBA = 2024 * 12  # meses objetivo desde enero 2024 son prueba
CENSO = ("rural", "lengua_indigena", "autoidentificacion_indigena", "sin_agua_red", "sin_electricidad")
ELECCIONES = (2002,2006, 2010, 2014, 2018, 2022, 2026, 2030)  # municipales, en octubre
CRISIS = re.compile(r"enfrenta")
FUERZA = re.compile(r"\bparo|huelga(?! de hambre)|bloque|\btoma\b|paraliz|invasi|retenc|secuestro|motin|destrucc|"
                    r"saqueo|quema|cierre de")
# Tema extractivo de una protesta de la Defensoría (actores + demanda), sobre el texto sin tildes. Términos sacados
# de las palabras que más distinguen a los 727 casos socioambientales de la Defensoría de los demás tipos, revisados
# a mano. Sin "empresa", "agua" ni "residuos sólidos": traen conflictos laborales, de servicios y de basura.
EXTRACTIVO_TERMINOS = {
    "mineria": r"miner[aoi]|\bminas?\b|mineral|relave|tajo|socavon|concentrado de|metales pesados|mercurio|arsenico|"
               r"plomo en (?:la )?sangre|formaliz|reinfo|pasivos?(?: ambiental| minero)|cierre de mina|chancadora|"
               r"extraccion de (?:oro|cobre|mineral)|lavadero de oro|draga",
    "hidrocarburos": r"petrol|hidrocarbur|gas natural|masificacion del gas|gasoduct|oleoduct|\blote\b|derrame|\bcrudo\b|"
                     r"perupetro|petroperu|pluspetrol|camisea|repsol|\btgp\b|frontera energy|oxy\b",
    "energia": r"hidroelectr|\brepresas?\b|central (?:termica|solar|eolica)|lineas? de transmision|servidumbre",
    "ambiental": r"contamin|ambiental|remediac|impactos? (?:ambiental|negativ)|\beia\b|estudio de impacto|"
                 r"cabecera de cuenca|\boefa\b|\bsenace\b|consulta previa|zona de amortiguamiento|tala ilegal",
    "renta": r"canon|sobrecanon|regalia|fondo social|convenio marco|responsabilidad social|aporte voluntario|"
             r"concesion|explotacion|exploracion|\bextract",
    "operaciones": r"las bambas|tia maria|conga|quellaveco|yanacocha|antamina|southern|glencore|antapaccay|"
                   r"hudbay|constancia|minsur|aruntani|barrick|newmont|minera buenaventura|gold fields|nexa|volcan|raura|"
                   r"casapalca|cerro verde|toquepala|cuajone|michiquillay|rio blanco|majaz|chinalco|toromocho|"
                   r"shougang|marcona|poderosa|coimolache|canariaco|zafranal|apumayo|anabi|hochschild|"
                   r"corani|ciemsa|first quantum|bear creek|la granja|mina justa|pampa de pongo",
}
EXTRACTIVO = re.compile("|".join(EXTRACTIVO_TERMINOS.values()))
# Pliego de trabajadores de una minera o petrolera: conflicto laboral, no con la comunidad (EGPP: laboral_minero).
LABORAL = re.compile(r"^(?:ex)?trabajador|^sindicat|^obrer|^federacion (?:nacional )?de trabajadores")
PLIEGO = re.compile(r"remunera|salari|despid|utilidades|reposicion|pliego|laboral|beneficios sociales|aumento")


def extractivo(texto_actores, texto_demanda=""):
    a, d = norm(texto_actores), norm(texto_demanda)
    return bool(EXTRACTIVO.search(f"{a} {d}")) and not (LABORAL.search(a) and PLIEGO.search(d))


def mes(fecha: str) -> int:
    return int(fecha[:4]) * 12 + int(fecha[5:7]) - 1


def texto_mes(m: int) -> str:
    return f"{m // 12}-{m % 12 + 1:02d}"


def nivel_accion(accion) -> int:
    a = norm(accion)
    return 4 if CRISIS.search(a) else 3 if FUERZA.search(a) else 2


def eventos(con) -> pd.DataFrame:
    """Protestas de todas las fuentes propias (Defensoría, EGPP, prensa y radio, SUTRAN, bolsa) → (ubigeo, m, nivel
    2-4). Solo las que llegan a distrito. ACLED entra desde 2018 (su uso comercial pide licencia)."""
    q = lambda s: pd.read_sql(s, con)
    d = q("SELECT a.ubigeo, r.anio * 12 + r.mes - 1 AS m, a.medida AS accion, 0 AS victimas, "
          "COALESCE(a.actores, '') AS actores, COALESCE(a.demanda, '') AS texto FROM accion_protesta a "
          "JOIN reporte r ON r.num = a.reporte_num WHERE length(a.ubigeo) = 6")
    d["extractivo"] = np.array([extractivo(a, x) for a, x in zip(d.actores, d.texto)]) | de_caso(con, d)
    d = d.drop(columns=["texto", "actores"])
    # La EGPP asigna a la capital lo que no sabe ubicar: esos eventos no dicen nada del distrito capital.
    e = q("SELECT ubigeo, fecha, accion_1 AS accion, COALESCE(heridos, 0) + COALESCE(muertos, 0) AS victimas, "
          "tipo_conflicto <> 'otro' AS extractivo FROM egpp_evento WHERE duplicado_de IS NULL AND capital_por_defecto = 0 AND length(ubigeo) = 6")
    p = q("SELECT ubigeo, COALESCE(fecha_evento, fecha_anuncio) AS fecha, accion, estado, 0 AS victimas, "
          "COALESCE(tipo_conflicto, 'otro') <> 'otro' AS extractivo FROM evento_prensa WHERE length(ubigeo) = 6")
    # Lo que la Defensoría no ve: vías cortadas por protesta (SUTRAN) y paralizaciones que las empresas reportan a la bolsa
    s = q("SELECT ubigeo, COALESCE(fecha_evento, visto_primero) AS fecha, 'bloqueo' AS accion, 0 AS victimas, "
          "0 AS extractivo FROM sutran_alerta WHERE length(ubigeo) = 6")
    try:
        from tremor.bolsa import ubigeos_incidentes
        b = ubigeos_incidentes(con).assign(accion="bloqueo", victimas=0, extractivo=1)
    except FileNotFoundError:  # el registro de bolsa vive en datos/crudos (no se publica)
        b = s.iloc[:0]
    for t in (e, p, s, b):
        t["m"] = t["fecha"].map(mes)
    # ACLED (desde 2018, solo el mes): cuenta como medida de fuerza solo si su nota describe un paro, bloqueo o toma
    # (`fuerza`, ver distritos.acled); la violencia de turba (linchamientos, ajustes) no es protesta y queda fuera.
    # Su uso comercial pide licencia; la tabla no se publica en `datos`.
    try:
        a = q("SELECT ubigeo, anio * 12 + mes - 1 AS m, CASE WHEN fuerza THEN 'bloqueo' ELSE 'marcha' END AS accion, "
              "(subtipo = 'Excessive force against protesters') AS victimas, extractivo FROM acled_evento "
              "WHERE tipo IN ('Protests', 'Riots') AND (subtipo <> 'Mob violence' OR fuerza) AND length(ubigeo) = 6")
    except Exception:
        a = d.iloc[:0]
    t = pd.concat([d, e, p, s, b, a], ignore_index=True)
    t["nivel"] = [4 if v > 0 else nivel_accion(a) for a, v in zip(t.accion, t.victimas)]
    t.loc[t.get("estado").eq("anunciada").fillna(False).to_numpy(), "nivel"] = 2  # anunciada: tensión, aún no ocurre
    t["extractivo"] = t.extractivo.astype(bool)
    return t[["ubigeo", "m", "nivel", "extractivo"]]


SECTORIAL = re.compile(r"trabajador|sindicat|docente|maestr|estudiant|salud|medic|enfermer|sute|cas\b")


def de_caso(con, d):
    """Acción de la Defensoría que comparte al menos 2 palabras propias (no comunes) con un caso socioambiental
    activo o latente del mismo distrito o provincia ese mes: se toma como extractiva aunque no use las palabras
    clave. Las de trabajadores y estudiantes se excluyen (sus pliegos coinciden por azar con los casos)."""
    k = pd.read_sql("SELECT c.ubigeo, r.anio * 12 + r.mes - 1 AS m, COALESCE(c.nombre, '') || ' ' || "
                    "COALESCE(c.descripcion, '') || ' ' || COALESCE(c.actores, '') AS texto FROM caso_mes cm "
                    "JOIN caso c ON c.id = cm.caso_id JOIN reporte r ON r.num = cm.reporte_num "
                    "WHERE c.tipo = 'Socioambiental' AND cm.estado IN ('activo', 'latente') "
                    "AND length(c.ubigeo) >= 4", con)
    palabras = lambda s: {w for w in norm(s).split() if len(w) >= 5}
    ta = d.texto.map(palabras)
    frec = pd.Series([w for s in ta for w in s]).value_counts()
    ta = ta.map(lambda s: s - set(frec.index[frec > len(d) * 0.003]))
    casos = {}
    for r in k.itertuples():
        casos.setdefault((r.ubigeo, r.m), []).append(palabras(r.texto))
    return np.array([not SECTORIAL.search(norm(x)) and any(len(w & c) >= 2 for c in
            casos.get((u, m), []) + casos.get((u[:4], m), [])) for u, m, x, w in zip(d.ubigeo, d.m, d.texto, ta)])


def casos(con) -> pd.DataFrame:
    """Casos de la Defensoría por distrito y mes: activos, latentes y en diálogo, y lo que cambió ese mes."""
    t = pd.read_sql("SELECT cm.caso_id, c.ubigeo, r.anio * 12 + r.mes - 1 AS m, cm.estado, cm.dialogo FROM caso_mes cm "
                    "JOIN caso c ON c.id = cm.caso_id JOIN reporte r ON r.num = cm.reporte_num "
                    "WHERE length(c.ubigeo) = 6", con)
    t = cambios_de_caso(t)
    return t.groupby(["ubigeo", "m"])[["activos", "latentes", "dialogo", "nuevos", "activados",
                                       "dialogo_roto"]].sum().reset_index()


def cambios_de_caso(t):
    """Por caso y mes, frente a su reporte anterior: caso nuevo, de latente a activo, diálogo que se rompe (tenía
    diálogo y sigue activo sin él). El primer mes de la serie no cuenta como nuevo."""
    t = t.sort_values(["caso_id", "m"]).copy()
    t["activos"] = t.estado.eq("activo")
    t["latentes"] = t.estado.eq("latente")
    t["dialogo"] = t.dialogo.fillna("").str.upper().str.startswith("HAY DI")
    antes = t.groupby("caso_id")[["estado", "dialogo"]].shift()
    t["nuevos"] = antes.estado.isna() & (t.m > t.m.min())
    t["activados"] = antes.estado.eq("latente") & t.activos
    t["dialogo_roto"] = antes.dialogo.eq(True) & ~t.dialogo & t.activos
    return t


def matriz(t, columna, distritos, meses):
    """Long → matriz distritos × meses (suma)."""
    x = t.pivot_table(index="ubigeo", columns="m", values=columna, aggfunc="sum", fill_value=0)
    return x.reindex(index=distritos, columns=meses, fill_value=0).to_numpy(float)


def ventana(x, k):
    """Suma de los últimos k meses, incluido el actual (columna t: t-k+1 … t)."""
    s = np.concatenate([np.zeros((len(x), 1)), x.cumsum(axis=1)], axis=1)
    return s[:, 1:] - s[:, np.maximum(np.arange(1, x.shape[1] + 1) - k, 0)]


def anomalia(x, k=24):
    """Cuánto se aparta el valor de hoy de los k meses anteriores del mismo distrito o zona, en desviaciones (z).
    El +0.5 en el denominador evita que una zona siempre en cero salte a z enorme por un solo evento."""
    previo = lambda y: np.concatenate([np.full((len(y), 1), np.nan), y[:, :-1]], axis=1)  # termina en t-1
    media = previo(ventana(x, k)) / k
    var = previo(ventana(x ** 2, k)) / k - media ** 2
    return (x - media) / (np.sqrt(np.maximum(var, 0)) + 0.5)


ANOMALIAS = {"zona_fuerza_3": "medidas de fuerza", "zona_protestas_sin_fuerza_3": "marchas o plantones sin paro",
             "zona_casos_activos": "casos activos en la Defensoría", "zona_certificaciones_3": "certificaciones ambientales",
             "zona_emergencias_3": "emergencias por lluvias, huaicos o sequía",
             "fuerza_3_provincia": "medidas de fuerza en el resto de la provincia"}


def futuro(x, h):
    """Suma de los h meses siguientes (t+1 … t+h); NaN donde todavía no hay datos."""
    s = np.concatenate([np.zeros((len(x), 1)), x.cumsum(axis=1)], axis=1)
    n = x.shape[1]
    t = np.arange(n)
    salida = s[:, np.minimum(t + 1 + h, n)] - s[:, t + 1]
    salida[:, t + h >= n] = np.nan
    return salida


def resto(x, grupos):
    """Para cada distrito, la suma de los otros distritos de su grupo (provincia o departamento)."""
    total = pd.DataFrame(x).groupby(grupos).transform("sum").to_numpy()
    return total - x


def panel(con):
    """Panel distrito × mes con variables (todas conocidas al cierre del mes t) y objetivos a HORIZONTE meses."""
    ev, cs = eventos(con), casos(con)
    ultimo = int(pd.read_sql("SELECT MAX(r.anio * 12 + r.mes - 1) AS m FROM accion_protesta a "
                             "JOIN reporte r ON r.num = a.reporte_num", con).m[0])
    distritos = sorted(u for u in catalogo()[3] if len(u) == 6)
    meses = list(range(INICIO - 36, ultimo + 1))
    ev["fuerza"], ev["crisis"], ev["protesta"] = ev.nivel >= 3, ev.nivel == 4, 1
    ev["fuerza_extractiva"] = ev.fuerza & ev.extractivo
    F, K, P, FX = (matriz(ev, c, distritos, meses) for c in ("fuerza", "crisis", "protesta", "fuerza_extractiva"))
    A, L, D, CN, CA, DR = (matriz(cs, c, distritos, meses) for c in ("activos", "latentes", "dialogo", "nuevos",
                                                                    "activados", "dialogo_roto"))
    se = pd.read_sql("SELECT ubigeo, anio * 12 + mes - 1 AS m, tipo LIKE '%EIA%' AS eia, 1 AS cert "
                     "FROM senace_certificacion", con)
    C, E = (matriz(se, c, distritos, meses) for c in ("cert", "eia"))
    em = pd.read_sql("SELECT ubigeo, anio * 12 + mes - 1 AS m, 1 AS n FROM emergencia", con)
    EM = ventana(matriz(em, "n", distritos, meses), 3)
    EM[:, np.array(meses) < 2020 * 12 + 2] = np.nan  # el registro empieza en 2020: antes es "sin dato", no cero
    ac = pd.read_sql("SELECT ubigeo, anio * 12 + mes - 1 AS m, 1 AS n, extractivo AS x FROM acled_evento "
                     "WHERE tipo IN ('Protests', 'Riots')", con)
    AC, AX = (matriz(ac, c, distritos, meses) for c in ("n", "x"))
    sin_acled = (np.array(meses) < 2018 * 12) | (np.array(meses) + HORIZONTE >= ac.m.max())  # último mes: parcial
    # Gobierno local (tremor/gobierno.py): gasto municipal del mes, JNE en El Peruano, revocatorias e informes de control
    gm = pd.read_sql("SELECT ubigeo, m, variable, valor FROM distrito_mes", con)
    G = lambda *vs: matriz(gm[gm.variable.isin(vs)], "valor", distritos, meses)
    antes = lambda anio: np.array(meses) < anio * 12
    VAC = ventana(G("jne_vacancia", "jne_convoca", "jne_suspension"), 12)
    VAC[:, antes(2012)] = np.nan  # El Peruano indexa al JNE desde 2012 (y con huecos: 2014)
    REV = ventana(G("revocatoria_consulta"), 24)
    REV[:, antes(2012)] = np.nan
    CGR = np.roll(G("cgr_con_responsabilidad"), 2, axis=1)  # se publica ~1 mes después de emitirse: 2 de margen
    CGR = ventana(CGR, 12)
    CGR[:, antes(2019)] = np.nan  # el buscador empieza en 2018
    TOT, PRY = ventana(G("dev_total"), 12), ventana(G("dev_proyectos"), 12)
    INV = np.where(TOT > 0, PRY / np.where(TOT > 0, TOT, 1), np.nan)
    INV[:, antes(2011)] = np.nan
    PRY3 = ventana(G("dev_proyectos"), 3)
    CAE = np.where(np.roll(PRY3, 12, axis=1) > 0, PRY3 / np.where(np.roll(PRY3, 12, axis=1) > 0, np.roll(PRY3, 12, axis=1), 1) - 1, np.nan)
    CAE[:, antes(2011)] = np.nan  # obras del trimestre frente al mismo trimestre del año anterior
    nivel = np.select([K > 0, F > 0, (P > 0) | (A > 0), L > 0], [4, 3, 2, 1], 0)
    F3 = ventana(F, 3)
    W = vecinos(distritos)
    VECINDAD.update(idx={u: k for k, u in enumerate(distritos)}, W=W > 0)
    zona = lambda x: W @ x  # suma en el distrito y sus vecinos
    idx = np.where(F > 0, np.arange(len(meses)), -10 ** 6)
    v = {"fuerza_1": F, "fuerza_3": F3, "fuerza_12": ventana(F, 12), "fuerza_36": ventana(F, 36),
         "protestas_12": ventana(P, 12), "crisis_36": ventana(K, 36),
         "fuerza_extractiva_12": ventana(FX, 12), "fuerza_extractiva_36": ventana(FX, 36),
         "meses_sin_fuerza": np.minimum(np.arange(len(meses)) - np.maximum.accumulate(idx, axis=1), 120),
         "certificaciones_12": ventana(C, 12), "eia_36": ventana(E, 36), "emergencias_3": EM,
         "casos_activos": A, "casos_latentes": L, "casos_dialogo": D,
         "fuerza_3_provincia": resto(F3, [u[:4] for u in distritos]),
         "fuerza_3_departamento": resto(F3, [u[:2] for u in distritos]),
         "fuerza_3_corredor": por_corredor(con, F3, distritos),
         "nivel": nivel, "y_fuerza": (futuro(F + K, HORIZONTE) > 0).astype(float),
         "y_crisis": (futuro(K, HORIZONTE) > 0).astype(float),
         "y_extractivo": (futuro(FX, HORIZONTE) > 0).astype(float),
         "zona_fuerza_1": zona(F), "zona_fuerza_3": zona(F3), "zona_fuerza_12": zona(ventana(F, 12)),
         "zona_fuerza_36": zona(ventana(F, 36)), "zona_fuerza_extractiva_12": zona(ventana(FX, 12)),
         "zona_fuerza_extractiva_36": zona(ventana(FX, 36)), "zona_protestas_12": zona(ventana(P, 12)),
         "zona_casos_activos": zona(A), "zona_casos_dialogo": zona(D),
         "z_fuerza": (futuro(zona(F + K), HORIZONTE) > 0).astype(float),
         "z_extractivo": (futuro(zona(FX), HORIZONTE) > 0).astype(float),
         # Lo que cambió en los últimos 3 meses: señales con fecha, que suben y bajan de un mes a otro.
         "casos_nuevos_3": ventana(CN, 3), "casos_activados_3": ventana(CA, 3), "dialogo_roto_3": ventana(DR, 3),
         "zona_casos_nuevos_3": zona(ventana(CN, 3)), "zona_casos_activados_3": zona(ventana(CA, 3)),
         "zona_dialogo_roto_3": zona(ventana(DR, 3)), "zona_certificaciones_3": zona(ventana(C, 3)),
         "zona_protestas_sin_fuerza_3": zona(ventana(P - F, 3)),  # marchas, plantones, pronunciamientos
         "zona_alza": zona(F3) - zona(ventana(F, 12)) / 4, "zona_emergencias_3": zona(EM),
         "zona_vacancias_12": zona(VAC), "zona_revocatorias_24": zona(REV), "zona_control_12": zona(CGR),
         "inversion_pct_gasto": np.clip(INV, 0, 1), "obras_vs_anio_previo": np.clip(CAE, -1, 5),
         # El mes que importa es t+2: el reporte del mes t sale a mediados de t+1, y para entonces t+1 ya va por la mitad.
         "z1_fuerza": (futuro(zona(F + K), 2) - futuro(zona(F + K), 1) > 0).astype(float)}
    v["z1_brote"] = np.where(zona(F3) > 0, np.nan, v["z1_fuerza"])
    for c in ANOMALIAS:  # cada señal frente a la historia de su propia zona (no se reescala: es otra variable)
        v["anom_" + c] = anomalia(v[c])
    for y in OBJETIVOS:
        v[y][np.isnan(futuro(F, HORIZONTE))] = np.nan
    for k, x in (("v_acled", AC), ("v_acled_extractivo", AX), ("vz_acled", zona(AC)),
                 ("vz_acled_extractivo", zona(AX))):  # validación externa, no entra al modelo
        v[k] = (futuro(x, HORIZONTE) > 0).astype(float)
        v[k][:, sin_acled] = np.nan
    desde = meses.index(INICIO)
    p = pd.DataFrame({k: x[:, desde:].ravel() for k, x in v.items()})
    p.insert(0, "m", np.tile(meses[desde:], len(distritos)))
    p.insert(0, "ubigeo", np.repeat(distritos, len(meses) - desde))
    p = contexto(con, p)
    p["operacion"] = (p[list(OPERACION)].sum(axis=1) > 0).astype(float)
    p.loc[p.operacion == 0, ["z_fuerza", "z_extractivo", "z1_fuerza", "z1_brote"]] = np.nan
    p["mes_del_anio"] = p.m % 12 + 1
    return p, nivel_mes(distritos, meses, nivel)


VECINDAD = {}


def vecinos(distritos):
    """Matriz distrito × distrito con 1 en el propio distrito y en los que limitan con él (límites INEI simplificados
    a ~100 m: se tocan con un margen de 300 m)."""
    import geopandas as gpd
    g = gpd.read_file(DATOS / "distritos.geojson")[["ubigeo", "geometry"]].to_crs(32718)
    g["geometry"] = g.buffer(300)
    par = gpd.sjoin(g, g, predicate="intersects")
    i = {u: k for k, u in enumerate(distritos)}
    W = np.eye(len(distritos))
    for a, b in zip(par.ubigeo_left, par.ubigeo_right):
        if a in i and b in i:
            W[i[a], i[b]] = 1
    return W


def por_corredor(con, x, distritos):
    """Contagio por la vía: para cada distrito, lo ocurrido en los otros distritos de sus corredores (C…, AL… y los
    con nombre propio de tremor.distritos.CORREDORES). Un distrito en dos corredores suma ambos."""
    dc = pd.read_sql("SELECT DISTINCT ubigeo, corredor FROM distrito_corredor", con)
    m = pd.crosstab(dc.ubigeo, dc.corredor).reindex(index=distritos, fill_value=0).clip(upper=1).to_numpy(float)
    return m @ (m.T @ x) - m.sum(axis=1, keepdims=True) * x


def nivel_mes(distritos, meses, nivel):
    i, j = np.nonzero(nivel)
    return pd.DataFrame({"ubigeo": np.array(distritos)[i], "mes": [texto_mes(meses[k]) for k in j],
                         "nivel": nivel[i, j]})


def asof(p, t, columna_anio, valores):
    """Pega a cada fila de p el último valor de t con anio ≤ p[columna_anio] (por distrito y variable)."""
    p = p.sort_values(columna_anio)
    for v in valores:
        s = t.dropna(subset=[v]).sort_values("anio")[["ubigeo", "anio", v]]
        p = pd.merge_asof(p, s, left_on=columna_anio, right_on="anio", by="ubigeo",
                          direction="backward").drop(columns="anio")
    return p


def contexto(con, p):
    """Variables de contexto con su rezago (FR-001): anuales del año anterior, PIM del año, última elección."""
    q = lambda s: pd.read_sql(s, con)
    p["anio_previo"] = p.m // 12 - 1
    dv = q("SELECT ubigeo, anio, variable, valor FROM distrito_variable")
    ancho = dv.pivot_table(index=["ubigeo", "anio"], columns="variable", values="valor").reset_index()
    fotos = ancho[ancho.anio == 0].drop(columns="anio").dropna(axis=1, how="all")  # anio 0: foto sin serie
    p = p.merge(fotos, on="ubigeo", how="left")
    for c in ("unidades_mineras", "pasivos_mineros", "lote_explotacion", "lote_exploracion", "oleoducto_norperuano",
              "comunidades", "comunidades_pct_territorio", "reserva_indigena_pct_territorio", "via_nacional_km",
              "anp_pct_territorio", "amortiguamiento_pct_territorio", "proyectos_cartera", "minas_tajo_abierto",
              "minas_subterraneas", "conflictos_hidricos_ana", "denuncias_oefa_extractivas"):
        p[c] = p[c].fillna(0)
    minero = pd.read_sql("SELECT DISTINCT ubigeo FROM distrito_corredor WHERE corredor = 'Corredor Minero del Sur'", con)
    p["corredor_minero_sur"] = p.ubigeo.isin(minero.ubigeo).astype(float)
    serie = ancho[ancho.anio > 0]
    p = asof(p, serie, "anio_previo", ["idh", "concesiones_ha", "concesiones_metalicas_nuevas_ha", "poblacion",
                                       "perdida_bosque_ha"])
    p["perdida_bosque_ha"] = p.perdida_bosque_ha.fillna(0)  # fuera de la Amazonía no hay bosque húmedo
    # shortcut: la pobreza distrital es una sola foto (2018) y se usa para todos los años; reemplazar si sale otra.
    p = p.merge(serie[serie.anio == 2018][["ubigeo", "pobreza_sup"]], on="ubigeo", how="left")
    # shortcut: el Censo 2017 es estructural (lengua, ruralidad, servicios) y se usa también antes de 2017.
    p = p.merge(serie[serie.anio == 2017][["ubigeo", *CENSO]], on="ubigeo", how="left")
    for c in ("concesiones_ha", "concesiones_metalicas_nuevas_ha"):
        p[c] = p[c].fillna(0)
    p["anio_eleccion"] = [max(e for e in ELECCIONES if e * 12 + 10 <= m) for m in p.m]  # resultados desde noviembre
    p = p.merge(serie.rename(columns={"anio": "anio_eleccion"})[
        ["ubigeo", "anio_eleccion", "margen_victoria", "nep_listas", "participacion"]], on=["ubigeo", "anio_eleccion"],
        how="left")
    p["meses_a_eleccion"] = [min(e * 12 + 9 for e in ELECCIONES if e * 12 + 9 >= m) - m for m in p.m]
    mef = q("SELECT ubigeo, anio, pim_canon, devengado_canon FROM mef_municipal")
    p["anio"] = p.m // 12
    p = p.merge(mef[["ubigeo", "anio", "pim_canon"]], on=["ubigeo", "anio"], how="left")
    p["canon_pc"] = p.pim_canon / p.poblacion
    mef["ejecucion_canon"] = mef.devengado_canon / mef.pim_canon.where(mef.pim_canon > 0)
    p = p.merge(mef.rename(columns={"anio": "anio_previo"})[["ubigeo", "anio_previo", "ejecucion_canon"]],
                on=["ubigeo", "anio_previo"], how="left")
    en = q("SELECT ccdd, anio AS anio_previo, pobreza AS pobreza_departamento FROM enaho_departamento")
    p["ccdd"] = p.ubigeo.str[:2]
    p = p.merge(en, on=["ccdd", "anio_previo"], how="left")
    precios = q("SELECT serie, periodo, valor FROM bcrp_mensual WHERE serie IN ('PN01652XM', 'PN01654XM')")
    precios["m"] = precios.periodo.map(mes)
    precios = precios.pivot_table(index="m", columns="serie", values="valor").sort_index()
    cambio = np.log(precios).diff(12).rename(columns={"PN01652XM": "cobre_12m", "PN01654XM": "oro_12m"})
    p = p.merge(cambio, left_on="m", right_index=True, how="left")
    return p.drop(columns=["anio", "anio_previo", "anio_eleccion", "ccdd", "pim_canon", "poblacion"]).sort_values(
        ["m", "ubigeo"]).reset_index(drop=True)


GRUPOS = {
    "historia": ["fuerza_1", "fuerza_3", "fuerza_12", "fuerza_36", "protestas_12", "crisis_36", "meses_sin_fuerza",
                 "fuerza_extractiva_12", "fuerza_extractiva_36"],
    "casos": ["casos_activos", "casos_latentes", "casos_dialogo"],
    "contagio": ["fuerza_3_provincia", "fuerza_3_departamento"],
    "vias": ["via_nacional_km", "fuerza_3_corredor", "corredor_minero_sur"],
    "extraccion": ["unidades_mineras", "pasivos_mineros", "lote_explotacion", "lote_exploracion",
                   "oleoducto_norperuano", "concesiones_ha", "concesiones_metalicas_nuevas_ha", "proyectos_cartera",
                   "certificaciones_12", "eia_36",
                   "minas_tajo_abierto", "minas_subterraneas"],
    "territorio": ["comunidades", "comunidades_pct_territorio", "reserva_indigena_pct_territorio",
                   "lengua_indigena", "autoidentificacion_indigena", "rural", "anp_pct_territorio",
                   "amortiguamiento_pct_territorio", "estres_hidrico", "emergencias_3", "perdida_bosque_ha", "ronda_campesina"],
    "economia": ["cobre_12m", "oro_12m", "canon_pc", "ejecucion_canon"],
    "desarrollo": ["idh", "pobreza_sup", "pobreza_departamento", "sin_agua_red", "sin_electricidad"],
    "gobernanza": ["oficina_ambiental", "atiende_denuncias_ambientales", "participacion_formas", "personal_municipal"],
    "politica": ["meses_a_eleccion", "margen_victoria", "nep_listas", "participacion"],
    "zona": ["zona_fuerza_1", "zona_fuerza_3", "zona_fuerza_12", "zona_fuerza_36", "zona_fuerza_extractiva_12",
             "zona_fuerza_extractiva_36", "zona_protestas_12", "zona_casos_activos", "zona_casos_dialogo"],
    "cambios": ["casos_nuevos_3", "casos_activados_3", "dialogo_roto_3", "zona_casos_nuevos_3",
                "zona_casos_activados_3", "zona_dialogo_roto_3", "zona_certificaciones_3",
                "zona_protestas_sin_fuerza_3", "zona_alza", "zona_emergencias_3"],
    "calendario": ["mes_del_anio"],
    "gobierno": ["zona_vacancias_12", "zona_revocatorias_24", "zona_control_12", "inversion_pct_gasto",
                 "obras_vs_anio_previo"],
    "anomalias": ["anom_" + c for c in ANOMALIAS],
}
VARIABLES = [v for g in GRUPOS.values() for v in g]
# Fuera del modelo por fuga: las denuncias OEFA (2018-2024) y los conflictos ANA (sin fecha) se solapan con la prueba.
# Fotos recientes que sí entran (anteriores a la prueba, pero posteriores a casi todo el entrenamiento); el chequeo
# "sin_fotos" mide cuánto dependen de ellas los aciertos.
FOTOS = ["oficina_ambiental", "atiende_denuncias_ambientales", "participacion_formas", "personal_municipal",
         "ronda_campesina", "proyectos_cartera"]


MIEMBROS = ("lasso", "bosque", "gradient_boosting")  # el ensamble los promedia (como en 14.388, ML for wage prediction)


class SinVacias:
    """Las variables que aún no existían en la ventana de entrenamiento (IDH desde 2017, canon por persona…) quedan
    toda en NaN, y el boosting se cae al buscar sus cortes: se ponen en 0 (sin información) en el ajuste y al predecir."""
    def fit(self, x, y=None):
        self.vacias = np.isnan(np.asarray(x, dtype=float)).all(axis=0)
        return self

    def transform(self, x):
        x = np.array(x, dtype=float)
        x[:, self.vacias] = 0.0
        return x

    def get_params(self, deep=True):
        return {}

    def set_params(self, **kw):
        return self


def modelos():
    """La competencia de modelos de los cursos del profesor (14.388 y MGTECON 634, en github.com/d2cml-ai):
    lineales con y sin penalización, árbol podado, bosque y boosting; todos de scikit-learn."""
    from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import FunctionTransformer, StandardScaler
    from sklearn.tree import DecisionTreeClassifier
    lineal = lambda **kw: make_pipeline(FunctionTransformer(lambda x: np.sign(x) * np.log1p(np.abs(x))),
                                        SimpleImputer(strategy="median"), StandardScaler(),
                                        LogisticRegression(max_iter=2000, **kw))
    return {"logistica": lineal(),
            "lasso": lineal(l1_ratio=1.0, C=0.05, solver="saga"),
            "arbol": DecisionTreeClassifier(max_depth=4, min_samples_leaf=500, random_state=0),
            "bosque": RandomForestClassifier(n_estimators=200, min_samples_leaf=50, max_features=0.3, n_jobs=2,  # -1 copia el panel por núcleo: sin memoria en la laptop
                                             random_state=0),
            "gradient_boosting": make_pipeline(SinVacias(), HistGradientBoostingClassifier(
                max_iter=300, learning_rate=0.05, min_samples_leaf=200, l2_regularization=1.0, random_state=0))}


# Punto 6: cada modelo prueba 3 valores de su parámetro principal; gana el de mejor precisión en el top 20 de un
# bloque de validación (objetivos 2021-2023) que no toca la prueba (2024+).
GRILLA = {"logistica": [{}], "lasso": [{"logisticregression__C": c} for c in (0.01, 0.05, 0.2)],
          "arbol": [{"max_depth": d} for d in (3, 4, 6)],
          "bosque": [{"min_samples_leaf": h} for h in (20, 50, 150)],
          "gradient_boosting": [{"histgradientboostingclassifier__learning_rate": a} for a in (0.02, 0.05, 0.1)]}
VALIDA = 2021 * 12
AFINADO = {}  # (objetivo, modelo) -> parámetros elegidos


def modelo(nombre, objetivo):
    return modelos()[nombre].set_params(**AFINADO.get((objetivo, nombre), {}))


def afinar(entrena, objetivo):
    """Elige los parámetros de GRILLA con validación temporal dentro del entrenamiento (objetivos 2021-2023) y
    devuelve (bloque de validación, {modelo: predicciones}) para elegir el ganador y calibrar sin tocar la prueba."""
    a, b = entrena[entrena.m + HORIZONTE < VALIDA], entrena[entrena.m >= VALIDA - 1]
    yb, disj = b[objetivo].to_numpy(), objetivo.startswith("z")
    pred = {}
    for nombre, opciones in GRILLA.items():
        ps = [modelos()[nombre].set_params(**o).fit(a[VARIABLES], a[objetivo]).predict_proba(b[VARIABLES])[:, 1]
              for o in opciones]
        nota = [precision_top(b, s, yb, disjuntas=disj) for s in ps]
        k = int(np.argmax(nota))
        AFINADO[objetivo, nombre], pred[nombre] = opciones[k], ps[k]
        print(f"  {objetivo}: {nombre} {AFINADO[objetivo, nombre]} (validación {nota[k]:.3f})", flush=True)
    pred["ensamble"] = np.mean([pred[n] for n in MIEMBROS], axis=0)
    return b, pred


class Ensamble:
    """Promedio de probabilidades de MIEMBROS."""
    def __init__(self, objetivo):
        self.objetivo = objetivo

    def fit(self, x, y):
        self.m = [modelo(n, self.objetivo).fit(x, y) for n in MIEMBROS]
        return self

    def predict_proba(self, x):
        return np.mean([m.predict_proba(x) for m in self.m], axis=0)


def ajustar(nombre, objetivo, x, y):
    return (Ensamble(objetivo) if nombre == "ensamble" else modelo(nombre, objetivo)).fit(x, y)


def ingenuo(p, objetivo="y_fuerza"):
    """La regla a vencer: hubo medida de fuerza el último mes (en la zona, si el objetivo es de zona); desempata la
    historia de 12 meses."""
    z = "zona_" if objetivo.startswith("z") else ""
    return (p[z + "fuerza_1"] > 0) * 1000 + p[z + "fuerza_12"]


def por_mes(p, score, y, k=20, solo_nuevos=False, historia="fuerza_12", disjuntas=False, sin_capitales=False):
    """Fracción de aciertos entre los k distritos con mayor score, mes a mes. Con `disjuntas`, el top k solo admite
    zonas que no comparten distritos con otra ya elegida: un mismo bloqueo no se cuenta como varios aciertos."""
    t = p[["ubigeo", "m"] + ([historia] if solo_nuevos else [])].assign(s=score, y=y)
    if solo_nuevos:
        t = t[t[historia] == 0]
    if sin_capitales:
        t = t[~t.ubigeo.str.endswith("01")]  # la EGPP pone la capital cuando no sabe el distrito

    def top(g):
        g = g.nlargest(len(g) if disjuntas else k, "s")
        if not disjuntas:
            return g.y.mean()
        W, idx, cubierto, elegidos = VECINDAD["W"], VECINDAD["idx"], np.zeros(len(VECINDAD["idx"]), bool), []
        for u, yy in zip(g.ubigeo, g.y):
            zona = W[idx[u]]
            if not (zona & cubierto).any():
                cubierto |= zona
                elegidos.append(yy)
                if len(elegidos) == k:
                    break
        return np.mean(elegidos)
    return t.groupby("m").apply(top, include_groups=False)


def precision_top(p, score, y, k=20, **kw):
    """Promedio por mes de `por_mes`."""
    return float(por_mes(p, score, y, k, **kw).mean())


def intervalo(serie, n=1000, semilla=0):
    """Intervalo del 90% del promedio mensual, remuestreando meses (bootstrap)."""
    r = np.random.default_rng(semilla)
    x = serie.to_numpy()
    medias = x[r.integers(0, len(x), (n, len(x)))].mean(axis=1)
    return float(np.quantile(medias, 0.05)), float(np.quantile(medias, 0.95))


def captura(p, score, y, q=0.10):
    """Fracción de los eventos que caen en el 10% de filas con mayor score de cada mes (lo que ve quien revisa solo
    ese 10%)."""
    t = p[["m"]].assign(s=score, y=y)
    t["arriba"] = t.groupby("m").s.rank(ascending=False, pct=True, method="first") <= q
    return float(t[t.arriba].y.sum() / max(t.y.sum(), 1))


def evaluar(p, objetivo):
    """Entrena con objetivos hasta 2023-12 y mide en 2024+ (FR-002). Devuelve las métricas, el mejor modelo y su
    interpretación en prueba."""
    from sklearn.metrics import average_precision_score, brier_score_loss
    p = p[p[objetivo].notna()]
    entrena, prueba = p[p.m + HORIZONTE < PRUEBA], p[p.m >= PRUEBA - 1]  # objetivo de prueba: desde enero 2024
    y = prueba[objetivo].to_numpy()
    z = objetivo.startswith("z")
    externa = ("vz_acled" if z else "v_acled") + ("_extractivo" if objetivo.endswith("extractivo") else "")  # ACLED
    historia = "zona_fuerza_12" if z else "fuerza_12"
    filas, puntajes, ajustados = [], {"ingenuo": ingenuo(prueba, objetivo).to_numpy(float)}, {}
    bloque, validacion = afinar(entrena, objetivo)
    for n in modelos():
        ajustados[n] = modelo(n, objetivo).fit(entrena[VARIABLES], entrena[objetivo])
        puntajes[n] = ajustados[n].predict_proba(prueba[VARIABLES])[:, 1]
        print(f"  {objetivo}: {n} listo", flush=True)
    puntajes["ensamble"] = np.mean([puntajes[n] for n in MIEMBROS], axis=0)
    nota_val = {n: precision_top(bloque, s, bloque[objetivo].to_numpy(), disjuntas=z) for n, s in validacion.items()}
    mejor = max(nota_val, key=nota_val.get)  # se elige con la validación 2021-2023, no con la prueba
    calibrar(objetivo, validacion[mejor], bloque[objetivo].to_numpy())
    for n, s in puntajes.items():
        mensual = por_mes(prueba, s, y, disjuntas=z)
        li, ls = intervalo(mensual)
        m = {"pr_auc": average_precision_score(y, s), "precision_top20": float(mensual.mean()),
             "precision_top20_li": li, "precision_top20_ls": ls, "validacion_top20": nota_val.get(n, np.nan),
             "precision_top20_nuevos": precision_top(prueba, s, y, solo_nuevos=True, historia=historia, disjuntas=z),
             "precision_top20_sin_capitales": precision_top(prueba, s, y, disjuntas=z, sin_capitales=True),
             "captura_top10pct": captura(prueba, s, y),
             "brier": brier_score_loss(y, s) if n != "ingenuo" else np.nan,
             "tasa_base": y.mean(), "filas_prueba": len(y), "filas_entrena": len(entrena)}
        ok = prueba[externa].notna().to_numpy()
        ya = prueba[externa].to_numpy()[ok]
        m |= {"pr_auc_acled": average_precision_score(ya, s[ok]), "tasa_base_acled": ya.mean(),
              "precision_top20_acled": precision_top(prueba[ok], s[ok], ya, disjuntas=z),
              "captura_top10pct_acled": captura(prueba[ok], s[ok], ya)}
        filas += [(n, objetivo, k, float(v)) for k, v in m.items()]
    metricas = pd.DataFrame(filas, columns=["modelo", "objetivo", "metrica", "valor"])
    # shortcut: el calibrador se ajusta con un modelo entrenado hasta 2020 y se aplica a uno entrenado hasta 2023; si la
    # tabla de deciles muestra desvío en la prueba, recalibrar con validación cruzada temporal.
    CALIBRACION.append(deciles(objetivo, puntajes[mejor], y))  # medida en la prueba, ajustada en validación
    if z:  # puntajes de prueba por zona: la vista por empresa (tremor.empresas) reconstruye cómo le habría ido
        for n in (mejor, "ingenuo"):
            t = prueba[["ubigeo", "m"]].assign(objetivo=objetivo, modelo=n, puntaje=puntajes[n], y=y)
            t["pct"] = t.groupby("m").puntaje.rank(ascending=False, pct=True, method="first")
            PREDICCION.append(t)
    respaldo(p, objetivo, mejor, metricas)
    return metricas, mejor, interpretar(ajustados.get(mejor, ajustados["gradient_boosting"]), prueba,
                                        puntajes[mejor], objetivo)


CALIBRADOR, CALIBRACION, PREDICCION = {}, [], []


def calibrar(objetivo, s, y):
    """Los bosques encogen las probabilidades: una regresión isotónica ajustada en la validación (2021-2023) las lleva
    a frecuencias observadas; la alerta las usa así y la tabla por decil se mide en la prueba (2024+)."""
    from sklearn.isotonic import IsotonicRegression
    CALIBRADOR[objetivo] = IsotonicRegression(out_of_bounds="clip", y_min=0, y_max=1).fit(s, y)


def deciles(objetivo, s, y):
    d = pd.DataFrame({"s": s, "y": y, "c": CALIBRADOR[objetivo].predict(s)})
    d["decil"] = pd.qcut(d.s.rank(method="first"), 10, labels=False) + 1
    return d.groupby("decil").agg(predicha=("s", "mean"), calibrada=("c", "mean"), observada=("y", "mean"),
                                  filas=("y", "size")).reset_index().assign(objetivo=objetivo)


VENTANAS = ((2016, 2018), (2018, 2020), (2020, 2022))  # además de la prueba principal (2024+)
RESPALDO = []


def respaldo(p, objetivo, mejor, metricas):
    """Robustez: el ganador (con sus parámetros) contra el ingenuo en ventanas anteriores, cada una entrenada solo con
    lo previo; y en la prueba principal, el mismo modelo sin las fotos recientes (FOTOS)."""
    z = objetivo.startswith("z")
    for a0, a1 in VENTANAS:
        ent, pru = p[p.m + HORIZONTE < a0 * 12], p[(p.m >= a0 * 12 - 1) & (p.m < a1 * 12 - 1)]
        y = pru[objetivo].to_numpy()
        for n, s in (("ingenuo", ingenuo(pru, objetivo).to_numpy(float)),
                     (mejor, ajustar(mejor, objetivo, ent[VARIABLES], ent[objetivo]).predict_proba(pru[VARIABLES])[:, 1])):
            mensual = por_mes(pru, s, y, disjuntas=z)
            RESPALDO.append((objetivo, f"{a0}-{a1 - 1}", n, float(mensual.mean()), *intervalo(mensual),
                             captura(pru, s, y), float(y.mean())))
        print(f"  {objetivo}: ventana {a0}-{a1 - 1} lista", flush=True)
    v = metricas.pivot_table(index="modelo", columns="metrica", values="valor")
    for n in ("ingenuo", mejor):
        RESPALDO.append((objetivo, "2024-2026", n, v.loc[n, "precision_top20"], v.loc[n, "precision_top20_li"],
                         v.loc[n, "precision_top20_ls"], v.loc[n, "captura_top10pct"], v.loc[n, "tasa_base"]))
    sin = [c for c in VARIABLES if c not in FOTOS]
    ent, pru = p[p.m + HORIZONTE < PRUEBA], p[p.m >= PRUEBA - 1]
    y = pru[objetivo].to_numpy()
    s = ajustar(mejor, objetivo, ent[sin], ent[objetivo]).predict_proba(pru[sin])[:, 1]
    mensual = por_mes(pru, s, y, disjuntas=z)
    RESPALDO.append((objetivo, "2024-2026 sin fotos", mejor, float(mensual.mean()), *intervalo(mensual),
                     captura(pru, s, y), float(y.mean())))


def interpretar(mdl, prueba, s, objetivo):
    """Como en MGTECON 634: importancia por permutación (si gana el ensamble, la del boosting) y perfil promedio de
    los distritos por quintil de riesgo predicho."""
    from sklearn.inspection import permutation_importance
    muestra = prueba.sample(min(len(prueba), 40000), random_state=0)
    imp = permutation_importance(mdl, muestra[VARIABLES], muestra[objetivo], scoring="average_precision",
                                 n_repeats=3, random_state=0)
    importancia = pd.DataFrame({"objetivo": objetivo, "variable": VARIABLES, "importancia": imp.importances_mean,
                                "grupo": [g for g, cs in GRUPOS.items() for _ in cs]})
    q = pd.qcut(pd.Series(s).rank(method="first"), 5, labels=False).to_numpy() + 1
    perfil = prueba[VARIABLES + [objetivo]].assign(quintil=q).groupby("quintil").mean().T
    perfil.columns = [f"q{c}" for c in perfil.columns]
    return (importancia.sort_values("importancia", ascending=False),
            perfil.reset_index(names="variable").assign(objetivo=objetivo))


def razones(mdl, x, medianas):
    """Oclusión por grupo (FR-003): cuánto baja la probabilidad si el grupo toma su valor típico."""
    base = mdl.predict_proba(x[VARIABLES])[:, 1]
    caida = {}
    for g, cols in GRUPOS.items():
        z = x[VARIABLES].copy()
        for c in cols:
            z[c] = medianas[c]
        caida[g] = base - mdl.predict_proba(z)[:, 1]
    return base, pd.DataFrame(caida, index=x.index)


def frase(g, r):
    pct = lambda v: "s/d" if pd.isna(v) else f"{v:.0%}"
    if g == "historia":
        x = f", {r.fuerza_extractiva_36:.0f} por minería, hidrocarburos o ambiente" if r.fuerza_extractiva_36 else ""
        return f"{r.fuerza_12:.0f} medidas de fuerza en 12 meses ({r.fuerza_36:.0f} en 3 años{x})"
    if g == "casos":
        return f"{r.casos_activos:.0f} casos activos en la Defensoría ({r.casos_dialogo:.0f} con diálogo)"
    if g == "zona":
        x = f", {r.zona_fuerza_extractiva_36:.0f} por minería, hidrocarburos o ambiente" if r.zona_fuerza_extractiva_36 else ""
        return (f"en la zona (distrito y vecinos): {r.zona_fuerza_12:.0f} medidas de fuerza en 12 meses "
                f"({r.zona_fuerza_36:.0f} en 3 años{x}); {r.zona_casos_activos:.0f} casos activos")
    if g == "contagio":
        return f"{r.fuerza_3_provincia:.0f} medidas de fuerza en el resto de la provincia en 3 meses"
    if g == "extraccion":
        partes = [f"{r[c]:.0f} {t}" for c, t in (("unidades_mineras", "unidades mineras"),
                                                 ("minas_tajo_abierto", "a tajo abierto"),
                                                 ("proyectos_cartera", "proyectos mineros en cartera"),
                                                 ("pasivos_mineros", "pasivos mineros")) if r[c] > 0]
        partes += [t for c, t in (("lote_explotacion", "lote petrolero en explotación"),
                                  ("lote_exploracion", "lote en exploración"),
                                  ("oleoducto_norperuano", "Oleoducto Norperuano")) if r[c] > 0]
        if r.eia_36 > 0:
            partes.append(f"{r.eia_36:.0f} EIA aprobados en 3 años (SENACE)")
        elif r.certificaciones_12 > 0:
            partes.append(f"{r.certificaciones_12:.0f} certificaciones ambientales en 12 meses (SENACE)")
        if r.concesiones_metalicas_nuevas_ha > 0:
            partes.append(f"{r.concesiones_metalicas_nuevas_ha:,.0f} ha de concesiones metálicas nuevas")
        return "; ".join(partes) or "concesiones mineras en el distrito"
    if g == "economia":
        canon = "" if pd.isna(r.canon_pc) else f"; canon S/ {r.canon_pc:,.0f} por habitante"
        return f"cobre {r.cobre_12m:+.0%} y oro {r.oro_12m:+.0%} en 12 meses{canon}"
    if g == "desarrollo":
        idh = "s/d" if pd.isna(r.idh) else f"{r.idh:.2f}"
        return (f"IDH {idh}; pobreza hasta {pct(r.pobreza_sup / 100 if pd.notna(r.pobreza_sup) else np.nan)}; "
                f"{pct(r.sin_agua_red)} de viviendas sin agua de red")
    if g == "territorio":
        partes = []
        if r.comunidades:
            partes.append(f"{r.comunidades:.0f} comunidades campesinas o nativas en el "
                          f"{pct(r.comunidades_pct_territorio)} del territorio")
        if r.reserva_indigena_pct_territorio:
            partes.append("reserva para pueblos en aislamiento")
        if r.anp_pct_territorio or r.amortiguamiento_pct_territorio:
            partes.append(f"{pct(r.anp_pct_territorio + r.amortiguamiento_pct_territorio)} en área natural protegida "
                          "o su zona de amortiguamiento")
        if r.ronda_campesina == 1:
            partes.append("rondas campesinas")
        if r.perdida_bosque_ha >= 100:
            partes.append(f"{r.perdida_bosque_ha:,.0f} ha de bosque perdidas el año anterior")
        if r.emergencias_3 > 0:
            partes.append(f"{r.emergencias_3:.0f} emergencias por lluvias, huaicos o sequía en 3 meses")
        if r.estres_hidrico >= 3:
            partes.append("escasez de agua en su cuenca (ANA)")
        partes.append(f"{pct(r.lengua_indigena)} con lengua materna indígena; {pct(r.rural)} rural")
        return "; ".join(partes)
    if g == "gobernanza":
        partes = [f"municipalidad con {r.personal_municipal:.0f} trabajadores"
                  if pd.notna(r.personal_municipal) else "personal municipal s/d"]
        partes.append("sin oficina ambiental" if r.oficina_ambiental == 0 else "con oficina ambiental")
        partes.append(f"{r.participacion_formas:.0f} formas de participación ciudadana (RENAMU 2023)")
        return "; ".join(partes)
    if g in ("cambios", "calendario", "anomalias", "gobierno"):
        return frase_cambio(g, r, r, True).removeprefix("sube: ")
    if g == "vias":
        tramo = "en el Corredor Minero del Sur; " if r.corredor_minero_sur else ""
        return (f"{tramo}{r.via_nacional_km:.0f} km de vía nacional; {r.fuerza_3_corredor:.0f} medidas de fuerza "
                f"en el mismo corredor en 3 meses")
    # Las capitales de provincia no tienen elección distrital (las gobierna el alcalde provincial): sin margen.
    margen = "" if pd.isna(r.margen_victoria) else f"; la última se ganó por {pct(r.margen_victoria)}"
    return f"{eleccion(r)}{margen}"


def este_mes(mdl, p, x, calibrador, meses=12):
    """La alerta del mes frente a lo normal en la misma zona: `normal` es la probabilidad media de sus últimos 12 meses
    y las razones del cambio salen de poner cada grupo de variables en su promedio de esos 12 meses (oclusión contra
    la propia zona, no contra el país): lo que hoy está distinto de lo habitual allí."""
    ultimo = p.m.max()
    previo = p[(p.m > ultimo - meses) & (p.m < ultimo) & (p.operacion == 1)]
    previo = previo.assign(prob=calibrador.predict(mdl.predict_proba(previo[VARIABLES])[:, 1]))
    normal = previo.groupby("ubigeo")[["prob", *VARIABLES]].mean(numeric_only=True)
    x = x[x.operacion == 1]
    habitual = normal.reindex(x.index)[VARIABLES].fillna(x[VARIABLES])
    prob, caida = razones(mdl, x, habitual)
    prob = calibrador.predict(prob)
    salida = pd.DataFrame({"normal_zona_1m": normal.prob.reindex(x.index), "cambio_zona_1m": prob - normal.prob.reindex(x.index)},
                          index=x.index)
    salida["razones_cambio_1m"] = [
        " · ".join(frase_cambio(g, x.loc[u], habitual.loc[u], caida.loc[u, g] > 0)
                   for g in caida.loc[u].drop("economia").abs().nlargest(3).index if abs(caida.loc[u, g]) >= 0.005)
        for u in x.index]
    return salida


MESES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
         "noviembre", "diciembre")


def eleccion(r, adelanto=2):
    """La elección municipal vista desde el mes de la alerta (t+2), no desde el último dato. Después de la elección
    el riesgo sube: de diciembre a febrero de los años electorales hubo el doble de paros que en otros años
    (disputas de resultados, transferencia, nuevas autoridades desde enero)."""
    m = int(r.m) + adelanto
    desde = m - max(e * 12 + 9 for e in ELECCIONES if e * 12 + 9 <= m)
    hasta = min(e * 12 + 9 for e in ELECCIONES if e * 12 + 9 >= m) - m
    if desde == 0:
        return "es el mes de la elección municipal"
    if desde <= 5:
        return "pasó la elección municipal y los meses que siguen suelen traer el doble de paros"
    return f"{'falta 1 mes' if hasta == 1 else f'faltan {hasta} meses'} para la elección municipal"


def frase_cambio(g, r, n, sube):
    """Una razón del cambio del mes: el valor de hoy frente al habitual de la zona; `sube` dice hacia dónde empuja."""
    signo = "sube" if sube else "baja"
    vs = lambda hoy, antes, texto: f"{texto}: {hoy:.0f} (lo habitual, {antes:.0f})"
    if g in ("zona", "historia"):
        c = "zona_fuerza_3" if g == "zona" else "fuerza_3"
        return f"{signo}: " + vs(r[c], n[c], "medidas de fuerza en la zona en los últimos 3 meses")
    if g == "casos":
        return f"{signo}: " + vs(r.zona_casos_activos, n.zona_casos_activos, "casos activos en la Defensoría en la zona")
    if g == "cambios":
        distinto = lambda c: (r[c] > 0) if n is r else abs(r[c] - n[c]) >= 0.5  # en frase(): lo que hay
        partes = [f"{texto}: {r[c]:.0f}" + ("" if n is r else f" (lo habitual, {n[c]:.0f})") for c, texto in (
            ("zona_casos_nuevos_3", "casos nuevos en la Defensoría"),
            ("zona_casos_activados_3", "casos que pasaron de latentes a activos"),
            ("zona_dialogo_roto_3", "casos que perdieron su mesa de diálogo"),
            ("zona_certificaciones_3", "certificaciones ambientales aprobadas por SENACE"),
            ("zona_protestas_sin_fuerza_3", "marchas o plantones sin paro"),
            ("zona_emergencias_3", "emergencias por lluvias, huaicos o sequía")) if distinto(c)]
        return f"{signo}: " + ("; ".join(partes) + ", en la zona en los últimos 3 meses" if partes
                               else "sin casos nuevos, activados ni diálogos rotos en la zona en 3 meses")
    if g == "anomalias":
        nivel = lambda z: "muy por encima" if z >= 2 else "por encima" if z >= 1 else "muy por debajo" if z <= -2 else "por debajo"
        partes = [f"{texto} {nivel(r['anom_' + c])} de lo habitual en la zona" for c, texto in ANOMALIAS.items()
                  if pd.notna(r["anom_" + c]) and abs(r["anom_" + c]) >= 1 and (r["anom_" + c] > 0) == sube]
        return f"{signo}: " + ("; ".join(partes) or "señales cerca de lo habitual en la zona")
    if g == "contagio":
        return f"{signo}: " + vs(r.fuerza_3_provincia, n.fuerza_3_provincia, "medidas de fuerza en el resto de la provincia en 3 meses")
    if g == "vias":
        return f"{signo}: " + vs(r.fuerza_3_corredor, n.fuerza_3_corredor, "medidas de fuerza en su corredor vial en 3 meses")
    if g == "gobierno":
        partes = [p for p in (
            f"{r.zona_vacancias_12:.0f} pedidos de vacancia o reemplazos de autoridades en la zona en 12 meses" if r.zona_vacancias_12 > 0 else "",
            f"{r.zona_revocatorias_24:.0f} consultas de revocatoria en la zona en 2 años" if r.zona_revocatorias_24 > 0 else "",
            f"{r.zona_control_12:.0f} informes de la Contraloría con responsabilidad en la zona en 12 meses" if r.zona_control_12 > 0 else "",
            f"el gasto en obras del municipio va {r.obras_vs_anio_previo:+.0%} frente al año anterior" if pd.notna(r.obras_vs_anio_previo) else "") if p]
        return f"{signo}: " + ("; ".join(partes) or "sin vacancias, revocatorias ni informes de control en la zona")
    if g == "calendario":
        return f"{signo}: en {MESES[int(r.mes_del_anio) % 12]} suele haber {'más' if sube else 'menos'} protestas"
    if g == "economia":
        return f"{signo}: cobre {r.cobre_12m:+.0%} en 12 meses"
    if g == "politica":
        return f"{signo}: {eleccion(r)}"
    return f"{signo}: " + frase(g, r)


def prensa_en_vivo(con, distritos, dias=30):
    """Capa en vivo de la prensa (diarios, radios, TV, Facebook): eventos de los últimos `dias` o anunciados a futuro.
    No entra al modelo (su historia empieza en 2026): sube el distrito a "alerta inmediata" si hay una medida de
    fuerza anunciada u ocurriendo en el mismo distrito o provincia; si solo se sabe el departamento, queda como señal."""
    from datetime import date, timedelta
    desde = (date.today() - timedelta(days=dias)).isoformat()
    ev = pd.read_sql("SELECT e.id, e.estado, COALESCE(e.fecha_evento, e.fecha_anuncio) AS fecha, e.ubigeo, e.accion, "
                     "e.actor, e.reclamo, MIN(n.enlace) AS enlace FROM evento_prensa e "
                     "LEFT JOIN evento_nota en ON en.evento_id = e.id LEFT JOIN nota n ON n.id = en.nota_id "
                     "WHERE COALESCE(e.fecha_evento, e.fecha_anuncio) >= ? AND e.ubigeo IS NOT NULL "
                     "GROUP BY e.id ORDER BY fecha DESC", con, params=(desde,))
    ev = ev.fillna({"actor": "s/d", "reclamo": "", "accion": ""})
    ev["fuerza"] = ev.accion.map(nivel_accion) >= 3
    salida = []
    for u in distritos:
        mios = ev[[u.startswith(x) for x in ev.ubigeo]]
        if mios.empty:
            continue
        cerca = mios[mios.ubigeo.str.len() >= 4]
        salida.append({"ubigeo": u, "alerta_inmediata": int(bool((cerca.fuerza).any())),
                       "senal_prensa": " | ".join(
                           f"{r.fecha} {r.estado}: {r.accion} ({r.actor or 's/d'}"
                           f"{', ' + r.reclamo if r.reclamo else ''}) en {nombre(r.ubigeo) or r.ubigeo}"
                           for r in mios.head(3).itertuples()),
                       "enlace_prensa": mios.enlace.dropna().iloc[0] if mios.enlace.notna().any() else None})
    return pd.DataFrame(salida, columns=["ubigeo", "alerta_inmediata", "senal_prensa", "enlace_prensa"]).set_index(
        "ubigeo")


def alerta(con, p, mejor):
    """Reentrena con todos los meses con objetivo conocido y predice desde el último mes."""
    ultimo = p.m.max()
    x = p[p.m == ultimo].set_index("ubigeo")
    salida = pd.DataFrame(index=x.index)
    for objetivo, col in (("y_fuerza", "prob"), ("y_extractivo", "prob_extractivo"), ("y_crisis", "prob_crisis"),
                          ("z_fuerza", "prob_zona"), ("z_extractivo", "prob_zona_extractivo"),
                          ("z1_fuerza", "prob_zona_1m"), ("z1_brote", "prob_brote")):
        t = p[p[objetivo].notna()]
        mdl = ajustar(mejor[objetivo], objetivo, t[VARIABLES], t[objetivo])
        prob, caida = razones(mdl, x, t[VARIABLES].median())
        salida[col] = CALIBRADOR[objetivo].predict(prob)
        salida[col.replace("prob", "puntaje")] = prob  # sin calibrar: ordena sin empates
        if objetivo != "y_crisis":
            salida[col.replace("prob", "razones")] = [
                " · ".join(frase(g, x.loc[u]) for g in caida.loc[u].nlargest(3).index if caida.loc[u, g] > 0)
                for u in x.index]
        if objetivo == "z1_fuerza":
            salida = salida.join(este_mes(mdl, p, x, CALIBRADOR[objetivo]))
    for c in ("prob_zona", "puntaje_zona", "razones_zona", "prob_zona_extractivo", "puntaje_zona_extractivo",
              "razones_zona_extractivo", "prob_zona_1m", "puntaje_zona_1m", "razones_zona_1m", "normal_zona_1m",
              "cambio_zona_1m", "razones_cambio_1m", "prob_brote", "puntaje_brote", "razones_brote"):
        salida.loc[x.operacion == 0, c] = np.nan  # la alerta de zona es solo para distritos con operación
    salida["puesto_zona"] = salida.puntaje_zona.rank(ascending=False, method="first")
    salida["puesto_zona_extractivo"] = salida.puntaje_zona_extractivo.rank(ascending=False, method="first")
    salida["puesto"] = salida.puntaje.rank(ascending=False, method="first").astype(int)
    salida["puesto_extractivo"] = salida.puntaje_extractivo.rank(ascending=False, method="first").astype(int)
    salida["nivel_actual"] = x.nivel.astype(int)
    salida["operacion_extractiva"] = (x[["unidades_mineras", "lote_explotacion", "lote_exploracion",
                                         "oleoducto_norperuano"]].sum(axis=1) > 0).astype(int)
    salida["lugar"] = [" / ".join(filter(None, (nombre(u[:2]), nombre(u[:4]), nombre(u)))) for u in x.index]
    corr = pd.read_sql("SELECT ubigeo, corredor FROM distrito_corredor WHERE corredor NOT LIKE 'AL%'", con)
    salida["corredores"] = corr.groupby("ubigeo").corredor.agg(lambda s: ", ".join(sorted(s))).reindex(salida.index)
    salida = salida.join(prensa_en_vivo(con, list(salida.index)))
    from tremor.animo import senal
    salida["animo_proyectos"] = [senal(con).get(u[:4]) for u in salida.index]  # radio y prensa, 7 días
    salida["alerta_inmediata"] = salida.alerta_inmediata.fillna(0).astype(int)
    salida["mes_base"] = texto_mes(ultimo)
    salida["ventana"] = f"{texto_mes(ultimo + 1)} a {texto_mes(ultimo + HORIZONTE)}"
    salida["ventana_1m"] = texto_mes(ultimo + 2)
    salida["zona_tranquila"] = (x.zona_fuerza_3 == 0).astype(int)  # prob_brote solo tiene sentido en estas
    salida.loc[salida.zona_tranquila == 0, ["prob_brote", "razones_brote"]] = np.nan
    salida["modelo"], salida["modelo_extractivo"] = mejor["y_fuerza"], mejor["y_extractivo"]
    salida["creado"] = ahora()
    return salida.reset_index().sort_values("puesto_extractivo")


BITACORA = ["mes_base", "ventana_1m", "ubigeo", "prob_zona_1m", "normal_zona_1m", "cambio_zona_1m", "prob_brote",
            "zona_tranquila", "razones_cambio_1m", "creado"]


def bitacora(con, a):
    """Guarda la alerta del mes tal como salió (una vez por mes base), para medir después, con datos que el modelo no
    vio, si lo que avisó pasó. Es el registro que no se puede retocar: lo que se le mostraría a un cliente."""
    a = a[a.prob_zona_1m.notna()][[c for c in BITACORA if c in a.columns]]
    try:
        hechos = set(pd.read_sql("SELECT DISTINCT mes_base FROM alerta_bitacora", con).mes_base)
    except Exception:
        hechos = set()
    a = a[~a.mes_base.isin(hechos)]
    if len(a):
        a.to_sql("alerta_bitacora", con, if_exists="append", index=False)
        con.commit()
    return len(a)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    con = conectar()
    p, niveles = panel(con)
    print(f"panel: {len(p):,} filas, {p.ubigeo.nunique()} distritos, {texto_mes(p.m.min())} a {texto_mes(p.m.max())}; "
          + ", ".join(f"{o} {p[o].mean():.2%}" for o in OBJETIVOS))
    metricas, importancia, perfil, mejor = [], [], [], {}
    for o in OBJETIVOS:
        m, mejor[o], (imp, per) = evaluar(p, o)
        metricas.append(m), importancia.append(imp), perfil.append(per)
    metricas = pd.concat(metricas)
    tabla = metricas.pivot_table(index=["objetivo", "modelo"], columns="metrica", values="valor")
    print(tabla[["validacion_top20", "precision_top20", "precision_top20_li", "precision_top20_ls",
                 "precision_top20_nuevos", "precision_top20_sin_capitales", "captura_top10pct", "tasa_base",
                 "precision_top20_acled", "tasa_base_acled"]].round(3).to_string())
    print("mejor:", mejor)
    a = alerta(con, p, mejor)
    print(f"bitácora: {bitacora(con, a)} zonas guardadas")
    metricas["horizonte"], metricas["creado"] = HORIZONTE, ahora()
    salidas = {"nivel_mes": niveles, "modelo_metrica": metricas, "modelo_importancia": pd.concat(importancia),
               "modelo_perfil": pd.concat(perfil), "alerta": a, "modelo_calibracion": pd.concat(CALIBRACION),
               "modelo_respaldo": pd.DataFrame(RESPALDO, columns=["objetivo", "ventana", "modelo", "precision_top20",
                                                                  "li_90", "ls_90", "captura_top10pct", "tasa_base"]),
               "modelo_prediccion": pd.concat(PREDICCION),
               "modelo_parametros": pd.DataFrame([(o, n, str(v)) for (o, n), v in AFINADO.items()],
                                                 columns=["objetivo", "modelo", "parametros"])}
    (DATOS / "exportes").mkdir(parents=True, exist_ok=True)
    for tabla_nombre, df in salidas.items():
        df.to_sql(tabla_nombre, con, if_exists="replace", index=False)
        df.to_csv(DATOS / "exportes" / f"{tabla_nombre}.csv", index=False)
    print(salidas["modelo_respaldo"].round(3).to_string(index=False))
    print(salidas["modelo_importancia"].groupby("objetivo").head(6).to_string(index=False))
    print(f"\nalerta extractiva {a.ventana.iloc[0]} (base {a.mes_base.iloc[0]}, modelo {mejor['y_extractivo']}):")
    print(a.head(15)[["puesto_extractivo", "lugar", "prob_extractivo", "prob", "nivel_actual",
                      "razones_extractivo"]].to_string(index=False))


if __name__ == "__main__":
    main()
