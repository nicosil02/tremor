"""Lead de la nota para las protestas sin lugar o anunciadas: muchos feeds dan solo el titular, y con el titular el LLM
confunde una marcha ocurrida con un anuncio (p. ej. "Agricultores exigen a Southern…" era una marcha en Candarave).


Decodifica el enlace de Google News al del medio, baja la página y guarda como `resumen` la descripción y los
primeros párrafos (máx. 600 caracteres; nunca el texto completo). Luego borra la codificación para que el
codificador la rehaga con más contexto.
"""
import html
import json
import re
import time
from datetime import date
from urllib.parse import quote, unquote

import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/130.0 Safari/537.36"}
BATCH = "https://news.google.com/_/DotsSplashUi/data/batchexecute"


class Limite(Exception):
    pass


def enlace_real(url: str) -> str | None:
    """news.google.com/rss/articles/<id> → URL del medio (firma y hora de la página + batchexecute)."""
    gid = re.search(r"articles/([^?/]+)", url)
    if not gid:
        return url
    # la página rss/articles trae la misma firma y no corta con captcha como /articles (25 de 25 seguidas, 9 nov)
    r = requests.get(f"https://news.google.com/rss/articles/{gid[1]}", headers=UA, timeout=30)
    if r.status_code == 429:
        raise Limite("Google News pide captcha: seguir más tarde")
    p = r.text
    sg, ts = re.search(r'data-n-a-sg="([^"]+)"', p), re.search(r'data-n-a-ts="([^"]+)"', p)
    if not (sg and ts):
        return None
    req = [[["Fbv4je", f'["garturlreq",[["X","X",["X","X"],null,null,1,1,"US:en",null,1,null,null,null,null,null,0,1],'
                       f'"X","X",1,[1,1,1],1,1,null,0,0,null,0],"{gid[1]}",{ts[1]},"{sg[1]}"]', None, "generic"]]]
    r = requests.post(BATCH, headers={**UA, "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"},
                      data="f.req=" + quote(json.dumps(req)), timeout=30)
    m = re.search(r'garturlres\\",\\"(.*?)\\"', r.text)
    return m[1] if m else None


def _limpio(s):
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", s)).split())


def lead(pagina: str, n=1500) -> str:
    """og:description + primeros párrafos con texto, hasta n caracteres."""
    partes = re.findall(r'<meta[^>]+(?:property|name)="(?:og:)?description"[^>]+content="([^"]*)"', pagina)[:1]
    partes += [p for p in map(_limpio, re.findall(r"<p[^>]*>(.*?)</p>", pagina, re.S)) if len(p) > 60]
    texto = ""
    for p in partes:
        p = _limpio(p)
        if p and p[:50] not in texto:
            texto += (" " if texto else "") + p
        if len(texto) >= n:
            break
    return texto[:n]


def fecha_pagina(pagina: str) -> str | None:
    """Fecha de publicación que declara el medio (meta article:published_time o datePublished de JSON-LD), AAAA-MM-DD.
    Google News a veces reindexa notas viejas con fecha de hoy: un paro de agosto aparecía como del 9 de noviembre."""
    m = re.search(r'(?:article:published_time|datePublished)"?\s*(?:content=|:)\s*"(\d{4}-\d{2}-\d{2})', pagina)
    return m[1] if m else None


def _palabras(s):
    return set(re.findall(r"\w{4,}", html.unescape(s).lower()))


def elegir_bing(rss: str, titular: str) -> str | None:
    """Del RSS de búsqueda de Bing News, el enlace al medio cuyo título se parece al titular (≥60% de sus palabras)."""
    meta, mejor = _palabras(titular), (0.0, None)
    for t, l in re.findall(r"<item>.*?<title>(.*?)</title>.*?<link>(.*?)</link>", rss, re.S):
        m = re.search(r"[?&]url=([^&]+)", html.unescape(l))
        if not m or not meta:
            continue
        k = len(meta & _palabras(t)) / len(meta)
        if k > mejor[0]:
            mejor = (k, unquote(m[1]))
    return mejor[1] if mejor[0] >= 0.6 else None


def por_bing(titular: str) -> str | None:
    """Respaldo cuando Google News pide captcha: buscar el titular en Bing News, que enlaza directo al medio."""
    r = requests.get(f"https://www.bing.com/news/search?q={quote(titular)}&format=rss", headers=UA, timeout=30)
    return elegir_bing(r.text, titular) if r.ok else None


def ampliar(con, version: str, limite=200, pausa=1.0) -> tuple[int, int]:
    """Protestas sin resumen que están sin lugar preciso o marcadas como anunciadas → lead del medio. Primero los
    enlaces directos al medio (sin cupo), después los de Google News (con pausa)."""
    # también las anunciadas sin fecha con resumen corto: la fecha suele estar en el cuerpo ("del 16 al 18 de noviembre")
    filas = con.execute("""SELECT n.id, n.enlace, n.titular, substr(n.publicado, 1, 10),
               c.precision IS NULL OR c.precision = 'departamento' OR (c.estado = 'anunciada' AND c.fecha_evento IS NULL)
        FROM nota n JOIN codificacion c ON c.nota_id = n.id AND c.version = ?
        WHERE c.es_protesta = 1 AND n.publicado >= date('now', '-30 day')
          AND (coalesce(n.resumen, '') = '' OR (c.estado = 'anunciada' AND c.fecha_evento IS NULL AND length(n.resumen) < 400))
        ORDER BY n.enlace LIKE '%news.google.com%' LIMIT ?""", (version, limite)).fetchall()
    if not filas:
        return 0, 0
    hechas, bing = 0, False
    viejo = dict(con.execute("SELECT id, resumen FROM nota WHERE id IN (%s)" % ",".join("?" * len(filas)), [f[0] for f in filas]))
    for id_, url, titular, publicado, sin_lugar in filas:
        if "news.google.com" in url:
            time.sleep(2 if bing else pausa)  # sin pausa Google corta con captcha a las ~15 consultas
        try:
            real = por_bing(titular) if bing and "news.google.com" in url else enlace_real(url)
            pagina = requests.get(real, headers=UA, timeout=30).text if real else ""
            texto = lead(pagina)
        except requests.RequestException:
            continue
        except Limite as e:
            print(f"  {e}; sigo por Bing News")  # sin saltarse el captcha: se busca el titular en otro buscador
            bing = True
            continue
        f = fecha_pagina(pagina)
        if f and publicado and f < publicado and (date.fromisoformat(publicado) - date.fromisoformat(f)).days > 3:
            # nota vieja que Google reindexó con fecha de hoy: no es una protesta de ahora, sale de la cola y de los eventos
            con.execute("UPDATE nota SET publicado = ?, filtro = 'vieja' WHERE id = ?", (f, id_))
            con.execute("DELETE FROM codificacion WHERE nota_id = ?", (id_,))
            con.commit()
            continue
        if texto and len(texto) > len(viejo.get(id_) or ""):
            con.execute("UPDATE nota SET resumen = ?, enlace = ? WHERE id = ?", (texto, real, id_))
            if sin_lugar:  # solo se recodifica lo que no tenía lugar; lo demás guarda el texto para leer adhesiones
                # la anterior queda como "previa" hasta que el LLM la rehaga: sin cupo, la protesta no desaparece
                con.execute("DELETE FROM codificacion WHERE nota_id = ? AND version IN ('previa', 'reglas')", (id_,))
                con.execute("UPDATE codificacion SET version = 'previa' WHERE nota_id = ? AND version = ?", (id_, version))
            con.commit()  # nota por nota: no bloquear la base durante las pausas
            hechas += 1
    return len(filas), hechas
