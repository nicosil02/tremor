"""Nombres de lugar → ubigeo (INEI 2023, catálogo de la EGPP en ubigeo.csv). Research R3 de 002.

El código queda al nivel que se pudo precisar: "21" departamento, "2105" provincia, "210501" distrito.
"""
import csv
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

ALIAS = {  # nombres comunes en prensa que no son el nombre oficial
    "lima metropolitana": ("provincia", "1501"), "lima provincias": ("region", "15"),
    "cuzco": ("region", "08"), "ancash": ("region", "02"), "region lima": ("region", "15"),
}


def norm(s) -> str:
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"^(?:region|departamento|provincia|distrito|dpto\.?|prov\.?)\s+(?:de\s+)?", "", s.strip())
    return " ".join(re.sub(r"[^a-z0-9 ]+", " ", s).split())


@lru_cache(maxsize=1)
def catalogo():
    regiones, provincias, distritos, nombres = {}, {}, {}, {}
    with open(Path(__file__).with_name("ubigeo.csv"), encoding="utf-8") as f:
        for r in csv.DictReader(f):
            u = r["ubigeo"]
            regiones[norm(r["region"])] = u[:2]
            provincias.setdefault(norm(r["provincia"]), set()).add(u[:4])
            distritos.setdefault(norm(r["distrito"]), set()).add(u)
            nombres[u[:2]], nombres[u[:4]], nombres[u] = r["region"], r["provincia"], r["distrito"]
    return regiones, provincias, distritos, nombres


PRECISION = {2: "departamento", 4: "provincia", 6: "distrito"}


def _region(nombre):
    n = norm(nombre)
    if n in ALIAS and ALIAS[n][0] == "region":
        return ALIAS[n][1]
    return catalogo()[0].get(n)


def resolver(region=None, provincia=None, distrito=None, localidad=None, pista=None):
    """Devuelve (código, precisión) o (None, None). `pista` es un departamento conocido por contexto
    (p. ej. el de la búsqueda); solo desambigua, no se devuelve si la nota no nombra ningún lugar."""
    regiones, provincias, distritos, _ = catalogo()
    r = _region(region)
    contexto = r or _region(pista)
    p = None
    if provincia:
        n = norm(provincia)
        if n in ALIAS and ALIAS[n][0] == "provincia":
            p = ALIAS[n][1]
        else:
            cand = {c for c in provincias.get(n, ()) if not contexto or c.startswith(contexto)}
            p = cand.pop() if len(cand) == 1 else None
    for nombre in (distrito, localidad):
        if not nombre:
            continue
        cand = {c for c in distritos.get(norm(nombre), ())
                if (not p or c.startswith(p)) and (not contexto or c.startswith(contexto))}
        if len(cand) == 1:
            return cand.pop(), "distrito"
        if not distrito and not p and norm(nombre) in provincias:  # la "localidad" es una provincia
            cand = {c for c in provincias[norm(nombre)] if not contexto or c.startswith(contexto)}
            if len(cand) == 1:
                return cand.pop(), "provincia"
    if p:
        return p, "provincia"
    if r:
        return r, "departamento"
    return None, None


def nombre(codigo) -> str | None:
    return catalogo()[3].get(codigo)
