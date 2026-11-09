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
from urllib.parse import quote

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
    r = requests.get(f"https://news.google.com/articles/{gid[1]}", headers=UA, timeout=30)
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


def lead(pagina: str, n=600) -> str:
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


def ampliar(con, version: str, limite=200, pausa=8.0) -> tuple[int, int]:
    """Protestas sin resumen que están sin lugar preciso o marcadas como anunciadas → lead del medio. Primero los
    enlaces directos al medio (sin cupo), después los de Google News (con pausa)."""
    filas = con.execute("""SELECT n.id, n.enlace FROM nota n JOIN codificacion c ON c.nota_id = n.id AND c.version = ?
        WHERE c.es_protesta = 1 AND (c.precision IS NULL OR c.precision = 'departamento' OR c.estado = 'anunciada')
          AND coalesce(n.resumen, '') = ''
        ORDER BY n.enlace LIKE '%news.google.com%' LIMIT ?""", (version, limite)).fetchall()
    hechas = 0
    for id_, url in filas:
        if "news.google.com" in url:
            time.sleep(pausa)  # sin pausa Google corta con captcha a las ~15 consultas
        try:
            real = enlace_real(url)
            texto = lead(requests.get(real, headers=UA, timeout=30).text) if real else ""
        except requests.RequestException:
            continue
        except Limite as e:
            print(f"  {e}")
            break
        if texto:
            con.execute("UPDATE nota SET resumen = ?, enlace = ? WHERE id = ?", (texto, real, id_))
            con.execute("DELETE FROM codificacion WHERE nota_id = ? AND version = ?", (id_, version))
            con.commit()  # nota por nota: no bloquear la base durante las pausas
            hechas += 1
    return len(filas), hechas
