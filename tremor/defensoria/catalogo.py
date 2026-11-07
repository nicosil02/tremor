"""Catálogo de reportes de conflictos sociales: descubrir, completar faltantes y descargar.

Historia 1 de specs/001-recolector-defensoria/spec.md. La identidad definitiva de cada reporte se
lee de su portada (Historia 2); aquí el número que sale del título o de la URL es solo una pista
para saber qué falta.
"""
import hashlib
import io
import re
import time
import zipfile
from urllib.parse import unquote

import requests
from bs4 import BeautifulSoup

from tremor.db import DATOS, ahora

LISTADO = "https://www.defensoria.gob.pe/categorias_de_documentos/reportes/"
CDX = "https://web.archive.org/cdx/search/cdx"
CRUDOS = DATOS / "crudos" / "defensoria"
PAUSA = 0.7  # segundos entre solicitudes al sitio de la Defensoría

_sesion = requests.Session()
_sesion.headers["User-Agent"] = "Mozilla/5.0 (Tremor; recolector de datos públicos)"

# Títulos que dicen "conflicto" pero no son el reporte mensual.
NO_ES_MENSUAL = re.compile(r"crisis pol[ií]tica|personas (heridas|fallecidas)", re.I)


def _get(url: str, timeout: int = 60) -> requests.Response:
    for intento in range(3):
        try:
            r = _sesion.get(url, timeout=timeout)
            if r.status_code < 500:
                return r
        except requests.RequestException:
            if intento == 2:
                raise
        time.sleep(3 * (intento + 1))
    r.raise_for_status()
    return r


def num_pista(titulo: str, url: str) -> int | None:
    """Número de reporte según el título o, si no lo trae, según el nombre del archivo."""
    m = re.search(r"\bn\.?\s*[°ºo]?\s*(\d{1,3})\b", titulo or "", re.I)
    if m:
        return int(m.group(1))
    archivo = unquote(url.rsplit("/", 1)[-1])
    if re.search(r"cronolog", archivo, re.I):  # anexos de cronología, no son reportes
        return None
    m = re.search(r"(?:sociales|conflictos|RCS|reporte|N)[-_ .°º]*(\d{2,3})(?!\d)", archivo, re.I)
    return int(m.group(1)) if m else None


def es_reporte_mensual(titulo: str, url: str) -> bool:
    texto = f"{titulo} {unquote(url)}"
    # "/Downloads/conflictos/" es la carpeta de reportes de la web antigua.
    patron = r"conflictos?[-_ ]sociales|RCS|/Downloads/conflictos/"
    return bool(re.search(patron, texto, re.I)) and not NO_ES_MENSUAL.search(texto)


def _tarjetas(html: str):
    sopa = BeautifulSoup(html, "html.parser")
    for cuerpo in sopa.select("div.card-body"):
        enlace, titulo = cuerpo.find("a", href=True), cuerpo.select_one(".card-title")
        if not enlace or not titulo:
            continue
        fecha = cuerpo.select_one(".card-subtitle")
        yield {
            "url": enlace["href"].strip(),
            "titulo": titulo.get_text(" ", strip=True),
            "fecha": fecha.get_text(" ", strip=True) if fecha else None,
        }


def descubrir(con, completo: bool = False) -> int:
    """Recorre el listado oficial. En modo incremental se detiene en la primera página sin novedades."""
    nuevos, pagina = 0, 1
    while True:
        url = LISTADO + (f"page/{pagina}/" if pagina > 1 else "")
        r = _get(url)
        if r.status_code == 404:
            break
        tarjetas = list(_tarjetas(r.text))
        if not tarjetas:
            break
        nuevos_pagina = 0
        for t in tarjetas:
            if not es_reporte_mensual(t["titulo"], t["url"]):
                continue
            formato = t["url"].rsplit(".", 1)[-1].lower()
            cur = con.execute(
                "INSERT OR IGNORE INTO documento (url, fuente, titulo, fecha_publicacion, formato,"
                " num_titulo, descubierto_en) VALUES (?, 'listado', ?, ?, ?, ?, ?)",
                (t["url"], t["titulo"], t["fecha"], formato, num_pista(t["titulo"], t["url"]), ahora()),
            )
            nuevos_pagina += cur.rowcount
        con.commit()
        nuevos += nuevos_pagina
        if not completo and nuevos_pagina == 0:
            break
        pagina += 1
        time.sleep(PAUSA)
    return nuevos


def numeros_conocidos(con) -> set[int]:
    filas = con.execute("SELECT COALESCE(reporte_num, num_titulo) FROM documento WHERE COALESCE(reporte_num, num_titulo) IS NOT NULL")
    return {f[0] for f in filas}


def faltantes(con) -> list[int]:
    conocidos = numeros_conocidos(con)
    return [n for n in range(1, max(conocidos, default=0) + 1) if n not in conocidos]


# Rutas de la web antigua y nueva donde el Wayback Machine guarda reportes.
# El CDX solo admite comodín al final, así que el nombre se filtra con una expresión regular.
PATRONES_WAYBACK = [
    "defensoria.gob.pe/modules/Downloads/conflictos/",
    "defensoria.gob.pe/wp-content/uploads/",
]


def buscar_en_wayback(con) -> int:
    """Para los números faltantes, busca copias archivadas en el Wayback Machine."""
    pendientes = set(faltantes(con))
    if not pendientes:
        return 0
    nuevos = 0
    for patron in PATRONES_WAYBACK:
        params = {"url": patron, "matchType": "prefix", "output": "json", "fl": "original,timestamp",
                  "filter": ["mimetype:application/pdf", "statuscode:200", "original:.*[Cc]onflict.*"],
                  "collapse": "urlkey"}
        try:
            filas = _get(requests.Request("GET", CDX, params=params).prepare().url, timeout=180).json()[1:]
        except (requests.RequestException, ValueError):
            continue
        for original, marca in filas:
            num = num_pista("", original)
            if num not in pendientes or not es_reporte_mensual("", original):
                continue
            cur = con.execute(
                "INSERT OR IGNORE INTO documento (url, fuente, titulo, formato, num_titulo, descubierto_en)"
                " VALUES (?, 'wayback', ?, 'pdf', ?, ?)",
                # id_ devuelve el archivo original, sin la barra del Wayback.
                (f"https://web.archive.org/web/{marca}id_/{original}", original, num, ahora()),
            )
            nuevos += cur.rowcount
        con.commit()
    probadas = "listado oficial; " + "; ".join(f"wayback {p}" for p in PATRONES_WAYBACK)
    for n in faltantes(con):
        con.execute("INSERT OR REPLACE INTO faltante VALUES (?, ?, ?)", (n, probadas, ahora()))
    con.execute(f"DELETE FROM faltante WHERE num NOT IN ({','.join(map(str, faltantes(con))) or 'NULL'})")
    con.commit()
    return nuevos


def _guardar(contenido: bytes, formato: str) -> str:
    huella = hashlib.sha256(contenido).hexdigest()
    CRUDOS.mkdir(parents=True, exist_ok=True)
    ruta = CRUDOS / f"{huella}.{formato}"
    if not ruta.exists():
        ruta.write_bytes(contenido)
    return huella


def descargar(con) -> tuple[int, int]:
    """Descarga los documentos sin huella. Los zip se abren y cada PDF interno es un documento."""
    ok = errores = 0
    pendientes = con.execute("SELECT url, formato FROM documento WHERE huella IS NULL").fetchall()
    for doc in pendientes:
        try:
            r = _get(doc["url"], timeout=180)
            r.raise_for_status()
            huella = _guardar(r.content, doc["formato"])
            con.execute("UPDATE documento SET huella = ?, error = NULL WHERE url = ?", (huella, doc["url"]))
            if doc["formato"] == "zip":
                with zipfile.ZipFile(io.BytesIO(r.content)) as z:
                    for nombre in z.namelist():
                        if nombre.lower().endswith(".pdf"):
                            h = _guardar(z.read(nombre), "pdf")
                            con.execute(
                                "INSERT OR IGNORE INTO documento (url, fuente, titulo, formato, num_titulo,"
                                " huella, descubierto_en) VALUES (?, 'zip', ?, 'pdf', ?, ?, ?)",
                                (f"{doc['url']}#{nombre}", nombre, num_pista("", nombre), h, ahora()),
                            )
            ok += 1
        except Exception as e:  # se registra y se sigue con el resto
            con.execute("UPDATE documento SET error = ? WHERE url = ?", (str(e)[:300], doc["url"]))
            errores += 1
        con.commit()
        time.sleep(PAUSA)
    return ok, errores
