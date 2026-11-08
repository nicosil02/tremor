"""Incidentes de conflicto social en minas del Perú, solo según lo que las empresas reportan a bolsas y reguladores.

    python -m tremor.bolsa bajar     # HKEX (MMG, Las Bambas), SMV (hechos de importancia, espejo de la BVL), SEC EDGAR
    python -m tremor.bolsa extraer   # párrafos con palabras clave → LLM → datos/crudos/bolsa/incidentes.csv

Los archivos bajados son datos no confiables: viven en datos/crudos/bolsa/ y solo se leen como texto.
Cada fila trae la URL del documento y una cita textual que se comprueba contra el texto (si no está, se descarta).
"""
import hashlib
import json
import re
import sys
import time
import unicodedata

import pandas as pd
import requests

from tremor.db import DATOS

CRUDOS = DATOS / "crudos" / "bolsa"
INDICE = CRUDOS / "indice.csv"
DESDE, HASTA = "2023-01-01", "2026-11-08"
SEC_UA = {"User-Agent": "Tremor investigacion nicolas.silva@pucp.edu.pe"}  # aprobado por el autor
WEB_UA = {"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"}

# HKEX: MMG (01208) tiene stockId interno 2693 (search/prefix.do?name=1208)
HKEX_TITULOS = r"PRODUCTION REPORT|LAS BAMBAS UPDATE|^VOLUNTARY ANNOUNCEMENT$|RESULTS FOR THE|ANNUAL RESULTS"
# SMV: los hechos de importancia que la SMV recibe, publicados por la BVL (la web de la SMV da error 500)
SMV = {"B20003": "Buenaventura", "B20027": "Southern Peru", "CM0006": "Cerro Verde", "A20032": "Minsur",
       "CM0001": "Volcan", "B20010": "Nexa Resources Perú", "CM0007": "Nexa Resources Atacocha",
       "B20026": "El Brocal", "B20013": "San Ignacio de Morococha", "002597": "Minera Corona", "CM0004": "Shougang"}
SMV_TITULOS = (r"bloque|paraliz|suspensi.n (?:de|temporal de) (?:operac|producc|activid|labores)|reanuda|reinicio de oper"
               r"|acceso|interrump|comunidad|protest|conflict")
# SEC: CIK de las que operan en el Perú
SEC = {"1001838": "Southern Copper", "1013131": "Buenaventura", "831259": "Freeport-McMoRan (Cerro Verde)",
       "1713930": "Nexa Resources", "1322422": "Hudbay (Constancia)"}
SEC_Q = ('blockade OR blockades OR blockaded OR roadblock OR roadblocks OR protest OR protests OR protesters '
         'OR "social unrest" OR "social conflict" OR "community conflict" OR bloqueo OR bloqueos OR "illegal miners"')
CLAVES = re.compile(r"blockad|road ?block|protest|unrest|social conflict|paro\b|bloque|toma de|invasi|paraliz"
                    r"|illegal miner|mineros (?:informales|ilegales)", re.I)
# La SEC mezcla operaciones de otros países (México, Indonesia, Brasil, Canadá): el párrafo tiene que nombrar el Perú
PERU = re.compile(r"Per[uú]|Las Bambas|T[ií]a Mar[ií]a|Cuajone|Toquepala|Ilo\b|Constancia|Pampacancha|Cerro Verde"
                  r"|Cerro Lindo|Atacocha|El Porvenir|Cajamarquilla|Uchucchacua|Julcani|Orcopampa|Tambomayo"
                  r"|Coimolache|Yanacocha|Colquijirca|El Brocal|San Gabriel|Arequipa|Cusco|Apur[ií]mac|Moquegua"
                  r"|Pasco|Chumbivilcas|Islay")


def _guardar(url, nombre, encabezados):
    ruta = CRUDOS / nombre
    if not ruta.exists():
        for intento in range(4):  # la SEC responde 503 a ratos
            r = requests.get(url, headers=encabezados, timeout=120)
            if r.status_code != 503:
                break
            time.sleep(10 * (intento + 1))
        r.raise_for_status()
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_bytes(r.content)
        time.sleep(0.5)  # SEC permite 10/s: vamos mucho más lento
    return str(ruta.relative_to(CRUDOS))


def hkex():
    p = dict(sortDir=0, sortByOptions="DateTime", category=0, market="SEHK", stockId=2693, documentType=-1,
             fromDate=DESDE.replace("-", ""), toDate=HASTA.replace("-", ""), title="", searchType=0, t1code=-2,
             t2Gcode=-2, t2code=-2, rowRange=1000, lang="E")
    r = requests.get("https://www1.hkexnews.hk/search/titleSearchServlet.do", params=p, headers=WEB_UA, timeout=60)
    for x in json.loads(r.json()["result"]):
        titulo = re.sub(r"\s+", " ", x["TITLE"]).strip()
        if re.search(HKEX_TITULOS, titulo) and "REPUBLISHED" not in titulo:
            url = "https://www1.hkexnews.hk" + x["FILE_LINK"]
            d, m, a = x["DATE_TIME"][:10].split("/")
            yield dict(fuente="HKEX", empresa="MMG (Las Bambas)", documento=titulo, fecha_documento=f"{a}-{m}-{d}",
                       url=url, archivo=_guardar(url, "hkex/" + url.rsplit("/", 1)[1], WEB_UA))


def smv():
    for rpj, empresa in SMV.items():
        cuerpo = {"rpjCode": rpj, "page": 1, "size": 2000, "search": "", "startDate": DESDE, "endDate": HASTA}
        r = requests.post("https://dataondemand.bvl.com.pe/v1/corporate-actions", json=cuerpo, headers=WEB_UA,
                          timeout=60)
        for x in json.loads(r.content.decode("utf-8", "replace"))["content"]:
            codigos = " ".join(c["descCodeHHII"] for c in x["codes"] or [])
            titulo = " ".join(x["observation"].split())
            if not (re.search(SMV_TITULOS, titulo, re.I) or "Huelgas, Interrupciones" in codigos) \
                    or re.search(r"negociaci.n de acciones|capital social|estatuto|OPA\b", titulo, re.I):
                continue
            for doc in x["documents"] or []:
                url = "https://documents.bvl.com.pe" + doc["path"]
                yield dict(fuente="SMV", empresa=empresa, documento=titulo, fecha_documento=x["registerDate"][:10],
                           url=url, archivo=_guardar(url, "smv/" + doc["path"].strip("/").replace("/", "_"), WEB_UA))


def sec():
    for cik, empresa in SEC.items():
        desde = 0
        while True:
            p = dict(q=SEC_Q, ciks=cik.zfill(10), dateRange="custom", startdt=DESDE, enddt=HASTA, **{"from": desde})
            h = requests.get("https://efts.sec.gov/LATEST/search-index", params=p, headers=SEC_UA, timeout=60).json()
            time.sleep(0.5)
            for x in h["hits"]["hits"]:
                s, (acc, nombre) = x["_source"], x["_id"].split(":", 1)
                tipo = s.get("file_type") or s.get("file_description") or ""
                if re.match(r"EX-(96|2|4|10|23|31|32|97)|ARS|GRAPHIC", tipo) or not nombre.lower().endswith(
                        (".htm", ".html", ".txt", ".pdf")):
                    continue  # informes técnicos, contratos y certificaciones: sin incidentes, muy largos
                url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc.replace('-', '')}/{nombre}"
                yield dict(fuente="SEC", empresa=empresa, documento=f"{s['form']} {nombre}",
                           fecha_documento=s["file_date"], url=url,
                           archivo=_guardar(url, f"sec/{cik}_{acc}_{nombre}", SEC_UA))
            desde += len(h["hits"]["hits"])
            if not h["hits"]["hits"] or desde >= h["hits"]["total"]["value"]:
                break


def bajar():
    filas = []
    for paso in (hkex, smv, sec):
        try:
            filas += list(paso())
        except Exception as e:  # una fuente caída no frena a las otras
            print(f"{paso.__name__}: {type(e).__name__} {str(e)[:150]}")
        print(paso.__name__, sum(f["fuente"] == paso.__name__.upper() for f in filas))
    pd.DataFrame(filas).drop_duplicates("url").to_csv(INDICE, index=False)


def texto(ruta) -> str:
    """Texto plano de un PDF o HTML bajado (sin ejecutar nada del archivo)."""
    if ruta.suffix.lower() == ".pdf":
        import pymupdf
        with pymupdf.open(ruta) as doc:
            return "\n\n".join(p.get_text() for p in doc)
    import warnings
    from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
    warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
    return BeautifulSoup(ruta.read_bytes(), "lxml").get_text("\n")


def plano(s: str) -> str:
    """Para comparar citas: sin tildes, comillas tipográficas ni saltos, en minúsculas."""
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return " ".join(re.sub(r"[^a-z0-9%]+", " ", s).split())


def parrafos(t: str) -> list[str]:
    """Párrafos con alguna palabra clave; los PDF cortan líneas, así que se unen por línea en blanco o punto final."""
    bloques = re.split(r"\n\s*\n|(?<=[.:;])\s*\n(?=[A-Z•(])", t)
    return [" ".join(b.split())[:2500] for b in bloques if CLAVES.search(b) and len(b.split()) >= 8]


SISTEMA = f"""Extraes incidentes de conflicto social que afectaron operaciones mineras EN EL PERÚ, a partir de
fragmentos de documentos que una empresa minera presentó a una bolsa o regulador. Cuenta como incidente: bloqueo de
vías o accesos, paro (de comunidades, transportistas, población o paro regional/nacional), toma o invasión de
instalaciones (también por mineros informales), protestas que detuvieron o perturbaron la operación o el transporte.
NO cuentan: huelgas o pliegos de sindicatos de trabajadores de la propia empresa, accidentes, clima, mantenimiento,
paradas por orden de autoridad sin protesta, riesgos genéricos ("podría haber protestas"), incidentes fuera del Perú.
Solo incidentes ocurridos entre {DESDE} y {HASTA}. No inventes: si el texto no lo dice, deja el campo vacío.
Responde JSON: {{"incidentes": [{{"unidad": "mina u operación", "fecha_inicio": "YYYY-MM-DD o YYYY-MM o vacío",
"fecha_fin": "igual", "dias_afectados": número o null, "tipo": "bloqueo|paro|toma|protesta|otro",
"lugar": "distrito, provincia o comunidad tal como lo escribe", "causa": "breve, actores por rol, sin nombres de
personas", "efecto": "p. ej. transporte de concentrado detenido, producción suspendida", "cita": "copia LITERAL de
menos de 25 palabras del fragmento, en su idioma original, que pruebe el incidente; elige un tramo sin nombres de
personas"}}]}}. Un incidente por
episodio; si el fragmento repite el mismo episodio, una sola entrada. Fechas en español o inglés: conviértelas;
"durante el trimestre" o "a fines de marzo" sin día → solo YYYY-MM si el mes es claro, si no vacío."""


def extraer():
    from tremor.db import conectar
    from tremor.llm import RespuestaInvalida, SinCuota, chat_json
    con, indice, vistos, filas, sin_cita = conectar(), pd.read_csv(INDICE).fillna(""), set(), [], 0
    for doc in indice.sort_values("fecha_documento").to_dict("records"):
        t = texto(CRUDOS / doc["archivo"])
        nuevos = []  # el mismo párrafo se repite trimestre a trimestre: va al LLM solo la primera vez
        # los hechos de importancia son cartas de 1-2 páginas, ya filtradas por título: van enteras
        for p in [" ".join(t.split())[:7000]] if doc["fuente"] == "SMV" and t.strip() else parrafos(t):
            if doc["fuente"] == "SEC" and not PERU.search(p):
                continue
            h = hashlib.sha1(f"{doc['empresa']}|{plano(p)}".encode()).hexdigest()
            if h not in vistos:
                vistos.add(h)
                nuevos.append(p)
        lote = ""
        for p in nuevos + [None]:
            if p is not None and len(lote) + len(p) < 7000:
                lote += p + "\n\n"
                continue
            if lote:
                usuario = f"Empresa: {doc['empresa']}\nDocumento: {doc['documento']} ({doc['fecha_documento']})\n\n{lote}"
                try:
                    res = chat_json(con, SISTEMA, usuario, "bolsa-1")
                except (SinCuota, RespuestaInvalida, requests.RequestException) as e:  # queda para la próxima corrida
                    print(f"  {doc['documento'][:60]}: {e}"[:160])
                    res = {}
                for i in res.get("incidentes") or []:
                    cita = " ".join(str(i.get("cita") or "").split()[:25])
                    if not cita or plano(cita) not in plano(t):
                        sin_cita += 1
                        continue
                    filas.append({**{k: i.get(k) for k in ("unidad", "fecha_inicio", "fecha_fin", "dias_afectados",
                                                           "tipo", "lugar", "causa", "efecto")},
                                  "empresa": doc["empresa"], "cita": cita,
                                  **{k: doc[k] for k in ("fuente", "documento", "fecha_documento", "url")}})
            lote = (p + "\n\n") if p else ""
    print(f"{len(filas)} menciones, {sin_cita} descartadas por cita que no está en el documento")
    pd.DataFrame(filas).to_csv(CRUDOS / "menciones.csv", index=False, encoding="utf-8")  # antes de fusionar
    df = fusionar(pd.DataFrame(filas))
    df.to_csv(CRUDOS / "incidentes.csv", index=False, encoding="utf-8")
    print(df.groupby(["empresa", "fuente"]).size().to_string())


COLUMNAS = ["empresa", "unidad", "fecha_inicio", "fecha_fin", "dias_afectados", "tipo", "lugar", "causa", "efecto",
            "fuente", "documento", "fecha_documento", "url", "cita"]


VACIAS = {"unidad", "minera", "mina", "mine", "operation", "operations", "operacion", "operaciones", "um", "de", "del",
          "the", "copper", "project", "proyecto", "cerro", "el", "la", "las", "san", "y", "and", "complex", "tajo",
          "open", "pit", "nexa", "resources"}


def _unidad(s) -> set:
    return set(plano(str(s or "")).split()) - VACIAS


def _fecha(s) -> str:
    """Solo YYYY-MM-DD o YYYY-MM; un año suelto o un trimestre no sirven para ubicar el mes."""
    s = re.sub(r"[^0-9-]", "", str(s or ""))[:10]
    return s if re.fullmatch(r"\d{4}-\d{2}(-\d{2})?", s) else ""


def _inicio(s: str) -> pd.Timestamp:
    return pd.Timestamp(s[:7] + "-01" if len(s) == 7 else s)


def _fin(s: str) -> pd.Timestamp:
    """Último día que cubre la fecha de fin, con 10 días de holgura (un mes sin día cubre el mes)."""
    return (pd.Timestamp(s[:7] + "-01") + pd.offsets.MonthEnd(0) if len(s) == 7 else pd.Timestamp(s)) +         pd.Timedelta(days=10)


def _mismo(f, g) -> bool:
    """Mismo incidente: comparten una palabra de la unidad y empiezan juntos (≤10 días; el mismo mes si alguno solo
    trae el mes) o uno empieza dentro del tramo del otro."""
    a, b = f["fecha_inicio"], g["fecha_inicio"]
    if not (f["u"] & g["u"]) or not a or not b:
        return False
    if len(a) == len(b) == 10:
        if abs((_inicio(a) - _inicio(b)).days) <= 10:
            return True
    elif a[:7] == b[:7]:
        return True
    dentro = lambda x, h: bool(h["fecha_fin"]) and _inicio(h["fecha_inicio"]) <= _inicio(x) <= _fin(h["fecha_fin"])
    return dentro(a, g) or dentro(b, f)


TRIMESTRE = {"01": "03", "04": "06", "07": "09", "10": "12"}


def _trimestre(f):
    """"Durante el tercer trimestre" no es 1 jul–30 set ni jul–set: queda el mes de inicio, sin fin ni días."""
    ini, fin = f["fecha_inicio"], f["fecha_fin"]
    if ini[5:7] in TRIMESTRE and fin[:4] == ini[:4] and fin[5:7] == TRIMESTRE[ini[5:7]] and ini[8:] in ("", "01") \
            and (len(fin) == 7 or fin[8:] in ("30", "31")):
        f["fecha_inicio"], f["fecha_fin"], f["dias_afectados"] = ini[:7], "", ""
    return f


def _juntar(filas):
    salida, descartadas = [], 0
    for f in filas:
        par = next((g for g in salida if _mismo(f, g)), None)
        if par is None and not f["fecha_inicio"]:
            ini = (pd.Timestamp(f["fecha_documento"]) - pd.DateOffset(months=4)).strftime("%Y-%m")
            par = next((g for g in salida if f["u"] & g["u"] and ini <= g["fecha_inicio"][:7] <= f["fecha_documento"]),
                       None)
            if par is None:
                descartadas += 1
                continue
        if par is None:
            salida.append(f)
            continue
        if f["fecha_documento"] < par["fecha_documento"]:  # vale la presentación más antigua
            for k in ("empresa", "fuente", "documento", "fecha_documento", "url", "cita", "unidad"):
                par[k] = f[k]
        # la fecha más precisa (día sobre mes); a igual precisión, el inicio más temprano y el fin más tardío, este
        # solo si lo dice un documento de ese mes (el aviso de reanudación), no un resumen posterior aproximado
        if len(f["fecha_inicio"]) > len(par["fecha_inicio"]) or (
                len(f["fecha_inicio"]) == len(par["fecha_inicio"]) and f["fecha_inicio"] < par["fecha_inicio"]):
            par["fecha_inicio"] = f["fecha_inicio"]
        if len(f["fecha_fin"]) > len(par["fecha_fin"]) or (
                len(f["fecha_fin"]) == len(par["fecha_fin"]) and f["fecha_fin"] > par["fecha_fin"]
                and pd.Timestamp(f["fecha_documento"]) <= _fin(f["fecha_fin"]) + pd.Timedelta(days=20)):
            par["fecha_fin"] = f["fecha_fin"]
        for k in ("dias_afectados", "lugar", "causa", "efecto", "tipo"):
            par[k] = par[k] or f[k]
        par["u"] = par["u"] | f["u"]
    return salida, descartadas


def fusionar(df: pd.DataFrame) -> pd.DataFrame:
    """Une las repeticiones de un incidente aunque las reporte otra empresa (p. ej. Cerro Verde en Freeport y en
    Buenaventura): queda el documento más antiguo y las fechas más precisas. Las filas sin mes se pegan a un
    incidente de su unidad que empezó en los 4 meses previos al documento, o se descartan. Se repite hasta que no
    cambie, porque un fin conocido después puede unir dos filas que al principio no se tocaban."""
    if df.empty:
        return pd.DataFrame(columns=COLUMNAS)
    df = df.fillna("").astype(str)
    df["fecha_inicio"], df["fecha_fin"] = df["fecha_inicio"].map(_fecha), df["fecha_fin"].map(_fecha)
    df["u"] = df["unidad"].map(_unidad)
    df = df[(df["fecha_fin"].where(df["fecha_fin"] != "", df["fecha_inicio"]) >= DESDE[:7])
            | (df["fecha_inicio"] == "")]  # incidentes que terminaron antes de 2023
    filas = [_trimestre(f) for f in df.sort_values("fecha_documento").to_dict("records")]
    salida, descartadas = _juntar([f for f in filas if f["fecha_inicio"]] + [f for f in filas if not f["fecha_inicio"]])
    while len(otra := _juntar(salida)[0]) < len(salida):
        salida = otra
    print(f"{descartadas} menciones sin mes que no se pudieron ubicar")
    return pd.DataFrame(salida)[COLUMNAS].sort_values(["fecha_inicio", "empresa"])


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    {"bajar": bajar, "extraer": extraer}[sys.argv[1]]()
