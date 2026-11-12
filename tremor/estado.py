"""Casos que sigue el Ejecutivo: la PCM (revista Willaqniki de la Secretaría de Gestión Social y Diálogo, trimestral:
casos en crisis y en riesgo inminente) y el MINAM (informe mensual de la OGASA en el SINIA: mesas de diálogo
socioambientales y lo que pasó en cada una).

Las tablas de los PDF vienen partidas en muchas líneas, así que el LLM las pasa a filas (con caché). Queda en
`caso_estado` y la ficha de cada operación lo muestra junto a los casos de la Defensoría. No entra al modelo: las dos
series empiezan en 2021 y el modelo aprende de 2010 a 2020.

`python -m tremor.estado` → las 2 últimas ediciones de cada uno (lo ya cargado no se vuelve a leer).
"""
import re
import sys

import pymupdf
import requests

from tremor.db import ahora, conectar
from tremor.lugares import resolver
from tremor.territorio import UA

WILLAQNIKI = "https://www.gob.pe/institucion/pcm/colecciones/12-reporte-willaqniki"
OGASA = "https://sinia.minam.gob.pe/taxonomy/term/146150"
ESQUEMA = """CREATE TABLE IF NOT EXISTS caso_estado (
    documento TEXT NOT NULL, fuente TEXT, orden INTEGER, nombre TEXT NOT NULL, nivel TEXT, tipologia TEXT,
    departamento TEXT, provincia TEXT, distrito TEXT, ubigeo TEXT, situacion TEXT, fecha TEXT, medida INTEGER,
    enlace TEXT, cargado TEXT, PRIMARY KEY (documento, nombre))"""
FILAS = ("Te doy el texto de una tabla de un informe del Estado peruano sobre conflictos sociales (el PDF parte cada "
         "celda en varias líneas). Devuelve cada caso de la tabla una sola vez. Por caso: nombre (el del caso, tal "
         "cual), departamento, provincia y distrito (el primero si nombra varios; null si no lo dice, también dentro "
         "del nombre del caso), nivel (uno de: crisis, riesgo inminente, tratamiento, seguimiento, prevención; sale "
         "del título de la tabla o de la columna Línea de acción), tipologia (minería, hidrocarburos, agrario, etc.), "
         "situacion (UNA oración formal de máximo 35 palabras con lo último que pasó; actores por rol o "
         "organización, nunca nombres de personas; null si dice que no hay información del mes), fecha (AAAA-MM-DD "
         "de lo último que pasó, o null) y medida (true si hubo paro, bloqueo, toma, retención o enfrentamiento). "
         'Responde JSON {"casos": [...]}. Si el texto no trae ninguna tabla de casos, {"casos": []}.')


def _get(url, **kw):
    r = requests.get(url, headers=UA, timeout=180, **kw)
    r.raise_for_status()
    return r


def ediciones_willaqniki(n=2):
    """(id, nombre, url del PDF) de las n ediciones más nuevas: el id de gob.pe crece con cada publicación."""
    hrefs = set(re.findall(r'href="(/institucion/pcm/informes-publicaciones/(\d+)-[^"]*willaqniki[^"]*)"', _get(WILLAQNIKI).text))
    for href, i in sorted(hrefs, key=lambda x: -int(x[1]))[:n]:
        pdf = re.search(r'(https://cdn\.www\.gob\.pe/uploads/document/file/\d+/(?!preview_)[^"?]+\.pdf)', _get("https://www.gob.pe" + href).text)
        if pdf:
            yield int(i), "Willaqniki " + href.rsplit("willaqniki-", 1)[-1].replace("-", " "), pdf[1]


def ediciones_ogasa(n=2):
    """(año*100+número, nombre, url del PDF) de los n informes mensuales más nuevos."""
    hrefs = set(re.findall(r'href="(/documentos/informe-ndeg-(\d+)-(\d{4})-ogasa[^"]*)"', _get(OGASA).text))
    for href, num, anio in sorted(hrefs, key=lambda x: (-int(x[2]), -int(x[1])))[:n]:
        pdf = re.search(r'href="([^"]+\.pdf)"', _get("https://sinia.minam.gob.pe" + href).text)
        if pdf:
            url = pdf[1] if pdf[1].startswith("http") else "https://sinia.minam.gob.pe" + pdf[1]
            yield int(anio) * 100 + int(num), f"OGASA {int(num):02d}-{anio}", url


def paginas(pdf: bytes, fuente: str) -> list[str]:
    """Las páginas con tablas de casos: en Willaqniki las de crisis y riesgo inminente (columnas Ubicación y
    Tipología); en la OGASA las del anexo 1 (columna Situación actual, sin las del OEFA ni del SERNANP)."""
    doc = pymupdf.open(stream=pdf, filetype="pdf")
    ts = [p.get_text() for p in doc]
    if fuente == "PCM":
        return [t for t in ts if "Ubicación" in t and "Tipología" in t]
    return [t for t in ts if "Situación actual" in t]


def filas(con, texto, version="estado-1"):
    from tremor.llm import chat_json
    return chat_json(con, FILAS, texto, version).get("casos") or []


def cargar(con, fuente, ediciones, por_lote=3):
    con.execute(ESQUEMA)
    hechas = {d for (d,) in con.execute("SELECT DISTINCT documento FROM caso_estado")}
    n = 0
    for orden, nombre, url in ediciones:
        if nombre in hechas:
            continue
        ts = paginas(_get(url).content, fuente)
        casos = {}
        for i in range(0, len(ts), por_lote):  # de a pocas páginas: la respuesta del LLM no se corta
            for c in filas(con, "\n".join(ts[i:i + por_lote])):
                if c.get("nombre") and len(c.get("situacion") or "") >= len((casos.get(c["nombre"]) or {}).get("situacion") or ""):
                    casos[c["nombre"]] = c
        for c in casos.values():
            ub, _ = resolver(c.get("departamento"), c.get("provincia"), c.get("distrito"))
            con.execute("INSERT OR REPLACE INTO caso_estado VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (nombre, fuente, orden, c["nombre"], (c.get("nivel") or "").lower() or None, c.get("tipologia"), c.get("departamento"),
                         c.get("provincia"), c.get("distrito"), ub, c.get("situacion"), c.get("fecha"),
                         int(bool(c.get("medida"))), url, ahora()))
        con.commit()
        print(f"  {nombre}: {len(ts)} páginas, {len(casos)} casos")
        n += len(casos)
    return n


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    con = conectar()
    for fuente, ed in (("PCM", ediciones_willaqniki), ("MINAM", ediciones_ogasa)):
        try:
            print(f"{fuente}: {cargar(con, fuente, ed())} casos nuevos")
        except Exception as e:  # PDF caído o LLM sin cupo: queda lo de la corrida anterior
            print(f"{fuente}: {e.__class__.__name__} {str(e)[:120]}")


if __name__ == "__main__":
    main()
