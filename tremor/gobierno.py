"""Señales mensuales del gobierno local: gasto municipal del mes (MEF), vacancias y revocatorias (JNE), informes de
control (Contraloría). Una tabla larga, `distrito_mes(ubigeo, m, variable, valor, fuente)`, con m = anio*12 + mes - 1
(la convención de tremor/modelo.py). La municipalidad provincial lleva el ubigeo del distrito capital.

`python -m tremor.gobierno {mef_mensual,jne,contraloria}`
"""
import argparse
import html
import json
import re
import sqlite3
import sys
import time
from collections import Counter, defaultdict
from datetime import date, timedelta

import requests

from tremor.db import DATOS, ahora, conectar
from tremor.lugares import norm, resolver
from tremor.territorio import UA, consulta, por_municipalidad

CRUDOS = DATOS / "crudos" / "gobierno"
ESQUEMA = """CREATE TABLE IF NOT EXISTS distrito_mes (
    ubigeo TEXT NOT NULL, m INTEGER NOT NULL, variable TEXT NOT NULL, valor REAL, fuente TEXT,
    consultado TEXT NOT NULL, PRIMARY KEY (ubigeo, m, variable))"""


def guardar(con, filas, fuente):
    """filas: [(ubigeo, m, variable, valor)]. Reemplaza las mismas llaves (idempotente)."""
    con.execute(ESQUEMA)
    momento = ahora()
    con.executemany("INSERT OR REPLACE INTO distrito_mes VALUES (?, ?, ?, ?, ?, ?)",
                    [(u, m, v, x, fuente, momento) for u, m, v, x in filas])
    con.commit()


# --- MEF: devengado de cada municipalidad en el mes (Consulta Amigable, filtro por mes) ---------------------
# dev_total: todo el gasto; dev_proyectos: solo proyectos de inversión (ap=Proyecto); dev_canon: rubro 18.
GASTOS = {"dev_total": ({}, "ActProy"), "dev_proyectos": ({}, "Proyecto"), "dev_canon": ({"rubro": "18"}, "ActProy")}


def mef_mensual(con, desde=2010):
    hoy = date.today()
    for anio in range(desde, hoy.year + 1):
        filas = []
        for mes in range(1, 13):
            if (anio, mes) >= (hoy.year, hoy.month):  # el mes en curso está incompleto
                break
            for variable, (filtro, ap) in GASTOS.items():
                url, f = consulta("municipalidad", {"nivel": "M", **filtro, "mes": str(mes)}, anio, ap)
                filas += [(u, anio * 12 + mes - 1, variable, dev) for u, (_, _, dev) in por_municipalidad(f).items()]
        guardar(con, filas, "MEF Consulta Amigable (devengado del mes)")
        print(f"  MEF {anio}: {len({f[0] for f in filas})} municipalidades, {len(filas)} filas")


# --- JNE: vacancias, suspensiones y convocatorias de reemplazo, leídas de El Peruano -------------------------------
# Las bases del JNE están cerradas a un script: la Plataforma Electoral e Infogob piden captcha y la consulta de
# expedientes (cej.jne.gob.pe) está tras un filtro antibots. Lo que sí es público y abierto es lo que el JNE publica en
# El Peruano: cada resolución con su título ("...vacancia ... alcalde de la Municipalidad Distrital de X, provincia
# de Y, departamento de Z"). La fecha es la de publicación (meses después de la solicitud), no la del pedido.
PERUANO = "https://busquedas.elperuano.pe/"
TARJETA = re.compile(r'text-primary">([^<]*)</p></div>.*?href="/dispositivo/NL/([\d-]+)".*?line-clamp-3" href="[^"]*"[^>]*>([^<]*)</a>', re.S)
LUGAR = re.compile(r"(?:municipalidad|concejo)(?: municipal)? (distrital|provincial) (?:de |del )?(.+?)"
                   r"(?: provincia y departamento (?:de |del )?(.+?)| provincia (?:de |del )?(.+?)"
                   r" (?:y )?departamento (?:de |del )?(.+?)| departamento (?:de |del )?(.+?)|)(?: y | que | en | por |$)")


def municipio(titulo: str) -> tuple[str, bool] | None:
    """Título de una resolución → (ubigeo del distrito, es provincial). La provincial va al distrito capital (..01).
    Sin provincia ni departamento (pasa en los años electorales) solo vale si el nombre es único en el país."""
    t = norm(titulo).replace("provincia constitucional del callao", "provincia y departamento del callao")
    if not (m := LUGAR.search(t)):
        return None
    nivel, nombre, misma, prov, dep, dep_solo = m.groups()
    dep = misma or dep or dep_solo
    if nivel == "provincial":
        codigo, precision = resolver(region=dep, provincia=nombre)
        return (codigo + "01", True) if precision == "provincia" else None
    codigo, precision = resolver(region=dep, provincia=misma or prov, distrito=nombre)
    return (codigo, False) if precision == "distrito" else None


def clases(titulo: str) -> list[str]:
    t = norm(titulo)
    salida = [v for v, clave in (("jne_vacancia", "vacancia"), ("jne_suspension", "suspension"),
                                 ("jne_revocatoria", "revocatoria")) if clave in t]
    if t.startswith("convocan"):  # reemplazo: definitivo (vacancia) o provisional (suspensión o licencia)
        salida.append("jne_convoca_provisional" if "provisional" in t else "jne_convoca")
    return salida


def peruano_dia(dia: date) -> dict:
    """Resoluciones del JNE publicadas ese día: {id del dispositivo: título}. Se pide día por día porque la búsqueda
    de un mes entero se corta: en agosto de 2026 perdía más de la mitad de las del JNE (comparado con el PDF del día)."""
    filas, inicio = {}, 0
    while True:
        for espera in (1, 10, 30, 90):  # pausa cortés; el servidor corta el SSL si se le pide muy seguido
            time.sleep(espera)
            try:
                r = requests.get(PERUANO, headers=UA, timeout=120, params=dict(
                    query="jurado nacional de elecciones", fechaIni=dia.strftime("%Y%m%d"),
                    fechaFin=dia.strftime("%Y%m%d"), tipoPublicacion="NL", ci="ONLY", start=inicio))
                r.raise_for_status()
                break
            except requests.RequestException:
                r = None
        if r is None:
            raise RuntimeError(f"El Peruano sin respuesta: {dia}")
        tarjetas = TARJETA.findall(r.content.decode("utf-8", "replace"))
        filas.update({i: html.unescape(t).strip() for e, i, t in tarjetas if "JURADO NACIONAL DE ELECCIONES" in e})
        if len(tarjetas) < 20:
            return filas
        inicio += 20


def peruano_mes(anio, mes) -> list[list[str]]:
    """Todas las resoluciones del JNE publicadas en el mes: [[id, título]], sin repetir el id. Se guardan en crudos
    (solo títulos). Junta lo leído día por día con la búsqueda mensual de una corrida anterior, si quedó en crudos."""
    carpeta = CRUDOS / "elperuano"
    ruta, mensual = carpeta / f"{anio}{mes:02d}_dias.json", carpeta / f"{anio}{mes:02d}.json"
    filas = dict(json.loads(mensual.read_text(encoding="utf-8"))) if mensual.exists() else {}
    if ruta.exists():
        return sorted(map(list, (filas | dict(json.loads(ruta.read_text(encoding="utf-8")))).items()))
    dias, d = {}, date(anio, mes, 1)
    while d.month == mes and d < date.today():
        dias |= peruano_dia(d)
        d = date.fromordinal(d.toordinal() + 1)
    if (anio, mes) < (date.today().year, date.today().month):  # el mes en curso no se guarda: sigue creciendo
        carpeta.mkdir(parents=True, exist_ok=True)
        ruta.write_text(json.dumps(sorted(map(list, dias.items())), ensure_ascii=False), encoding="utf-8")
    return sorted(map(list, (filas | dias).items()))


def jne(con, desde=2010, anios=None):
    hoy = date.today()
    sin_lugar = total = 0
    for anio in anios or range(desde, hoy.year + 1):
        cuenta = Counter()
        for mes in range(1, 13):
            if (anio, mes) > (hoy.year, hoy.month):
                break
            for _, titulo in peruano_mes(anio, mes):
                total += 1
                if not (c := clases(titulo)):
                    continue
                if not (lugar := municipio(titulo)):
                    sin_lugar += 1
                    continue
                for v in c:
                    cuenta[(lugar[0], anio * 12 + mes - 1, v + "_provincial" * lugar[1])] += 1
        con.execute(ESQUEMA)
        con.execute("DELETE FROM distrito_mes WHERE variable LIKE 'jne_%' AND m / 12 = ?", (anio,))
        guardar(con, [(*k, n) for k, n in cuenta.items()], "JNE en El Peruano (busquedas.elperuano.pe)")
        print(f"  JNE {anio}: {sum(cuenta.values())} conteos en {len({k[0] for k in cuenta})} municipalidades")
    print(f"  {total} resoluciones del JNE leídas; {sin_lugar} con clase y sin municipalidad reconocible")
    revocatoria(con)


# --- ONPE: consultas populares de revocatoria (resultados por mesa en datosabiertos.gob.pe) ------------------------
# Por distrito y mes de la votación: % de SÍ a la revocatoria del alcalde (posición 1 de la cédula) y de los regidores
# (las demás posiciones, sumadas). Los nombres de las autoridades no se leen. La consulta provincial va al distrito
# capital con el sufijo _provincial. Falta la segunda consulta de 2013 (7 de julio, Arequipa, Puno, Cusco, Tacna…):
# su ficha en datosabiertos enlaza por error el archivo de las Nuevas Elecciones Municipales 2014.
ARCHIVOS = "https://www.datosabiertos.gob.pe/sites/default/files/"
REVOCATORIAS = {  # archivo → (anio, mes, provincial)
    "Resultados%20por%20mesa%20CPR2012%20Distrital.csv": (2012, 9, False),
    "Resultados%20por%20mesa%20CPR2012%20Provincial.csv": (2012, 9, True),
    "Resultados%20por%20mesa%20CPR2013%20Distrital.csv": (2013, 3, False),
    "Resultados%20por%20mesa%20CPR2013%20Provincial.zip": (2013, 3, True),  # Lima Metropolitana, 217 MB sin comprimir
    "Resultados%20por%20mesa%20Consulta%20Popular%20de%20Revocatoria%20de%20Autoridades%20Municipales%202017.csv": (2017, 6, False),
    "Resultados%20por%20mesa%20Consulta%20Popular%20de%20Revocatorias%202021.csv": (2021, 10, False),
    "Resultados%20por%20mesa%20de%20la%20Consulta%20Popular%20de%20Revocatoria%202025%C2%A0.csv": (2025, 6, False)}


def resultado_revocatoria(lineas, provincial: bool) -> dict:
    """Líneas del CSV por mesa → {ubigeo INEI: (% SÍ alcalde, número de regidores, % SÍ regidores)}.
    El % es sobre los votos válidos (SÍ + NO); None si no hubo alcalde o regidores en consulta."""
    import csv
    votos, regidores = Counter(), defaultdict(set)
    for f in csv.DictReader(lineas, delimiter=";"):
        codigo, precision = resolver(region=f["DEPARTAMENTO"], provincia=f["PROVINCIA"],
                                     distrito=None if provincial else f["DISTRITO"])
        if precision != ("provincia" if provincial else "distrito"):
            continue
        u, quien = codigo + "01" if provincial else codigo, "alcalde" if f["UBICACION_EN_CEDULA"].strip() == "1" else "regidor"
        if quien == "regidor":
            regidores[u].add(f["UBICACION_EN_CEDULA"].strip())
        votos[(u, quien, "si")] += int(f["VOTOS_SI"] or 0)
        votos[(u, quien, "no")] += int(f["VOTOS_NO"] or 0)
    def pct(u, q):
        validos = votos[(u, q, "si")] + votos[(u, q, "no")]
        return round(100 * votos[(u, q, "si")] / validos, 1) if validos else None
    return {u: (pct(u, "alcalde"), len(regidores[u]), pct(u, "regidor")) for u in {k[0] for k in votos}}


def lineas_onpe(archivo):
    """Archivo de la ONPE (bajado una vez a crudos) → iterador de líneas de texto, también dentro de un zip."""
    import codecs
    import io
    import zipfile
    ruta = CRUDOS / "onpe" / requests.utils.unquote(archivo).replace(" ", "_").replace(chr(160), "")
    if not ruta.exists():
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.with_suffix(".part").write_bytes(requests.get(ARCHIVOS + archivo, headers=UA, timeout=600).content)
        ruta.with_suffix(".part").replace(ruta)
    if ruta.suffix == ".zip":
        z = zipfile.ZipFile(ruta)
        abrir = lambda: z.open(next(n for n in z.namelist() if n.lower().endswith(".csv")))
    else:
        abrir = lambda: ruta.open("rb")
    with abrir() as f:
        bom = f.read(3) == codecs.BOM_UTF8  # desde 2017 vienen en UTF-8 con BOM; antes, en latin-1
    return io.TextIOWrapper(abrir(), encoding="utf-8-sig" if bom else "latin-1")


def revocatoria(con):
    filas = []
    for archivo, (anio, mes, provincial) in REVOCATORIAS.items():
        sufijo, m = "_provincial" * provincial, anio * 12 + mes - 1
        for u, (alcalde, n_reg, reg) in resultado_revocatoria(lineas_onpe(archivo), provincial).items():
            filas += [(u, m, v + sufijo, x) for v, x in (("revocatoria_consulta", 1), ("revocatoria_si_alcalde", alcalde),
                      ("revocatoria_regidores", n_reg), ("revocatoria_si_regidores", reg)) if x is not None]
    con.execute(ESQUEMA)
    con.execute("DELETE FROM distrito_mes WHERE variable LIKE 'revocatoria_%'")
    guardar(con, filas, "ONPE, resultados por mesa de las consultas de revocatoria (datosabiertos.gob.pe)")
    consultas = [f for f in filas if f[2].startswith("revocatoria_consulta")]
    print(f"  Revocatorias: {len(consultas)} consultas, por año {dict(Counter(f[1] // 12 for f in consultas))}")


# --- Contraloría: informes de servicios de control por municipalidad ----------------------------------------------
# El Buscador de Informes de Control responde JSON a un POST, sin sesión ni captcha. Se publican desde 2018 (Ley 30742):
# antes de eso casi no hay. Trae nombres y DNI de los funcionarios con responsabilidad: no se guardan, solo los campos
# de abajo. El mes es el de emisión del informe; el de publicación suele ser el mismo o el siguiente.
CGR = "https://appbp.contraloria.gob.pe/BuscadorCGR/Informes/BusquedaInformesCGR.ashx"
CAMPOS_CGR = ("CodigoInforme", "Entidad", "Departamento", "Provincia", "Distrito", "FechaEmision", "EsConResponsabilidad",
              "Responsabilidad", "ModalidadServicio", "NivelGobierno")
FILTROS_CGR = ("pGeneral pAnio pEntidad pSector pModalidadServicio pReconstruccion pReconstruccionDepa pServicio pDepartamento "
               "pResponsabilidad pCovid pCovidDepa pNivelGobierno pProvincia pDistrito pAnioFinEjec pEsConResponsabilidad "
               "pEvento pOperativo").split()


def cgr_mes(anio, mes) -> list[dict]:
    """Informes publicados en el mes, solo con CAMPOS_CGR (sin personas). Se guardan en crudos."""
    ruta = CRUDOS / "contraloria" / f"{anio}{mes:02d}.json"
    if ruta.exists():
        return json.loads(ruta.read_text(encoding="utf-8"))
    fin = date.fromordinal(date(anio + mes // 12, mes % 12 + 1, 1).toordinal() - 1)
    salida, pagina = [], 1
    while True:
        datos = dict.fromkeys(FILTROS_CGR, "") | dict(
            ActionPage="TransportType", Action="loadInformesElastic", PageSize=1000, PageNumber=pagina,
            pFechaInicio=f"01/{mes:02d}/{anio}", pFechaHasta=fin.strftime("%d/%m/%Y"),
            pFechaInicioEjec="01/01/1800", pFechaFinEjec="01/01/2500")
        for espera in (0, 5, 20, 60):
            time.sleep(espera)
            try:
                lote = requests.post(CGR, data=datos, headers=UA, timeout=300).json()
                break
            except (requests.RequestException, ValueError):
                lote = None
        if lote is None:
            raise RuntimeError(f"Contraloría sin respuesta: {anio}-{mes}")
        salida += [{k: x.get(k) for k in CAMPOS_CGR} for x in lote]
        if not lote or pagina >= int(lote[0]["TotalPages"]):
            break
        pagina += 1
    if (anio, mes) < (date.today().year, date.today().month):
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(json.dumps(salida, ensure_ascii=False), encoding="utf-8")
    return salida


def filas_cgr(informes) -> list[tuple]:
    """Informes → [(ubigeo, m, variable, n)] de las municipalidades. La provincial lleva el sufijo _provincial."""
    cuenta, vistos = Counter(), set()
    for x in informes:
        entidad = norm(x["Entidad"])
        if x["CodigoInforme"] in vistos or not entidad.startswith("municipalidad") or not x["FechaEmision"]:
            continue
        vistos.add(x["CodigoInforme"])
        ubigeo, precision = resolver(region=x["Departamento"], provincia=x["Provincia"], distrito=x["Distrito"])
        if precision != "distrito":
            continue
        anio, mes = map(int, x["FechaEmision"].split("/")[:2])
        if not 2000 <= anio <= date.today().year:  # hay fechas mal digitadas (p. ej. año 8205)
            continue
        sufijo = "_provincial" * entidad.startswith("municipalidad provincial")
        clases = ["cgr_informes"] + ["cgr_con_responsabilidad"] * (x["EsConResponsabilidad"] == "S")             + ["cgr_penal"] * ("PENAL" in (x["Responsabilidad"] or ""))
        for v in clases:
            cuenta[(ubigeo, anio * 12 + mes - 1, v + sufijo)] += 1
    return [(*k, n) for k, n in cuenta.items()]


def contraloria(con, desde=2017):
    hoy, informes = date.today(), []
    for anio in range(desde, hoy.year + 1):
        for mes in range(1, 13):
            if (anio, mes) <= (hoy.year, hoy.month):
                informes += cgr_mes(anio, mes)
        print(f"  Contraloría {anio}: {len(informes)} informes publicados acumulados")
    filas = filas_cgr(informes)
    guardar(con, filas, "Contraloría, Buscador de Informes de Control (appbp.contraloria.gob.pe)")
    print(f"  {len(filas)} filas en {len({f[0] for f in filas})} distritos")


# --- Estados de emergencia por orden interno: decretos supremos de la PCM en El Peruano ----------------------------
# Los pide el Mininter con un informe de la Policía cuando hay bloqueos, conflicto o crimen. El artículo 1 dice desde
# cuándo, por cuántos días, dónde y para qué ("para hacer frente a la afectación del orden interno por..."). Se separa
# conflicto social de crimen por reglas; los de lluvias, heladas o peligro inminente no son de orden interno.
ORDEN = re.compile(r"orden interno|grupos hostiles|organizaciones criminales")
CONFLICTO_DS = re.compile(r"conflict|\bparo|bloque|protest|\bmoviliza|toma de (local|instalac|carretera|v[ií]a)|disturbio|"
                          r"manifestaci|comunidades (campesinas|nativas)|grave alteraci[oó]n del orden|actos de violencia de la poblaci")
CRIMEN_DS = re.compile(r"criminal|delincuen|miner[ií]a ilegal|extorsi|sicariato|narcotr|terroris|tr[aá]fico il[ií]cito|"
                       r"remanentes|sendero|tala ilegal|crimen organizado|grupos hostiles")
LISTA = re.compile(r",\s*|\s+y\s+")


def lugares_decreto(art1: str) -> set[str]:
    """Distritos (ubigeo) que nombra el artículo 1. Se parte en tramos "en el distrito.../en la provincia...": la
    provincia con que empieza un tramo entra entera; la que sigue a un distrito ("de la provincia de Y") solo lo ubica.
    Si un tramo no nombra distritos ni provincias, entra el departamento entero."""
    from tremor.lugares import catalogo
    regiones, provincias, distritos, _ = catalogo()
    t = norm(art1.replace(";", " PUNTOYCOMA ").replace(",", " y "))
    t = t.replace("provincia constitucional del callao", "provincia de callao").replace("lima metropolitana", "la provincia de lima")
    deps = {c for n, c in regiones.items() if re.search(rf"\b{n}\b", t)}  # solo acota la búsqueda: sobrar no estorba

    def nombres(pat, s, tabla):  # el nombre conocido más largo al inicio de cada trozo ("leoncio prado circunscripciones")
        trozos = [n.split() for m in re.finditer(pat, s) for n in LISTA.split(m[1])]
        return [n for w in trozos for n in [next((" ".join(w[:k]) for k in range(len(w), 0, -1) if " ".join(w[:k]) in tabla), None)] if n]
    hasta = r"(?= de la provincia| de las provincias| del? departamento| y departamento| de los departamentos| en | de la region| los distritos| el distrito|$)"
    prov = lambda pat, s: {c for n in nombres(pat, s, provincias) for c in provincias[n] if c[:2] in deps}
    salida = set()
    corta = lambda s: re.split(r" para | a fin | con la finalidad| la policia| las fuerzas", s)[0]
    for tramo in (u for s in t.split(" puntoycoma ") for u in re.split(r" (?:en|por|emergencia|dias) (?=(?:el|los|la|las) (?:distritos?|provincias?) )", re.sub(r"^(?:y )?en ", "", corta(s)))):
        enteras = prov(r"^(?:\w+ )*?(?:la|las) provincias? del? (.+?)" + hasta, tramo) if re.match(r"(?:la|las) provincia", tramo) else set()
        ubica = prov(r"de (?:la|las) provincias? del? (.+?)" + hasta, tramo)
        ds = nombres(r"distritos? (?:fronterizos? )?del? (.+?)" + hasta, tramo, distritos)
        salida |= {u for c in distritos.values() for u in c if u[:4] in enteras}
        salida |= {u for n in ds for u in distritos[n] if u[:2] in deps and (u[:4] in ubica or not ubica)}
        if not enteras and not ds and not re.search(r"distrito|provincia", tramo):
            salida |= {u for c in distritos.values() for u in c if u[:2] in {regiones[n] for n in nombres(r"departamentos? (?:del? )?(.+?)$", tramo, regiones)}}
    return salida


def lugares_anexo(anexo: str) -> set[str]:
    """Distritos del anexo de un decreto ("en los distritos que se indican en el Anexo"): una tabla numerada con distrito,
    provincia y departamento, donde la provincia y el departamento solo se escriben en la primera fila de su grupo.
    Un nombre repetido en el país se resuelve con la provincia vigente; si aun así es ambiguo, no entra."""
    from tremor.lugares import catalogo
    regiones, provincias, distritos, _ = catalogo()
    t = norm(anexo).replace("kimbiri", "quimbiri").replace("tintaypuncu", "tintay puncu")  # como los escribe el INEI
    deps = {c for n, c in regiones.items() if re.search(rf"\b{n}\b", t)}
    largo = lambda w, tabla: next((" ".join(w[a:a + k]) for a in range(min(2, len(w))) for k in range(min(5, len(w) - a), 0, -1)
                                   if " ".join(w[a:a + k]) in tabla), None)
    salida, prov = set(), set()
    for fila in re.split(r" \d{1,3} (?=[a-z])", " " + t.split(" total ")[0])[1:]:  # la cabecera queda fuera
        w = fila.split()
        d = largo(w, distritos)
        resto = fila.replace(d, " ", 1) if d else fila
        p = largo(resto.split(), provincias)
        if p and {c for c in provincias[p] if c[:2] in deps}:
            prov = {c for c in provincias[p] if c[:2] in deps}
        cand = {u for u in distritos.get(d, ()) if u[:2] in deps}
        cand = {u for u in cand if u[:4] in prov} or (cand if len(cand) == 1 else set())
        salida |= cand
    return salida


def leer_decreto(texto: str) -> dict | None:
    """De un decreto supremo de estado de emergencia: causa (crimen si lo nombra; si no, conflicto), inicio, días y distritos.
    None si no es de orden interno (lluvias, heladas, peligro inminente)."""
    k = max(texto.find("DECRETA:"), texto.find("DECRETA :"))
    if k < 0:
        return None
    art1 = re.split(r"Art[ií]culo 2\b", texto[k:k + 2500])[0]
    # de orden interno: lo dice el artículo 1 o, en los antiguos ("Prorrogar el Estado de Emergencia en el distrito de
    # Cocachacra"), el decreto suspende derechos constitucionales. Invocar el artículo 137 no basta: antes de 2011
    # también lo invocaban los de heladas, sismos y plagas. La emergencia nacional del COVID suspende derechos y no cuenta.
    cuerpo = texto[max(0, k - 5000):k + 4000]
    # no declara ni prorroga nada en un territorio: precisiones a otro decreto y la emergencia en los penales
    if re.search(r"prec[ií]s|establecimientos penitenciarios", art1[:400], re.I):
        return None
    if re.search(r"covid|emergencia nacional|emergencia sanitaria", cuerpo, re.I) or not (
            ORDEN.search(art1.lower()) or re.search(r"suspen\w+ (?:d?el ejercicio de )?(?:los )?derechos constitucionales", cuerpo, re.I)):
        return None
    c = texto.rfind("CONSIDERANDO", 0, k)
    motivo = (texto[c if c >= 0 else max(0, k - 2500):k] + art1).lower()  # el PDF trae otras normas antes
    # frases de cajón que citan casi todos (la finalidad de la Policía y el D. Leg. 1095): no son el motivo. Sin
    # quitarlas, la emergencia de Puno por las protestas de 2023 salía como crimen
    motivo = re.sub(r"prevenir, investigar y combatir la delincuencia|en (?:los )?casos de tr[aá]fico il[ií]cito de drogas, "
                    r"terrorismo [oy] protecci[oó]n de instalaciones estrat[eé]gicas", " ", motivo)
    crimen = CRIMEN_DS.search(motivo)
    causas = {c for c, si in (("crimen", crimen), ("conflicto", CONFLICTO_DS.search(motivo))) if si}
    if not causas:  # sin motivo nombrado: la prórroga hereda la causa del decreto anterior; la declaratoria es conflicto
        causas = {"hereda"} if re.search(r"prorrog", art1.lower()) else {"conflicto"}
    inicio = re.search(r"a partir del? (\d{1,2}) de (\w+) de (\d{4})", norm(art1))
    pub = re.search(r"Fecha de publicaci[oó]n: (\d\d)/(\d\d)/(\d{4})", texto)
    meses = "enero febrero marzo abril mayo junio julio agosto setiembre octubre noviembre diciembre".split()
    if inicio and inicio[2].replace("septiembre", "setiembre") in meses:
        f = date(int(inicio[3]), meses.index(inicio[2].replace("septiembre", "setiembre")) + 1, int(inicio[1]))
    elif pub:
        f = date(int(pub[3]), int(pub[2]), int(pub[1]))
    else:
        return None
    dias = re.search(r"\((\d+)\) d[ií]as", art1)
    lugares = lugares_decreto(art1)
    if not lugares and "ANEXO:" in texto:  # "en los distritos que se indican en el Anexo"
        lugares = lugares_anexo(texto.split("ANEXO:", 1)[1])
    # sin distritos porque nombra la carretera: emergencias() pone los de la vía (tabla distrito_corredor). La
    # emergencia en toda la Red Vial Nacional queda sin distritos: marcaría medio país y no distingue a nadie.
    vias = "sur" if not lugares and re.search(r"corredor vial sur", art1, re.I) else None
    return {"causas": causas, "inicio": f, "dias": int(dias[1]) if dias else 30, "lugares": lugares, "vias": vias}


def _peruano(binario=False, **params):
    ruta = params.pop("ruta", "")
    for espera in (1, 10, 30, 90):  # el servidor corta el SSL si se le pide muy seguido
        time.sleep(espera)
        try:
            r = requests.get(PERUANO + ruta, headers=UA, timeout=120, params=params)
            r.raise_for_status()
            if binario:
                return r.content
            try:
                return r.content.decode("utf-8")
            except UnicodeDecodeError:  # los decretos antiguos traen el cuerpo en latin-1
                return r.content.decode("cp1252", "replace")
        except requests.RequestException:
            pass
    raise RuntimeError(f"El Peruano sin respuesta: {params}")


def decretos_mes(m: int) -> dict:
    """{id: título} de los decretos de estado de emergencia publicados en el mes m (anio*12 + mes - 1). Se pagina
    mientras salgan títulos de emergencia (antes de ~2012 la frase exacta no filtra y el resto es ruido). Se filtra
    por el título y no por la institución: los de 2026 salen como Secretaría del Consejo de Ministros, no como PCM."""
    ini = date(m // 12, m % 12 + 1, 1)
    fin = date((m + 1) // 12, (m + 1) % 12 + 1, 1) - timedelta(1)
    filas = {}
    for inicio in range(0, 200, 20):
        tarjetas = TARJETA.findall(_peruano(query='"estado de emergencia"', tipoPublicacion="NL", ci="ONLY", start=inicio,
                                            fechaIni=ini.strftime("%Y%m%d"), fechaFin=fin.strftime("%Y%m%d")))
        nuevas = {i: html.unescape(t).strip() for e, i, t in tarjetas if re.search(r"[Ee]stado de [Ee]mergencia", t)}
        filas |= nuevas
        if len(tarjetas) < 20 or not nuevas:
            break
    return filas


def texto_decreto(i, titulo="") -> str:
    """Los considerandos y los artículos de un decreto, con su fecha de publicación. El PDF es la página entera del
    diario, con otras normas: se lee desde la última vez que aparece el título (la primera es el sumario)."""
    pagina = _peruano(ruta=f"dispositivo/NL/{i}")
    t = html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", pagina)))
    pdf = re.search(r"/api/archivo/file/[\w-]+/\*/[\w-]+\.pdf", pagina)
    if ("DECRETA" not in t or "�" in t) and pdf:  # sin texto o con tildes rotas: el PDF de la norma
        import pymupdf
        with pymupdf.open(stream=_peruano(binario=True, ruta=pdf[0][1:]), filetype="pdf") as doc:
            cuerpo = " ".join(p.get_text() for p in doc)
        cuerpo = re.sub(r"-\s+(?=[a-záéíóúñ])", "", re.sub(r"\s+", " ", cuerpo))
        aqui = [m.start() for m in re.finditer(r"\W+".join(map(re.escape, titulo.split()[:8])), cuerpo, re.I)] if titulo else []
        t = (re.search(r"Fecha de publicaci[oó]n: \d\d/\d\d/\d{4}", t) or [""])[0] + " " + cuerpo[aqui[-1] if aqui else 0:]
    k = max(t.find("DECRETA:"), t.find("DECRETA :"))
    pub = re.search(r"Fecha de publicaci[oó]n: \d\d/\d\d/\d{4}", t)
    firma = max(k, t.find("Dado en la Casa de Gobierno", k))
    a = re.search("anexo", t[firma:], re.I)  # la tabla de distritos, tras las firmas
    anexo = " ANEXO: " + t[firma + a.start():firma + a.start() + 6000] if a else ""
    return (pub[0] + " " if pub else "") + t[max(0, k - 8000):k + 2500] + anexo if k >= 0 else ""


def emergencias(con, desde=2006, max_meses=24, releer=False):
    """Lee de a max_meses los meses aún no buscados (más el actual y el anterior, que siguen creciendo), guarda cada
    decreto en `decreto_emergencia` y rehace en distrito_mes emergencia_conflicto y emergencia_crimen: 1 en cada mes
    que el distrito estuvo bajo estado de emergencia por esa causa (un decreto puede tener las dos)."""
    con.execute("""CREATE TABLE IF NOT EXISTS decreto_emergencia (id TEXT PRIMARY KEY, titulo TEXT, causas TEXT,
                   inicio TEXT, dias INTEGER, lugares TEXT)""")
    con.execute("CREATE TABLE IF NOT EXISTS decreto_emergencia_mes (m INTEGER PRIMARY KEY)")
    def fila(i, titulo):  # (causas, inicio, días, lugares) como se guardan; las carreteras, por sus distritos
        d = leer_decreto(texto_decreto(i, titulo)) or {}
        if d.get("vias"):
            try:
                d["lugares"] = {u for (u,) in con.execute("SELECT DISTINCT ubigeo FROM distrito_corredor WHERE corredor = 'Corredor Minero del Sur'")}
            except sqlite3.OperationalError:  # sin la tabla (python -m tremor.distritos vias)
                pass
        return (",".join(sorted(d.get("causas", ()))) or None, str(d.get("inicio") or "") or None, d.get("dias"),
                json.dumps(sorted(d.get("lugares", ()))))
    if releer:  # tras cambiar una regla: vuelve a leer con las reglas de hoy los que tienen causa
        for i, titulo in con.execute("SELECT id, titulo FROM decreto_emergencia WHERE causas IS NOT NULL").fetchall():
            con.execute("UPDATE decreto_emergencia SET causas = ?, inicio = ?, dias = ?, lugares = ? WHERE id = ?", (*fila(i, titulo), i))
            con.commit()
    hoy = date.today().year * 12 + date.today().month - 1
    hechos = {m for (m,) in con.execute("SELECT m FROM decreto_emergencia_mes")}
    pendientes = [m for m in range(desde * 12, hoy - 1) if m not in hechos][:max_meses] + [hoy - 1, hoy]
    vistos = {i for (i,) in con.execute("SELECT id FROM decreto_emergencia")}
    for m in pendientes:
        for i, titulo in decretos_mes(m).items():
            if i in vistos:
                continue
            con.execute("INSERT OR REPLACE INTO decreto_emergencia VALUES (?, ?, ?, ?, ?, ?)", (i, titulo, *fila(i, titulo)))
        if m < hoy - 1:
            con.execute("INSERT OR IGNORE INTO decreto_emergencia_mes VALUES (?)", (m,))
        con.commit()
        print(f"  {m // 12}-{m % 12 + 1:02d} buscado", flush=True)
    filas, ultima = set(), {}  # ultima: distrito → causas del último decreto que lo nombró
    for causas, inicio, dias, lugares in con.execute("SELECT causas, inicio, dias, lugares FROM decreto_emergencia "
                                                     "WHERE causas IS NOT NULL ORDER BY inicio"):
        lugares, f = json.loads(lugares), date.fromisoformat(inicio)
        if causas == "hereda":
            previas = Counter(ultima.get(u, "conflicto") for u in lugares)
            causas = previas.most_common(1)[0][0] if previas else "conflicto"
        ultima |= dict.fromkeys(lugares, causas)
        fin = date.fromordinal(f.toordinal() + dias - 1)
        filas |= {(u, m, f"emergencia_{c}", 1.0) for u in lugares
                  for m in range(f.year * 12 + f.month - 1, fin.year * 12 + fin.month) for c in causas.split(",")}
    con.execute(ESQUEMA)
    con.execute("DELETE FROM distrito_mes WHERE variable LIKE 'emergencia_%'")
    guardar(con, sorted(filas), "El Peruano, decretos supremos de estado de emergencia (PCM)")
    print(f"  {len(filas)} filas distrito-mes en {len({f[0] for f in filas})} distritos")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(prog="python -m tremor.gobierno")
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("mef_mensual"); m.add_argument("--desde", type=int, default=2010)
    j = sub.add_parser("jne"); j.add_argument("--desde", type=int, default=2010); j.add_argument("--anios", type=int, nargs="*")
    c = sub.add_parser("contraloria"); c.add_argument("--desde", type=int, default=2017)
    e = sub.add_parser("emergencias"); e.add_argument("--desde", type=int, default=2006); e.add_argument("--max-meses", type=int, default=24)
    e.add_argument("--releer", action="store_true")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
    {"mef_mensual": lambda con: mef_mensual(con, a.desde), "jne": lambda con: jne(con, a.desde, a.anios),
     "contraloria": lambda con: contraloria(con, a.desde), "emergencias": lambda con: emergencias(con, a.desde, a.max_meses, a.releer)}[a.cmd](conectar())
