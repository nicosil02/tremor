"""Fichas de conflicto de los informes trimestrales de la Oficina General de Gestión Social del MINEM.

Solo los informes de 2014-T4 a 2018-T4 traen una ficha por caso (nombre, ubicación, actores, problemática,
hechos del trimestre, situación); los anteriores son narrativos y después de 2018 no se publicó más.
`python -m tremor.minem_social`
"""
import re
import sys
import time
from urllib.parse import unquote

import pymupdf
import requests

from tremor.db import DATOS, conectar
from tremor.lugares import norm, resolver
from tremor.territorio import UA

PAGINAS = {2018: 4719996, 2017: 4720061, 2016: 4720089, 2015: 4720094, 2014: 4720185}
CRUDOS = DATOS / "crudos" / "minem_social"
MESES = "ENERO|FEBRERO|MARZO|ABRIL|MAYO|JUNIO|JULIO|AGOSTO|SETIEMBRE|SEPTIEMBRE|OCTUBRE|NOVIEMBRE|DICIEMBRE"
TRIMESTRE = {"enero": 1, "abril": 2, "julio": 3, "octubre": 4}
# rótulos de la ficha: al inicio de línea, mayúsculas o no, seguidos de ":" o salto de línea
FIN_ROT = r"\s*(?::|\n)"
UBIC = r"\n\s*ubicaci[oó]n\b"
ACT = r"\n\s*actores" + FIN_ROT
PROB = r"\n\s*(?:problem[aá]tica|materia de conflicto)" + FIN_ROT
HECHOS = rf"\n\s*(?:descripci[oó]n\s+de\s+los\s+hechos|acciones|evoluci[oó]n[^\n]*|(?-i:(?:{MESES})\b)|(?:{MESES})\b[^\n]{{0,25}}\n)"
SIT = r"\n\s*(?:(?:situaci[oó]n|estado)\s+actual[^\n:]{0,20}|seguimiento|prospectiva|proyecc+i[oó]n)" + FIN_ROT
CASO = r"(?im)^[ \t•\d.-]*nombre\s+del\s+caso\s*:?"
FIN = r"(?m)^\s*\d\.-?\s+INVERSI[OÓ]N SOCIAL"  # sección que sigue a las fichas
ROTULO = r"(?-i:\n\s*(?:[A-H]\.\s+)?(?:ZONA [A-Z]+|REGI[OÓ]N +[A-ZÁÉÍÓÚÑ]+(?: [A-ZÁÉÍÓÚÑ]+)*|OTROS CASOS[^\n]*|\d\.-?\s+MANEJO[^\n]*|\d\.\d\s+CASO [^\n]*)\s*(?:\n|$))"  # títulos entre fichas
# nombres de los informes → nombre oficial (erratas, grafías viejas y centros poblados conocidos → su distrito)
ERRATAS = {"chalhuahuacho": "Challhuahuacho", "echarati": "Echarate", "ollaechea": "Ollachea", "lotero": "Loreto",
           "loreto nauta": "Loreto", "la encanada": "Encañada", "tambogrande": "Tambo Grande", "saccsamarca": "Sacsamarca",
           "pueblo nuevo de colan": "Colán", "huayhuay": "Huay-Huay", "pichanaki": "Pichanaqui", "parathia": "Paratia",
           "paragsha": "Simón Bolívar", "toquepala": "Ilabaya", "santa ana quillabamba": "Santa Ana"}
ESQUEMA = """CREATE TABLE IF NOT EXISTS minem_caso (
    trimestre TEXT, orden INTEGER, nombre TEXT, departamento TEXT, provincia TEXT, distrito TEXT, ubigeo TEXT,
    actores TEXT, problematica TEXT, situacion TEXT, enlace TEXT, PRIMARY KEY (trimestre, orden))"""


def informes():
    """[(trimestre 'YYYY-Qn', url del PDF)] desde 2014-Q4, raspando la página de cada año."""
    salida = []
    for anio, i in PAGINAS.items():
        h = requests.get(f"https://www.gob.pe/institucion/minem/informes-publicaciones/{i}-informe-trimestral-{anio}",
                         headers=UA, timeout=60).text
        for url in sorted(set(re.findall(r'https://cdn\.www\.gob\.pe/uploads/document/file/\d+/Informe[^"\s<>]+\.pdf', h))):
            mes = re.search(r"\((\w+)", unquote(url)).group(1).lower()
            t = f"{anio}-Q{TRIMESTRE[mes]}"
            if t >= "2014-Q4":
                salida.append((t, url))
        time.sleep(1)
    return sorted(salida)


def pdf(url):
    """Descarga una vez y guarda en crudos/ (nombre = id del archivo en gob.pe)."""
    ruta = CRUDOS / (url.split("/")[-2] + ".pdf")
    if not ruta.exists():
        CRUDOS.mkdir(parents=True, exist_ok=True)
        ruta.write_bytes(requests.get(url, headers=UA, timeout=180).content)
        time.sleep(1)
    return ruta


def texto(ruta):
    """Texto del PDF sin membretes (lema del año, decenio) ni números de página."""
    with pymupdf.open(ruta) as doc:
        t = "\n".join(p.get_text() for p in doc)
    t = re.sub("[\uf0a7\uf0b7\uf0d8\u0335]", "•", t)  # viñetas de Symbol y rayas sueltas
    return "\n".join(l for l in t.split("\n")
                     if not re.fullmatch(r"\s*\d*\s*|\s*[\"“]?\s*(?:\d{4}\s*-\s*\d{4}\s+Decenio|A[ñn]o de).*", l))


def limpio(s):
    return " ".join(s.split()).strip(" :.,;-–")


def corte(s, *patrones):
    """Posición del primer rótulo que aparezca (o el final)."""
    pos = [m.start() for p in patrones if (m := re.search(p, s, re.I))]
    return min(pos, default=len(s))


def ubicacion(s):
    """(departamento, provincia, distrito) del bloque de ubicación; distrito trae los centros poblados aparte."""
    partes = re.split(r"\b(departamentos?|regi[oó]n|provincias?|distritos?|centros?\s+poblados?|localidad(?:es)?|anexos?|caser[ií]os?"
                      r"|c\.?\s*campesinas?|comunidad(?:es)?(?:\s+campesinas?)?|proyectos?|empresa)\b", s or "", flags=re.I)
    campos = {}
    for rot, val in zip(partes[1::2], partes[2::2]):
        clave = rot.lower()[:4]
        if clave in ("depa", "regi"):
            clave = "depa"
        campos.setdefault(clave, re.sub(r"^de\s+|\s+de(?:\s+la)?$", "", limpio(val)))  # "provincias de Satipo de la Región Junín"
    return campos.get("depa"), campos.get("prov"), campos.get("dist")


def lista(s):
    """Nombres sueltos de una lista ("Ayabaca y Huancabamba", "Huarmey (capital)"), con las erratas corregidas."""
    nombres = (limpio(x) for x in re.split(r",|;|/|\(|\)|\.\s|\s[-–]\s|\by\b|\be\b|\ben\b", s or ""))
    return [ERRATAS.get(norm(x), x) for x in nombres if x]


def ubigeo(dep, prov, dist):
    """Primer distrito resoluble a nivel distrital; si ninguno, el mejor código grueso."""
    deps, provs = lista(dep) or [None], lista(prov) or [None]
    pares = [(r, p) for r in deps for p in provs + [None]] + [(None, p) for p in provs if p]  # departamento errado
    for d in lista(dist):
        for r, p in pares:
            cod, prec = resolver(r, p, d)
            if prec == "distrito":
                return cod
    return resolver(deps[0], provs[0])[0]


def fichas(t):
    """Una fila por cada 'NOMBRE DEL CASO' del texto. Cada campo va de su rótulo al rótulo siguiente."""
    filas = []
    t = t[:corte(t[(i := corte(t, CASO)):], FIN) + i]
    for bloque in re.split(CASO, t)[1:]:
        bloque = bloque[:corte(bloque, ROTULO)]
        pos = {k: corte(bloque, x) for k, x in (("u", UBIC), ("a", ACT), ("p", PROB), ("h", HECHOS), ("s", SIT))}

        def campo(k, rotulo, largo=1500):
            ini = pos[k]
            fin = min([v for v in pos.values() if v > ini] + [len(bloque)])
            return limpio(re.sub(rotulo, "", bloque[ini:fin], count=1, flags=re.I))[:largo] or None

        cabeza = bloque[:min(pos.values())]
        dep, prov, dist = ubicacion(campo("u", UBIC + r"(?:\s+geogr[aá]fica)?") or cabeza)  # sin rótulo: va en el título
        filas.append({
            "nombre": limpio(cabeza)[:300], "departamento": dep, "provincia": prov, "distrito": dist,
            "ubigeo": ubigeo(dep, prov, dist),
            "actores": (campo("a", ACT) or "").replace("•", ";").strip("; ") or None,
            "problematica": campo("p", PROB),
            # situación actual y seguimiento hasta el fin de la ficha; si no hay, lo último de los hechos
            "situacion": campo("s", SIT) or (limpio(bloque[pos["h"]:])[-1500:] or None),
        })
    return filas


def cargar(con):
    con.execute(ESQUEMA)
    for t, url in informes():
        filas = fichas(texto(pdf(url)))  # un PDF a la vez: la memoria es poca
        con.execute("DELETE FROM minem_caso WHERE trimestre = ?", (t,))
        con.executemany("INSERT INTO minem_caso VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                        [(t, i, f["nombre"], f["departamento"], f["provincia"], f["distrito"], f["ubigeo"],
                          f["actores"], f["problematica"], f["situacion"], url) for i, f in enumerate(filas, 1)])
        print(t, len(filas), "casos", flush=True)
    con.commit()  # un solo commit: otro proceso escribe en la misma base


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    cargar(conectar())
