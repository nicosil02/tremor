"""Notas de prensa (research R4): feeds RSS propios de los medios + Google News por departamento.

Se guarda titular, resumen corto (si el feed lo trae), medio, fecha y enlace. Nunca el texto completo.
"""
import hashlib
import re
import time
from datetime import date, timedelta, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from urllib.parse import quote

import requests

from tremor.db import ahora
from tremor.lugares import norm

# medio → (feed, departamento que cubre o None si es nacional). Probados el 7 nov 2026.
FEEDS = {
    "RPP": ("https://rpp.pe/rss", None),
    "Correo": ("https://diariocorreo.pe/arc/outboundfeeds/rss/?outputType=xml", None),
    "El Comercio": ("https://elcomercio.pe/arc/outboundfeeds/rss/?outputType=xml", None),
    "Infobae Perú": ("https://www.infobae.com/arc/outboundfeeds/rss/category/peru/", None),
    "Andina": ("https://andina.pe/agencia/rss.aspx", None),
    "Servindi": ("https://www.servindi.org/feed", None),
    "Actualidad Ambiental": ("https://www.actualidadambiental.pe/feed/", None),
    "Convoca": ("https://convoca.pe/rss.xml", None),
    "Wayka": ("https://wayka.pe/feed/", None),
    "Noticias SER": ("https://www.noticiasser.pe/feed", None),
    "Debates Indígenas": ("https://www.debatesindigenas.org/feed", None),
    "Pachamama Radio": ("https://pachamamaradio.org/feed/", "Puno"),
    "Los Andes": ("https://losandes.com.pe/feed/", "Puno"),
    "El Búho": ("https://elbuho.pe/feed/", "Arequipa"),
    "Radio Uno": ("https://radiouno.pe/feed/", "Tacna"),
    "Sin Fronteras": ("https://diariosinfronteras.com.pe/feed/", "Tacna"),
    "Prensa Regional": ("https://www.prensaregional.pe/feed/", "Moquegua"),
    "Inforegión": ("https://www.inforegion.pe/feed/", "Junín"),
    "Diario Ahora": ("https://www.diarioahora.pe/feed/", "Huánuco"),
    "Radio Marañón": ("https://www.radiomaranon.org.pe/feed/", "Cajamarca"),
    "Observatorio de Conflictos Mineros": ("https://conflictosmineros.org.pe/feed/", None),
}
DEPARTAMENTOS = ["Amazonas", "Áncash", "Apurímac", "Arequipa", "Ayacucho", "Cajamarca", "Callao", "Cusco",
                 "Huancavelica", "Huánuco", "Ica", "Junín", "La Libertad", "Lambayeque", "Lima", "Loreto",
                 "Madre de Dios", "Moquegua", "Pasco", "Piura", "Puno", "San Martín", "Tacna", "Tumbes", "Ucayali"]
GNEWS = "https://news.google.com/rss/search?q={q}&hl=es-419&gl=PE&ceid=PE:es-419"
PALABRAS = "(paro OR bloqueo OR huelga OR marcha OR protesta OR toma OR plantón OR enfrentamiento OR movilización)"
# Búsquedas temáticas en todo el país: sin "Perú" Google mezcla Argentina, México y España.
TEMAS = ["(paro OR bloqueo OR huelga) Perú", "(protesta OR movilización OR marcha) Perú", "paro indefinido Perú",
         "paro regional Perú", "(anuncian OR convocan) (paro OR huelga OR movilización) Perú",
         "(comuneros OR comunidades campesinas OR ronderos) Perú", "(comunidades nativas OR indígenas) protesta Perú",
         "minera (protesta OR conflicto OR bloqueo OR paro) Perú", "(lote petrolero OR derrame OR oleoducto) Perú",
         "frente de defensa Perú", "(enfrentamiento OR heridos) protesta Perú", "conflicto social Perú"]
LIMA = timezone(timedelta(hours=-5))
UA = {"User-Agent": "Mozilla/5.0 (tremor)"}

ACCION = re.compile(r"\bparo|bloque|huelga|marcha|moviliz|protest|\btoma\b|\btoman\b|tomaron|plant[oó]n|enfrent|"
                    r"piquete|vigilia|cacerolazo|paraliz|acatan|levantamiento|rechaz|exigen|reclam|conflicto|"
                    r"comuner|rondas? campesin|frente de defensa|derrame|contamina", re.I)
NO_ES = re.compile(r"marcha blanca|puesta en marcha|en marcha\b|marcha atr[aá]s|paro card|paro respir|f[uú]tbol|\bgol\b|"
                   r"liga 1|selecci[oó]n peruana|copa\b|partido de|campeonato|tenis|v[oó]ley|concierto|pel[ií]cula|"
                   r"hor[oó]scopo|receta|sudamericana|libertadores", re.I)


def id_nota(medio, titular):
    return hashlib.sha1(f"{norm(medio)}|{norm(titular)}".encode()).hexdigest()[:16]


def filtro(texto: str) -> str | None:
    """None si pasa al LLM; si no, el motivo del descarte (FR-011)."""
    if NO_ES.search(texto):
        return "no_es_protesta"
    if not ACCION.search(texto):
        return "sin_palabra_de_accion"
    return None


def _limpio(s):
    s = re.sub(r"<!\[CDATA\[|\]\]>", "", s or "")
    return " ".join(re.sub(r"<[^>]+>", " ", unescape(unescape(s))).split())


def parsear(xml: str, medio_fijo=None):
    for item in re.findall(r"<item>(.*?)</item>", xml, re.S):
        g = lambda t: (m := re.search(rf"<{t}[^>]*>(.*?)</{t}>", item, re.S)) and _limpio(m[1])
        titulo, medio = g("title") or "", medio_fijo or g("source") or ""
        if titulo.endswith(" - " + medio):
            titulo = titulo[: -len(medio) - 3]
        resumen = g("description") or ""
        if resumen.startswith(titulo[:40]) or "news.google.com" in (g("link") or "") and len(resumen) < 400:
            resumen = ""  # Google News repite el título
        try:
            pub = parsedate_to_datetime(g("pubDate")).astimezone(LIMA).isoformat(timespec="minutes")
        except (TypeError, ValueError):
            pub = None
        yield {"medio": medio, "titular": titulo.strip(), "resumen": resumen[:600], "publicado": pub, "enlace": g("link")}


def _guardar(con, notas, consulta, dep):
    nuevas = 0
    for n in notas:
        if not n["titular"]:
            continue
        cur = con.execute("INSERT OR IGNORE INTO nota VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                          (id_nota(n["medio"], n["titular"]), n["medio"], n["titular"], n["resumen"], n["publicado"],
                           n["enlace"], consulta, dep, ahora(), filtro(n["titular"] + " " + n["resumen"])))
        nuevas += cur.rowcount
    con.commit()
    return nuevas


def recolectar(con, desde: date | None = None, hasta: date | None = None, pausa=1.0) -> tuple[int, int]:
    """Sin fechas: feeds de los medios + Google News de las últimas 24 h. Con fechas: Google News día a día
    (los feeds solo traen lo reciente; la búsqueda retro trae ~10 notas por consulta)."""
    nuevas = vistas = 0
    if not desde:
        for medio, (url, dep) in FEEDS.items():
            try:
                r = requests.get(url, timeout=30, headers=UA); r.raise_for_status()
            except requests.RequestException as e:
                print(f"  {medio}: {e.__class__.__name__}")
                continue
            notas = list(parsear(r.text, medio)); vistas += len(notas)
            nuevas += _guardar(con, notas, f"feed:{medio}", dep)
    dias = [(None, None)] if not desde else [(desde + timedelta(d), desde + timedelta(d + 1))
                                             for d in range(((hasta or desde) - desde).days + 1)]
    for d0, d1 in dias:
        for tema, dep in [(t, None) for t in TEMAS] + [(f'{PALABRAS} "{d}" Perú', d) for d in DEPARTAMENTOS]:
            q = f"{tema} " + (f"after:{d0} before:{d1}" if d0 else "when:1d")
            try:
                r = requests.get(GNEWS.format(q=quote(q)), timeout=30, headers=UA); r.raise_for_status()
            except requests.RequestException as e:
                print(f"  {dep} {d0}: {e.__class__.__name__}")
                continue
            notas = list(parsear(r.text)); vistas += len(notas)
            nuevas += _guardar(con, notas, q, dep)
            time.sleep(pausa)
    return nuevas, vistas
