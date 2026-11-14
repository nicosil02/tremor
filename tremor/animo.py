"""Ánimo hacia proyectos y empresas extractivas en radio y prensa: menciones y tono por proyecto, y su alza frente a
las semanas previas. Hipótesis de diseño: antes de un conflicto suben las menciones del proyecto y el tono se vuelve
negativo. Por reglas (léxico del dominio), no por LLM: cada tono se puede explicar con las palabras que lo dieron.

    python -m tremor.animo        # tablas mencion y animo (foto de los últimos 7 días frente a las 8 semanas previas; avisa picos y rachas negativas)

shortcut: diccionario curado de los proyectos más conflictivos; ampliarlo con SENACE/OEFA cuando haya alias limpios."""
import csv
import functools
import re
import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from tremor.db import DATOS, RAIZ, ahora, conectar
from tremor.lugares import norm

# nombre: (alias, departamento, provincias de la zona de influencia)
PROYECTOS = {
    "Las Bambas (MMG)": (r"las bambas|\bmmg\b", "Apurímac", ["Cotabambas", "Grau"]),
    "Corredor Minero del Sur": (r"corredor minero", "Cusco", ["Chumbivilcas", "Espinar"]),
    "Tía María (Southern)": (r"t[ií]a mar[ií]a|lindero", "Arequipa", ["Islay"]),
    "Toquepala y Cuajone (Southern)": (r"toquepala|cuajone|southern", "Moquegua", ["Mariscal Nieto", "Ilo"]),
    "Antapaccay y Coroccohuayco (Glencore)": (r"antapaccay|tintaya|coroccohuayco|glencore", "Cusco", ["Espinar"]),
    "Constancia (Hudbay)": (r"constancia|hudbay", "Cusco", ["Chumbivilcas"]),
    "Conga y Yanacocha (Newmont)": (r"\bconga\b|yanacocha|newmont", "Cajamarca", ["Cajamarca", "Celendín", "Hualgayoc"]),
    "Michiquillay": (r"michiquillay", "Cajamarca", ["Cajamarca"]),
    "Quellaveco (Anglo American)": (r"quellaveco|anglo american", "Moquegua", ["Mariscal Nieto"]),
    "Antamina": (r"antamina", "Áncash", ["Huari"]),
    "Cerro Verde": (r"cerro verde", "Arequipa", ["Arequipa"]),
    "Zafranal": (r"zafranal", "Arequipa", ["Castilla"]),
    "Río Blanco": (r"r[ií]o blanco copper|proyecto r[ií]o blanco|majaz", "Piura", ["Huancabamba", "Ayabaca"]),
    "Lote 192 y Lote 8": (r"lote 192|lote 1-?ab|lote 8\b", "Loreto", ["Datem del Marañón", "Loreto"]),
    "Oleoducto Norperuano (Petroperú)": (r"oleoducto|petroper[uú]", "Loreto", ["Datem del Marañón", "Loreto"]),
    "Lote 95 (Petrotal)": (r"lote 95|petrotal", "Loreto", ["Requena"]),
    "Camisea (Pluspetrol, TGP)": (r"camisea|pluspetrol|\btgp\b|lote 88|lote 56", "Cusco", ["La Convención"]),
    "Toromocho (Chinalco)": (r"toromocho|chinalco", "Junín", ["Yauli"]),
    "Inmaculada (Hochschild)": (r"inmaculada|hochschild", "Ayacucho", ["Paucar del Sara Sara", "Parinacochas"]),
    "Marcona (Shougang)": (r"shougang|marcona", "Ica", ["Nazca"]),
    "Lagunas Norte (Boroo)": (r"lagunas norte|barrick|boroo", "La Libertad", ["Santiago de Chuco"]),
    # "la poderosa" sola también es una radio (La Poderosa Mix) y frase de prédica: solo cuenta con contexto minero
    "Minera Poderosa": (r"minera poderosa|^(?=.*\b(?:minas?|miner[oa]s?|pataz|vijus|socav[oó]n)\b).*\bla poderosa\b(?!\s+mix)",
                        "La Libertad", ["Pataz"]),
    "Minera Bateas": (r"minera bateas|\bbateas\b", "Arequipa", ["Caylloma"]),
    "Raura": (r"\braura\b", "Huánuco", ["Lauricocha"]),
    "Volcan": (r"minera volcan|volcan compa", "Pasco", ["Pasco"]),
    "San Rafael (Minsur)": (r"minsur", "Puno", ["Melgar"]),
    "Corani (Bear Creek)": (r"corani|bear creek", "Puno", ["Carabaya"]),
}
NEGATIVO = re.compile(r"contamin|derram|incumpl|rechaz|denunci|abus|enga[ñn]|despoj|muert|herid|protest|\bparo\b|"
                      r"bloque|huelga|moviliz|exig|reclam|conflict|tensi[oó]n|malestar|indign|amenaz|desaloj|"
                      r"repres|afect|da[ñn]o|perjud|metales pesados|plomo|ars[eé]nico|polvo|rajadur|no queremos|"
                      r"traici|mient|corrup|estado de emergencia|sin consulta|enfrent|ultim[aá]tum", re.I)
POSITIVO = re.compile(r"\bacuerdo|di[aá]logo|mesa de (?:trabajo|desarrollo)|benefici|aporte|inversi[oó]n|desarrollo|"
                      r"empleo|convenio|(?<!in)cumpli[oó]|apoy|financi|construy|entreg|capacit|"
                      r"responsabilidad social|levant(?:an|aron) (?:el )?(?:paro|bloqueo)|tregua", re.I)
ALIAS = {n: re.compile(a, re.I) for n, (a, _, _) in PROYECTOS.items()}
# Quién habla, por el medio: la prensa minera suele publicar lo que manda la empresa y las organizaciones tienen agenda
# propia; ninguna de las dos es opinión pública. Por palabras del nombre, no por lista de medios: una revista minera
# nueva entra sola.
SECTOR = re.compile(r"miner|mining|proactivo|minart|energiminas|energ[ií]a|business|empresarial|negocios|desde adentro|"
                    r"bnamericas|iimp|snmpe|gesti[oó]n|semana econ[oó]mica", re.I)
ORGANIZACION = re.compile(r"cooperacci|observatorio|muqui|servindi|pressenza|derechos humanos|aidesep|conacami|cnddhh|"
                          r"grufides|wayka|convoca", re.I)
NACIONAL = re.compile(r"^(rpp|el comercio|la rep[uú]blica|correo|expreso|per[uú] ?21|gesti[oó]n|infobae|am[eé]rica|canal n|"
                      r"tv ?per[uú]|andina|exitosa|diario uno|ojo ?p[uú]blico|idl|la raz[oó]n|trome|latina|panamericana|atv|"
                      r"rcr|el peruano|caretas|hildebrandt|sudaca|epicentro|la encerrona|willax|pbo)", re.I)
REGIONAL = {"macronorte": "La Libertad"}  # medios regionales que llegan por Google News y no se deducen de otra forma


@functools.lru_cache
def _departamento_medio():
    from tremor.prensa.recolectar import FEEDS
    with open(Path(__file__).parent / "radios.csv", encoding="utf-8") as f:
        return {**{r["medio"].lower(): r["departamento"] for r in csv.DictReader(f)},
                **{m.lower(): d for m, (_, d) in FEEDS.items() if d}, **REGIONAL}


def medios_regionales(con, minimo=3, parte=0.8):
    """{medio: departamento} deducido de la base: un medio cuyas notas salen casi todas de la búsqueda de un mismo
    departamento es de ahí (Infobae sale en todos y no pasa). Así un medio regional nuevo se ubica solo."""
    n = {}
    for medio, dep, k in con.execute("SELECT lower(medio), departamento_consulta, COUNT(*) FROM nota WHERE medio IS NOT NULL "
                                     "AND departamento_consulta IS NOT NULL AND consulta != 'radio' GROUP BY 1, 2"):
        n.setdefault(medio, {})[dep] = k
    return {m: max(d, key=d.get) for m, d in n.items() if sum(d.values()) >= minimo and max(d.values()) / sum(d.values()) >= parte}


def departamento_de(medio, aprendidos=None):
    """Departamento del medio: por la lista de radios y feeds, por lo aprendido de la base o porque lo lleva en el nombre
    ("Diario La Opinión Ica"). None si no se sabe."""
    from tremor.lugares import catalogo
    m = (medio or "").lower()
    dep = _departamento_medio().get(m) or (aprendidos or {}).get(m)
    if dep:
        return norm(dep)
    regiones, provincias, _, _ = catalogo()
    palabras = " " + norm(medio or "") + " "
    return next((r for r in regiones if f" {r} " in palabras),  # el departamento o, si no, una provincia de un solo departamento
                next((r for r, c in regiones.items() for p, cs in provincias.items()
                      if len(p) >= 5 and f" {p} " in palabras and {x[:2] for x in cs} == {c}), None))


def quien(medio, proyecto, aprendidos=None):
    """Desde dónde se habla del proyecto: 'sector', 'organizacion', 'zona' (radio o medio del departamento del proyecto),
    'region' (medio de otro departamento) o 'nacional' (prensa de alcance nacional). Lo que no se sabe ubicar queda en
    'otros': no se le cuelga a nadie."""
    conocido = (medio or "").lower() in _departamento_medio()  # una radio o un feed de la lista no se juzga por el nombre
    if not conocido and ORGANIZACION.search(medio or ""):
        return "organizacion"
    if not conocido and SECTOR.search(medio or ""):
        return "sector"
    dep = departamento_de(medio, aprendidos)
    if dep and (conocido or not NACIONAL.search(medio or "")):
        return "zona" if dep == norm(PROYECTOS.get(proyecto, ("", dep))[1]) else "region"
    return "nacional" if NACIONAL.search(medio or "") else "otros"



def tono(texto):
    """(negativos, positivos, tono -1..1) en las frases que nombran el proyecto."""
    neg, pos = len(NEGATIVO.findall(texto)), len(POSITIVO.findall(texto))
    return neg, pos, (pos - neg) / (pos + neg) if pos + neg else 0.0


def menciones(texto):
    """[(proyecto, frases que lo nombran ± una frase)]."""
    frases = re.split(r"(?<=[.!?])\s+", texto)
    salida = []
    for nombre, rx in ALIAS.items():
        idx = [i for i, f in enumerate(frases) if rx.search(f)]
        if idx:
            ventana = sorted({j for i in idx for j in (i - 1, i, i + 1) if 0 <= j < len(frases)})
            salida.append((nombre, " ".join(frases[j] for j in ventana)))
    return salida


def _trigramas(texto, n=70):
    p = re.findall(r"\w+", norm(texto))[:n]
    return {tuple(p[i:i + 3]) for i in range(len(p) - 2)}


def historias(filas, dias=3, umbral=0.85):
    """[(nota_id, proyecto, fecha, texto)] → {(nota_id, proyecto): nota_id de la primera vez que salió esa historia}.
    Dos notas del mismo proyecto son la misma historia si, a lo más con `dias` de diferencia, los tríos de palabras
    seguidas de la más corta (titular y comienzo del texto) están en la otra en un 85%: el cable de agencia o el
    comunicado que diez medios copian tal cual. Sin esto, diez copias contaban como diez menciones.
    ponytail: compara cada nota con las historias abiertas del proyecto, O(n²) por proyecto; con miles por proyecto,
    un índice invertido de tríos."""
    salida, abiertas = {}, {}
    for nota_id, proyecto, fecha, texto in sorted(filas, key=lambda f: (f[2], f[0])):
        t = _trigramas(texto)
        dia = date.fromisoformat(fecha)
        cual = None
        if len(t) >= 6:  # un titular de menos de 8 palabras coincide por casualidad
            for cabeza, (t0, d0) in abiertas.setdefault(proyecto, {}).items():
                if (dia - d0).days <= dias and len(t & t0) / min(len(t), len(t0)) >= umbral:
                    cual = cabeza
                    break
            if cual is None:
                abiertas[proyecto][nota_id] = (t, dia)
        salida[(nota_id, proyecto)] = cual or nota_id
    return salida


def provincias():
    """proyecto → ubigeos de provincia (4 dígitos), resueltos por nombre en el catálogo del INEI."""
    u = pd.read_csv(RAIZ / "tremor" / "ubigeo.csv", dtype=str)
    clave = {(norm(r.region), norm(r.provincia)): r.ubigeo[:4] for r in u.itertuples()}
    salida = {n: [clave[(norm(d), norm(p))] for p in ps] for n, (_, d, ps) in PROYECTOS.items()}
    assert all(len(v) == len(PROYECTOS[n][2]) for n, v in salida.items()), "provincia mal escrita"
    return salida


def actualizar(con, hoy=None):
    notas = pd.read_sql("SELECT id, medio, titular, resumen, substr(publicado, 1, 10) AS fecha, consulta FROM nota "
                        "WHERE publicado IS NOT NULL AND COALESCE(filtro, '') NOT IN ('religioso', 'musica_o_ruido', 'aviso', 'medio_extranjero')", con)
    filas = []
    for r in notas.itertuples():
        for nombre, frase in menciones(f"{r.titular}. {r.resumen or ''}".replace(r.medio or "\0", "")):  # sin el nombre del medio
            neg, pos, t = tono(frase)
            filas.append((r.id, nombre, r.fecha, r.medio, "radio" if r.consulta == "radio" else "web", neg, pos, t))
    m = pd.DataFrame(filas, columns=["nota_id", "proyecto", "fecha", "medio", "origen", "negativos", "positivos", "tono"])
    tabla_dicho(con)  # el tono que dio el LLM al leer la mención manda sobre el del léxico
    m = m.merge(pd.read_sql("SELECT nota_id, proyecto, tono AS t_llm, voz FROM mencion_dicho WHERE tono IS NOT NULL", con), "left", on=["nota_id", "proyecto"])
    m["tono"] = m.pop("t_llm").fillna(m.tono)
    # la misma nota en varios medios es una historia; la radio no se compara (cada transcripción sale distinta)
    texto = {r.id: f"{r.titular}. {r.resumen or ''}".replace(r.medio or "\0", "") for r in notas.itertuples()}
    h = historias([(r.nota_id, r.proyecto, r.fecha, texto[r.nota_id]) for r in m[m.origen == "web"].itertuples()])
    m["historia"] = [h.get((r.nota_id, r.proyecto), r.nota_id) for r in m.itertuples()]
    # nota de la empresa: habla ella (voz que dio el LLM), o es una nota favorable que tres medios o más copiaron
    # igual, que es como circula un comunicado. Se marca, no se borra: la app decide si la muestra aparte
    copiada = m.groupby(["proyecto", "historia"]).medio.transform("nunique") >= 3
    m["corporativa"] = ((m.pop("voz") == "empresa") | (copiada & (m.tono > 0))).astype(int)
    m.to_sql("mencion", con, if_exists="replace", index=False)
    hoy = hoy or date.today()
    m["dias"] = (pd.Timestamp(hoy) - pd.to_datetime(m.fecha)).dt.days
    reciente, previo = m[m.dias.between(0, 6)], m[m.dias.between(7, 7 + 56 - 1)]
    a = pd.DataFrame({"historias_7d": reciente.groupby("proyecto").historia.nunique(),
                      "medios_7d": reciente.groupby("proyecto").medio.nunique(),
                      "corporativas_7d": reciente.groupby("proyecto").corporativa.sum(),
                      "menciones_7d": reciente.groupby("proyecto").size(),
                      "negativas_7d": reciente[reciente.tono < 0].groupby("proyecto").size(),
                      "tono_7d": reciente.groupby("proyecto").tono.mean(),
                      "base_7d": previo.groupby("proyecto").size() / 8}).reindex(list(PROYECTOS)).fillna(0)
    a["alza"] = (a.menciones_7d / a.base_7d.clip(lower=1)).round(2)  # ×veces lo normal (mínimo 1 de base)
    a["pct_negativo"] = (a.negativas_7d / a.menciones_7d.clip(lower=1)).round(2)
    a["aviso"] = pd.Series(avisos(reciente, previo)).reindex(a.index)
    prov = provincias()
    a = a.reset_index(names="proyecto").assign(provincias=lambda d: d.proyecto.map(lambda n: " ".join(prov[n])),
                                               hasta=str(hoy), creado=ahora())
    a.to_sql("animo", con, if_exists="replace", index=False)
    historia(con, m, a, str(hoy)[:7])
    (DATOS / "exportes").mkdir(parents=True, exist_ok=True)
    a.to_csv(DATOS / "exportes" / "animo.csv", index=False)
    return m, a


def historia(con, m, a, mes):
    """El mes en curso del índice queda en animo_mes (se reemplaza en cada corrida): con un año de historia se puede
    probar la reputación como variable del modelo."""
    con.execute("CREATE TABLE IF NOT EXISTS animo_mes (proyecto TEXT, mes TEXT, menciones INTEGER, negativas INTEGER, "
                "tono REAL, alza REAL, PRIMARY KEY (proyecto, mes))")
    mm = m[m.fecha.str.startswith(mes)]
    alza = a.set_index("proyecto").alza
    filas = [(p, mes, len(g), int((g.tono < 0).sum()), float(g.tono.mean()), float(alza.get(p, 0))) for p, g in mm.groupby("proyecto")]
    con.executemany("INSERT OR REPLACE INTO animo_mes VALUES (?, ?, ?, ?, ?, ?)", filas)
    con.commit()


def avisos(reciente, previo):
    """Proyecto → aviso de ánimo negativo: un pico (un día con ≥3 historias negativas, ≥3× su día normal y en dos
    medios o más) o una racha (menciones negativas en ≥3 de los últimos 7 días). Se cuentan historias, no notas: un
    cable copiado por diez medios no es un pico. ponytail: umbrales a ojo, calibrar con los eventos."""
    unicas = lambda d: d[d.tono < 0].drop_duplicates(["proyecto", "fecha", "historia"])
    neg = unicas(reciente).groupby(["proyecto", "fecha"]).size()
    medios = reciente[reciente.tono < 0].groupby(["proyecto", "fecha"]).medio.nunique()
    normal = unicas(previo).groupby("proyecto").size() / 56
    salida = {}
    for proyecto, dias in neg.groupby(level=0):
        dias = dias.droplevel(0)
        pico = dias[(dias >= 3) & (dias >= 3 * normal.get(proyecto, 0)) & (medios[proyecto].reindex(dias.index) >= 2)]
        texto = [f"pico negativo el {d} ({n} menciones)" for d, n in pico.items()]
        if len(dias) >= 3:
            texto.append(f"racha negativa: {len(dias)} de los últimos 7 días")
        if texto:
            salida[proyecto] = "; ".join(texto)
    return salida


def senal(con):
    """Provincia (4 dígitos) → frase de ánimo para la alerta, solo de proyectos con menciones recientes."""
    try:
        a = pd.read_sql("SELECT * FROM animo WHERE menciones_7d > 0", con)
    except (sqlite3.OperationalError, pd.errors.DatabaseError):
        return {}
    salida = {}
    for r in a.sort_values("menciones_7d", ascending=False).itertuples():
        texto = (f"{r.proyecto}: {r.menciones_7d:.0f} menciones en 7 días (×{r.alza:g}), {r.pct_negativo:.0%} negativas"
                 + (f" — AVISO: {r.aviso}" if isinstance(r.aviso, str) else ""))
        for p in r.provincias.split():
            salida.setdefault(p, []).append(texto)
    return {p: "; ".join(v) for p, v in salida.items()}


DICHO = ("Lees una nota de prensa o la transcripción automática, con errores, de un fragmento de radio peruana donde se nombra a una "
         "empresa o proyecto extractivo. Escribe en UNA oración de máximo 25 palabras, en castellano llano, qué pasó o qué se dijo sobre ese proyecto y quién lo dijo "
         "(por rol: un dirigente, un locutor, un comunero, una autoridad…), sin nombres de personas. Cuenta solo lo que se opina o "
         "informa SOBRE la operación: reclamos, apoyos, denuncias, acuerdos, anuncios. Si son saludos a trabajadores o vecinos, una "
         "mención de pasada, publicidad de la propia empresa, música o prédica, di exactamente \"no habla del proyecto\". "
         "\n\nDi el TONO: cómo queda la imagen de la empresa ante quien lee o escucha, no si la nota opina.\n"
         "- \"critica\": la acusan, la denuncian, le reclaman, protestan contra ella, la sancionan, pierde un juicio o se le "
         "atribuye un daño. Vale aunque el medio solo lo informe y aunque quien acusa sea poco creíble.\n"
         "- \"favorable\": recibe un premio o reconocimiento, entrega algo, hace una obra o un programa, cumple un acuerdo, "
         "gana un juicio, o alguien la apoya o la celebra.\n"
         "- \"neutra\": la empresa es la víctima (un ataque, un robo, mineros ilegales en su concesión), cifras de producción, "
         "un trámite, un juicio contra otros, o no queda ni bien ni mal.\n"
         "Di el TEMA, uno solo: \"protesta\" (paro, bloqueo o marcha contra la empresa), \"judicial\" (juicios, fiscalía, "
         "denuncias penales), \"dialogo\" (mesa, reunión, acuerdo), \"aporte\" (donación, obra o programa social), "
         "\"reconocimiento\" (premio, certificación, ranking), \"ambiente\" (contaminación, agua, relaves), \"seguridad\" "
         "(ataques, crimen, minería ilegal, accidentes), \"laboral\" (trabajadores, sindicato, huelga), \"otro\".\n"
         "Di la VOZ, quién habla de la empresa en la nota: \"empresa\" (la propia empresa, su portavoz o su comunicado), "
         "\"comunidad\" (comuneros, dirigentes, pobladores, frentes de defensa, trabajadores), \"autoridad\" (alcalde, "
         "gobernador, ministerio, fiscalía, juez, congresista), \"medio\" (el periodista o locutor opina o informa por su "
         "cuenta) u \"otro\".\n"
         "Ejemplos (tono, tema):\n"
         "\"Las Bambas entrega camión volquete a la comunidad de Chila\" → favorable, aporte\n"
         "\"Minera obtiene el Galardón Plata del Premio Iberoamericano de la Calidad\" → favorable, reconocimiento\n"
         "\"Duro revés judicial para la minera: la comunidad sigue en alerta\" → critica, judicial\n"
         "\"Detenido acusa a la minera de contratar sicarios\" → critica, judicial\n"
         "\"Gobernador pide presencia del ejército tras ataque a la minera\" → neutra, seguridad\n"
         "\"Fiscalía pide prisión para comuneros por las protestas contra la mina\" → neutra, judicial\n"
         "\"Comuneros bloquean la vía y exigen que la minera cumpla el convenio\" → critica, protesta\n"
         'Responde JSON {"dicho": "<oración>", "tono": "favorable" | "critica" | "neutra", "tema": "<tema>", "voz": "<voz>"}.')
TONO_LLM = {"favorable": 1, "critica": -1, "crítica": -1}
VOCES_LLM = {"empresa", "comunidad", "autoridad", "medio", "otro"}
TEMAS_LLM = {"protesta", "judicial", "dialogo", "aporte", "reconocimiento", "ambiente", "seguridad", "laboral", "otro"}


def tabla_dicho(con):
    con.execute("CREATE TABLE IF NOT EXISTS mencion_dicho (nota_id TEXT, proyecto TEXT, dicho TEXT, tono INTEGER, tema TEXT, voz TEXT, PRIMARY KEY (nota_id, proyecto))")
    for col in {"tono": "INTEGER", "tema": "TEXT", "voz": "TEXT"}.items():  # bases de antes del tono, el tema y la voz
        if col[0] not in [c[1] for c in con.execute("PRAGMA table_info(mencion_dicho)")]:
            con.execute(f"ALTER TABLE mencion_dicho ADD COLUMN {col[0]} {col[1]}")


def dicho(con, max_solicitudes=60):
    """Qué pasó o qué se dijo del proyecto en cada mención de los últimos 30 días, radio y prensa, en una oración del LLM,
    y su tono hacia la empresa (tabla mencion_dicho): es el título de la mención en la app y el color de la barra de
    reputación. El léxico y el transformer se equivocaban ("entrega camión volquete a la comunidad" salía crítica).
    Las que quedaron sin tono se vuelven a pedir. Sin cupo, se sigue en la próxima corrida."""
    from tremor.llm import chat_json, SinCuota, RespuestaInvalida
    tabla_dicho(con)
    desde = (date.today() - timedelta(days=30)).isoformat()
    xs = con.execute("""SELECT m.nota_id, m.proyecto, CASE WHEN m.origen = 'radio' THEN n.resumen ELSE n.titular || '. ' || COALESCE(n.resumen, '') END
                        FROM mencion m JOIN nota n ON n.id = m.nota_id
                        WHERE m.fecha >= ? AND COALESCE(n.filtro, '') NOT IN ('religioso', 'musica_o_ruido', 'aviso', 'medio_extranjero')
                          AND NOT EXISTS (SELECT 1 FROM mencion_dicho d WHERE d.nota_id = m.nota_id AND d.proyecto = m.proyecto AND d.voz IS NOT NULL)
                        ORDER BY m.fecha DESC""", (desde,)).fetchall()[:max_solicitudes]
    hechas = 0
    for nota_id, proyecto, texto in xs:
        mm = ALIAS[proyecto].search(texto) if proyecto in ALIAS else None
        trozo = texto[max(0, mm.start() - 400):mm.end() + 400] if mm else texto[:800]
        try:
            r = chat_json(con, DICHO, f"Proyecto: {proyecto}\n\n{trozo}", "dicho4")
        except SinCuota as e:
            print(f"  dicho de menciones pendiente: {str(e)[:80]}")
            break
        except RespuestaInvalida:
            continue
        tema = str(r.get("tema")).strip().lower().replace("á", "a")
        voz = str(r.get("voz")).strip().lower()
        con.execute("INSERT OR REPLACE INTO mencion_dicho (nota_id, proyecto, dicho, tono, tema, voz) VALUES (?, ?, ?, ?, ?, ?)",
                    (nota_id, proyecto, (r.get("dicho") or "").strip()[:300], TONO_LLM.get(str(r.get("tono")).strip().lower(), 0),
                     tema if tema in TEMAS_LLM else "otro", voz if voz in VOCES_LLM else "otro"))
        hechas += 1
    con.commit()
    return hechas


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    con = conectar()
    m, a = actualizar(con)
    n = dicho(con)
    if n:  # el índice se rehace con los tonos recién leídos
        m, a = actualizar(con)
    print(f"{n} menciones resumidas por el LLM")
    print(f"{len(m)} menciones en {m.nota_id.nunique()} notas ({(m.origen == 'radio').sum()} de radio)")
    print(a[a.menciones_7d > 0][["proyecto", "menciones_7d", "base_7d", "alza", "pct_negativo", "tono_7d"]]
          .sort_values("menciones_7d", ascending=False).to_string(index=False))


if __name__ == "__main__":
    main()
