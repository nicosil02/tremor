"""Notas de prensa (research R4): feeds RSS propios de los medios + Google News por departamento.

Se guarda titular, resumen corto (si el feed lo trae), medio, fecha y enlace. Nunca el texto completo.
"""
import hashlib
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
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
    # Tomados de Base_legislativa (probados el 7 nov 2026)
    "La República": ("https://larepublica.pe/rss/sociedad.xml", None),
    "Gestión": ("https://gestion.pe/arcio/rss/category/peru/", None),
    "Perú21": ("https://peru21.pe/arcio/rss/category/politica/", None),
    "IDL-Reporteros": ("https://idl-reporteros.pe/feed/", None),
    "CEPES": ("https://www.cepes.org.pe/feed/", None),
    "La Revista Agraria": ("https://larevistaagraria.org/feed/", None),
    "Conveagro": ("https://www.conveagro.org.pe/feed/", None),
    "Agronoticias": ("https://agronoticias.pe/feed/", None),
    # Radios locales (directorio radio-browser, feeds probados el 7 nov 2026)
    "Exitosa": ("https://www.exitosanoticias.pe/feed/", None),
    # Televisión: las notas de los noticieros que cada canal publica en su web (los feeds de YouTube ya no responden)
    "Canal N": ("https://canaln.pe/feed", None),
    "América Noticias": ("https://www.americatv.com.pe/noticias/feed", None),
    "ATV Noticias": ("https://www.atv.pe/feed", None),
    "Willax": ("https://willax.pe/feed", None),
    "Radio Panamericana": ("https://www.radiopanamericana.com/feed/", None),
    "Radio Sin Patrones": ("https://radiosinpatrones.com/feed/", "Arequipa"),        # Valle de Tambo
    "Radio Yaraví": ("https://www.radioyaravi.org.pe/feed/", "Arequipa"),
    "Radio JR": ("http://www.radiojrfm.com/feed/", "Arequipa"),
    "Radio Onda Popular Cajamarca": ("https://radioondapopular.com/feed/", "Cajamarca"),
    "Radio Onda Popular Puno": ("https://radioondapopular.pe/feed/", "Puno"),
    "Radio Sol de los Andes": ("https://www.radiosoldelosandes.com.pe/feed/", "Puno"),  # Juliaca
    "Radio Andina Tarata": ("http://www.radioandinatarata.pe/rss.xml", "Tacna"),
    "RPT Radio": ("http://rptradio.com/feed/", "Moquegua"),
    "Radio Antena Sur": ("https://www.radioantenasur.com/feed/", None),
    "Radio Nova": ("https://radionova.pe/feed/", "Áncash"),                          # Chimbote
    "Radio Urbana": ("https://radiourbana.com.pe/feed/", "Áncash"),                   # Caraz
    "Radio La Chevérisima": ("http://www.radiolacheverisima.com/feed/", "Amazonas"),
    "Radio Bendición Divina": ("https://radiotvbendiciondivina.com/feed/", "Ayacucho"),  # Huanta
    "Carolina FM": ("https://carolinafm.pe/feed/", "Ica"),
    "Radio 1550": ("https://radio1550.com/feed/", "Junín"),
    "Radio Comas": ("https://radiocomas.com.pe/feed/", "Lima"),
    # Organizaciones y observatorios (sus comunicados anuncian paros y movilizaciones)
    "CGTP": ("https://www.cgtp.org.pe/feed/", None),
    "FENAMAD": ("https://fenamad.com.pe/feed/", "Madre de Dios"),
    "ORPIO": ("https://www.orpio.org.pe/feed/", "Loreto"),
    "CooperAcción": ("https://www.cooperaccion.org.pe/feed/", None),
    "CNDDHH": ("https://derechoshumanos.pe/feed/", None),
    "Grufides": ("https://www.grufides.org/feed/", "Cajamarca"),
    "Red Muqui": ("https://muqui.org/feed/", None),
    "DAR": ("https://www.dar.org.pe/feed/", None),
}
# Notas y comunicados del Ejecutivo en gob.pe (las últimas 25 de cada institución; probado el 11 nov 2026). La Policía
# informa desbloqueos y vías liberadas; la PCM, mesas de diálogo y actas. Pasan por el mismo filtro y el mismo LLM.
GOBPE = {"PCM": "pcm", "Policía Nacional": "pnp", "Mininter": "mininter", "MINAM": "minam", "MINEM": "minem",
         "OEFA": "oefa", "ANA": "ana"}
GOBPE_URL = "https://www.gob.pe/busquedas?contenido[]=noticias&sort_by=recent&institucion[]={}"
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
         "frente de defensa Perú",
         # clientes del piloto: toda nota que los nombre, no solo las de protesta (las lee tremor.animo)
         '("minera bateas" OR "minera raura" OR "minera poderosa" OR Caylloma OR Pataz OR Oyón)', "(enfrentamiento OR heridos) protesta Perú", "conflicto social Perú",
         # medios sin feed propio (Base_legislativa los lee así)
         f"{PALABRAS} site:expreso.com.pe", f"{PALABRAS} site:ojo-publico.com", f"{PALABRAS} site:canaln.pe"]
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


EXTRANJERO = re.compile(r"\.(ar|mx|uy|cl|co|ec|bo|ve|es|py|cr|gt|hn|sv|ni|pa|do|cu|pr|us)/?$", re.I)


def filtro(texto: str, fuente_url: str = "") -> str | None:
    """None si pasa al LLM; si no, el motivo del descarte (FR-011)."""
    if EXTRANJERO.search(fuente_url or ""):
        return "medio_extranjero"
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
            pub = (g("pubDate") or "")[:16] if re.match(r"\d{4}-\d\d-\d\dT", g("pubDate") or "") else None  # ISO (América)
        fuente = re.search(r'<source[^>]*url="([^"]+)"', item)
        yield {"medio": medio, "titular": titulo.strip(), "resumen": resumen[:600], "publicado": pub, "enlace": g("link"),
               "fuente_url": fuente[1] if fuente else ""}


MESES_ES = "enero febrero marzo abril mayo junio julio agosto setiembre octubre noviembre diciembre".split()


def parsear_gobpe(pagina: str, medio: str):
    """La búsqueda de gob.pe trae los resultados como JSON dentro del HTML; la fecha viene en castellano
    ("20 de octubre de 2026 -  9:02 p. m.")."""
    k = pagina.find('"results":')
    if k < 0:
        return
    for x in json.JSONDecoder().raw_decode(pagina[k + 10:])[0]:
        f = re.search(r"(\d+) de (\w+) de (\d{4}) -\s+(\d+):(\d\d) ([ap])", x.get("publication") or "")
        pub = None
        if f and f[2].replace("septiembre", "setiembre") in MESES_ES:
            h = int(f[4]) % 12 + (12 if f[6] == "p" else 0)
            pub = f"{f[3]}-{MESES_ES.index(f[2].replace('septiembre', 'setiembre')) + 1:02d}-{int(f[1]):02d}T{h:02d}:{f[5]}-05:00"
        enlace = re.search(r'href="([^"]+)"', x.get("url") or "")
        yield {"medio": medio, "titular": _limpio(x.get("name_with_parent")), "resumen": _limpio(x.get("content"))[:600],
               "publicado": pub, "enlace": "https://www.gob.pe" + enlace[1] if enlace else None, "fuente_url": ""}


def cuerpo_gobpe(pagina: str, n=1500) -> str:
    """El texto de una nota de gob.pe: va después de la fecha de publicación. Los comunicados de la Policía se
    titulan solo "Comunicado N° 32-2026" y la búsqueda trae apenas la primera línea; el bloqueo está más abajo."""
    t = " ".join(_limpio(re.sub(r"<(script|style|svg)\b.*?</\1>", " ", pagina, flags=re.S)).split())
    f = re.search(r"\d+ de \w+ de \d{4} - \d+:\d\d [ap]\. m\.", t)
    return t[f.end():f.end() + n].strip() if f else ""


def _guardar(con, notas, consulta, dep):
    nuevas = 0
    for n in notas:
        if not n["titular"]:
            continue
        cur = con.execute("INSERT OR IGNORE INTO nota VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                          (id_nota(n["medio"], n["titular"]), n["medio"], n["titular"], n["resumen"], n["publicado"],
                           n["enlace"], consulta, dep, ahora(), filtro(n["titular"] + " " + n["resumen"], n.get("fuente_url"))))
        nuevas += cur.rowcount
    con.commit()
    return nuevas


def lugares_cliente(con):
    """Nombres de los distritos y provincias de cada unidad y de cada tramo de la ruta de los clientes, en grupos de 8
    para buscarlos en Google News: una protesta chica en Callalli u Oyón no sale en la búsqueda por departamento.
    Sin los departamentos (ya se buscan) ni nombres de 3 letras o menos."""
    from tremor.avisos import CADENA, EMPRESAS
    from tremor.lugares import nombre
    ubs = {u for _, (emp, _a) in EMPRESAS.items() for (u,) in con.execute(
        "SELECT ubigeo FROM operacion WHERE lower(empresa) LIKE ? AND unidad NOT LIKE 'Pasivos%'", (f"%{emp}%",))}
    ubs |= {u for c in CADENA.values() if isinstance(c, dict) for t in c.get("tramos", []) for u in t["ubigeos"]}
    fuera = {norm(d) for d in DEPARTAMENTOS}
    nombres = sorted({n for u in ubs for n in (nombre(u), nombre(u[:4])) if n and len(n) > 3 and norm(n) not in fuera})
    return [nombres[i:i + 8] for i in range(0, len(nombres), 8)]


def recolectar(con, desde: date | None = None, hasta: date | None = None, pausa=1.0, google=True) -> tuple[int, int]:
    """Sin fechas: feeds de los medios + Google News de las últimas 24 h. Con fechas: Google News día a día
    (los feeds solo traen lo reciente; la búsqueda retro trae ~10 notas por consulta)."""
    nuevas = vistas = 0
    if not desde:
        def bajar(url):
            try:
                r = requests.get(url, timeout=30, headers=UA); r.raise_for_status()
                if r.encoding == "ISO-8859-1" and "charset" not in r.headers.get("content-type", "").lower():
                    r.encoding = "utf-8"  # sin charset, requests supone latin-1 y salen "PaÃ­ses"
                return r
            except requests.RequestException as e:
                return e
        with ThreadPoolExecutor(16) as pool:  # cada medio es otro servidor: en fila, uno lento frena a los 59
            bajados = list(pool.map(bajar, [url for url, _ in FEEDS.values()]))
        for (medio, (url, dep)), r in zip(FEEDS.items(), bajados):
            if isinstance(r, Exception):
                print(f"  {medio}: {r.__class__.__name__}")
                continue
            limite = (date.today() - timedelta(30)).isoformat()  # feeds abandonados o con años de archivo
            notas = [n for n in parsear(r.text, medio) if (n["publicado"] or "") >= limite]; vistas += len(notas)
            nuevas += _guardar(con, notas, f"feed:{medio}", dep)
        for medio, slug in GOBPE.items():
            try:
                r = requests.get(GOBPE_URL.format(slug), timeout=60, headers=UA); r.raise_for_status()
            except requests.RequestException as e:
                print(f"  gob.pe {medio}: {e.__class__.__name__}")
                continue
            notas = list(parsear_gobpe(r.text, medio)); vistas += len(notas)
            for x in notas:  # "Comunicado N° 32-2026": se lee la página, solo la primera vez
                if re.match(r"comunicado", x["titular"], re.I) and x["enlace"] and not con.execute(
                        "SELECT 1 FROM nota WHERE id = ?", (id_nota(medio, x["titular"]),)).fetchone():
                    try:
                        x["resumen"] = cuerpo_gobpe(requests.get(x["enlace"], timeout=60, headers=UA).text)[:1000] or x["resumen"]
                    except requests.RequestException:
                        pass
            nuevas += _guardar(con, notas, f"gobpe:{slug}", None)
    dias =[(None, None)] if not desde else [(desde + timedelta(d), desde + timedelta(d + 1))
                                             for d in range(((hasta or desde) - desde).days + 1)]
    for d0, d1 in dias:
        cliente = [(PALABRAS + " (" + " OR ".join(f'"{n}"' for n in g) + ") Perú", None) for g in lugares_cliente(con)]  # sin Perú, "Mara" trae a Mara Lezama
        # google=False (el vigilante, cada 2 min): solo los feeds y las búsquedas de los lugares del cliente
        for tema, dep in ([(t, None) for t in TEMAS] + [(f'{PALABRAS} "{d}" Perú', d) for d in DEPARTAMENTOS] if google else []) + cliente:
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
