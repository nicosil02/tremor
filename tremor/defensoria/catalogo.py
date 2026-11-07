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
    "defensoria.gob.pe/conflictos-sociales/objetos/",  # aquí estaba el n.° 70 (diciembre 2009)
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


MESES = {m: i for i, m in enumerate(
    "enero febrero marzo abril mayo junio julio agosto setiembre octubre noviembre diciembre".split(), 1)}
MESES["septiembre"] = 9
_MES = "|".join(MESES)

# Formas en que la portada dice el número, de la más a la menos específica (ver tests).
PATRONES_NUM = [
    r"reporte\s+(?:mensual\s+)?(?:de\s+)?(?:conflictos\s+sociales\s+)?n\s*[.°ºo]*\s*°?\s*(\d{1,3})\b",
    r"\b(\d{1,3})\s*°\s*reporte",                       # "60°REPORTE" (2009)
    r"conflictos\s+sociales\W{0,3}n\s*[.°ºo]*\s*°?\s*(\d{1,3})\b",
]
PATRON_PERIODO = rf"\b({_MES})\s+(?:de\s+|del\s+)?(\d{{4}})\b"


def texto_inicial(ruta, formato: str, paginas: int = 3) -> str:
    """Texto de las primeras páginas (PDF) o del inicio de la página (HTML)."""
    if formato == "html":
        sopa = BeautifulSoup(ruta.read_text(encoding="utf-8", errors="replace"), "html.parser")
        for s in sopa(["script", "style"]):
            s.decompose()
        return sopa.get_text("\n")[:20000]
    import pymupdf
    pymupdf.TOOLS.mupdf_display_errors(False)
    with pymupdf.open(ruta) as d:
        return "\n".join(d[i].get_text() for i in range(min(paginas, len(d))))


def leer_portada(texto: str) -> tuple[int | None, int | None, int | None]:
    """(número, mes, año) del reporte según su propio texto."""
    plano = re.sub(r"\s+", " ", texto)
    num = None
    for p in PATRONES_NUM:
        m = re.search(p, plano, re.I)
        if m:
            num = int(m.group(1))
            break
    m = re.search(PATRON_PERIODO, plano, re.I)
    mes, anio = (MESES[m.group(1).lower()], int(m.group(2))) if m else (None, None)
    return num, mes, anio


def identificar(con) -> dict:
    """Lee la portada de cada documento descargado y elige un documento principal por número."""
    conteo = {"leidos": 0, "discrepancias": []}
    pend = con.execute("SELECT url, formato, huella, num_titulo FROM documento"
                       " WHERE huella IS NOT NULL AND formato != 'zip' AND rol IS NULL").fetchall()
    for d in pend:
        ruta = CRUDOS / f"{d['huella']}.{d['formato']}"
        num, mes, anio = leer_portada(texto_inicial(ruta, d["formato"]))
        if num is None:  # la portada no lo dice en las primeras páginas: se buscan más
            num, mes2, anio2 = leer_portada(texto_inicial(ruta, d["formato"], paginas=10))
            mes, anio = mes or mes2, anio or anio2
        if num is None and d["num_titulo"] is not None:
            # El reporte n.° 1 y la edición especial del 35 no dicen su número en el texto.
            # ponytail: se acepta el del nombre del archivo; la secuencia de meses lo contrasta.
            num = d["num_titulo"]
        if num is not None and d["num_titulo"] is not None and num != d["num_titulo"]:
            conteo["discrepancias"].append((d["url"], d["num_titulo"], num))
        con.execute("UPDATE documento SET reporte_num = ?, mes = ?, anio = ? WHERE url = ?",
                    (num, mes, anio, d["url"]))
        conteo["leidos"] += 1
    con.commit()
    _asignar_roles(con)
    return conteo


def _asignar_roles(con):
    """Un principal por número; el resto es copia, parte, especial o sin número."""
    prioridad = {"listado": 0, "zip": 1, "wayback": 2}
    docs = con.execute("SELECT url, fuente, huella, reporte_num FROM documento"
                       " WHERE huella IS NOT NULL AND formato != 'zip'").fetchall()
    por_num = {}
    for d in docs:
        if d["reporte_num"] is None:
            # conflictos_2005.pdf es el resumen anual, no un reporte mensual.
            rol = "anual" if re.search(r"conflictos_\d{4}\.pdf$", d["url"]) else "sin_numero"
            con.execute("UPDATE documento SET rol = ? WHERE url = ?", (rol, d["url"]))
        else:
            por_num.setdefault(d["reporte_num"], []).append(d)
    for num, grupo in por_num.items():
        grupo.sort(key=lambda d: (prioridad[d["fuente"]], d["url"]))
        principal = next((d for d in grupo if not re.search(r"especial", d["url"], re.I)), grupo[0])
        for d in grupo:
            archivo = unquote(d["url"].rsplit("/", 1)[-1])
            if d is principal:
                rol = "principal"
            elif re.search(r"especial", archivo, re.I):
                rol = "especial"
            elif re.search(r"-\d\.pdf$", archivo) and d["huella"] != principal["huella"] \
                    and d["fuente"] == principal["fuente"]:
                rol = "parte"  # reporte subido en varios archivos (n.° 155)
            else:
                rol = "copia"
            con.execute("UPDATE documento SET rol = ? WHERE url = ?", (rol, d["url"]))
    con.commit()


def _guardar(contenido: bytes, formato: str) -> str:
    huella = hashlib.sha256(contenido).hexdigest()
    CRUDOS.mkdir(parents=True, exist_ok=True)
    ruta = CRUDOS / f"{huella}.{formato}"
    if not ruta.exists():
        ruta.write_bytes(contenido)
    return huella


TRUNCADO = 1048576  # el Wayback guardó algunos PDF cortados justo en 1 MB (185, 189, 190 y 198)


def _bajar(url: str) -> bytes:
    """Contenido de un documento. Para lo rescatado del Wayback se prueba antes el enlace original,
    que suele seguir vivo, y si no, la captura más grande (las primeras pueden estar truncadas)."""
    m = re.match(r"https://web\.archive\.org/web/\d+id_/(.+)", url)
    if m:
        original = m.group(1)
        try:
            r = _get(original.replace("http://", "https://"), timeout=180)
            if r.ok and r.content[:4] == b"%PDF":
                return r.content
        except requests.RequestException:
            pass
        filas = _get(requests.Request("GET", CDX, params={
            "url": original, "output": "json", "fl": "timestamp,length", "filter": "statuscode:200"},
        ).prepare().url, timeout=180).json()[1:]
        if filas:
            marca = max(filas, key=lambda f: int(f[1]))[0]
            url = f"https://web.archive.org/web/{marca}id_/{original}"
    r = _get(url, timeout=180)
    r.raise_for_status()
    if len(r.content) == TRUNCADO:
        raise ValueError("copia truncada en 1 MB")
    return r.content


def descargar(con) -> tuple[int, int]:
    """Descarga los documentos sin huella. Los zip se abren y cada PDF interno es un documento."""
    ok = errores = 0
    pendientes = con.execute("SELECT url, formato FROM documento WHERE huella IS NULL").fetchall()
    for doc in pendientes:
        try:
            contenido = _bajar(doc["url"])
            huella = _guardar(contenido, doc["formato"])
            con.execute("UPDATE documento SET huella = ?, error = NULL WHERE url = ?", (huella, doc["url"]))
            if doc["formato"] == "zip":
                with zipfile.ZipFile(io.BytesIO(contenido)) as z:
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
