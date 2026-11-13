"""Historia de la prensa regional desde 2018: archivo de medios WordPress por su API pública (`/wp-json/wp/v2/posts`).

Por nota se lee solo titular, extracto (≤600 caracteres), fecha y enlace; nunca el texto completo. Se guarda en `nota`
solo lo que pasa `recolectar.filtro`; de lo demás queda el conteo por medio y mes en `historia_conteo` (que también
marca los meses hechos: volver a correr sigue donde quedó). Respeta robots.txt y su Crawl-delay; si el medio responde
con algo que no es JSON (captcha, verificación de bot) o con 403/429, se deja ese medio.

Probados el 8 nov 2026. Fuera: La República (robots bloquea las secciones), RPP (robots bloquea el archivo hasta 2020),
Convoca y OjoPúblico (robots `Disallow: /`), Jornada (robots bloquea wp-json), CNDDHH (403), Correo y Andina (sus
sitemaps solo traen los últimos días), Servindi (Drupal sin archivo por fecha).
"""
import re
import time
import urllib.robotparser
from datetime import date

import requests

from tremor.lugares import catalogo, norm
from tremor.prensa.recolectar import _guardar, _limpio, filtro

UA = "TremorBot/0.1 (proyecto academico PUCP; +https://github.com/nicosil02/tremor)"
# medio (mismo nombre que en FEEDS, para no duplicar notas) → (sitio, departamento que cubre o None)
MEDIOS = {
    "Radio Uno": ("https://radiouno.pe", "Tacna"),
    "Sin Fronteras": ("https://diariosinfronteras.com.pe", "Tacna"),          # desde 2020-06
    "Prensa Regional": ("https://www.prensaregional.pe", "Moquegua"),          # desde 2018-07
    "Los Andes": ("https://losandes.com.pe", "Puno"),                           # desde 2018-11
    "Radio Onda Azul": ("https://radioondaazul.com", "Puno"),                   # desde 2019-04
    "Pachamama Radio": ("https://pachamamaradio.org", "Puno"),                  # desde 2022-02, Crawl-delay 10
    "Radio Yaraví": ("https://www.radioyaravi.org.pe", "Arequipa"),             # desde 2018-06
    "El Búho": ("https://elbuho.pe", "Arequipa"),
    "Cutivalú": ("https://cutivalu.pe", "Piura"),
    "El Tiempo": ("https://eltiempo.pe", "Piura"),                              # desde 2020-03
    "Inforegión": ("https://www.inforegion.pe", "Junín"),
    "Diario Ahora": ("https://diarioahora.pe", "Huánuco"),                      # desde 2018-06
    "Cusco en Portada": ("https://cuscoenportada.com", "Cusco"),
    "Radio Nova": ("https://radionova.pe", "Áncash"),
    "Diario Voces": ("https://diariovoces.com.pe", "San Martín"),
    "RCR Perú": ("https://rcrperu.com", None),                                  # red de radios regionales
    "Wayka": ("https://wayka.pe", None),
    "Actualidad Ambiental": ("https://actualidadambiental.pe", None),
    "Observatorio de Conflictos Mineros": ("https://conflictosmineros.org.pe", None),
    "Red Muqui": ("https://muqui.org", None),
    "CooperAcción": ("https://www.cooperaccion.org.pe", None),
    "Grufides": ("https://grufides.org", "Cajamarca"),
    "DAR": ("https://www.dar.org.pe", None),
    "IDL-Reporteros": ("https://idl-reporteros.pe", None),
    "CGTP": ("https://www.cgtp.org.pe", None),
}
ESQUEMA = """CREATE TABLE IF NOT EXISTS historia_conteo (medio TEXT, mes TEXT, vistas INTEGER, pasan INTEGER,
    PRIMARY KEY (medio, mes))"""
# Palabras de acción del manual EGPP (más estrictas que el filtro): ordenan la cola del LLM, no descartan.
EGPP = re.compile(r"\bparo\b|\bparos\b|bloque|huelga|marcha|moviliz|protest|\btoma\b|\btoman\b|tomaron|planton|"
                  r"enfrent|piquete|vigilia|cacerolazo|paraliz|acatan")


class Bloqueado(Exception):
    pass


def meses(desde: str, hasta: str):
    a, m = map(int, desde.split("-")); b, n = map(int, hasta.split("-"))
    while (a, m) <= (b, n):
        yield f"{a}-{m:02d}"
        a, m = (a + 1, 1) if m == 12 else (a, m + 1)


def _siguiente(mes):
    a, m = map(int, mes.split("-"))
    return f"{a + 1}-01" if m == 12 else f"{a}-{m + 1:02d}"


def notas_wp(items, medio):
    for it in items:
        titular = _limpio((it.get("title") or {}).get("rendered"))
        resumen = re.sub(r"\s*(\[(…|&hellip;|\.\.\.)\]|Leer m[aá]s.*)$", "", _limpio((it.get("excerpt") or {}).get("rendered")))
        yield {"medio": medio, "titular": titular, "resumen": resumen[:600], "enlace": it.get("link"),
               "publicado": (it.get("date") or "")[:16] + "-05:00" if it.get("date") else None}


def _get(url, params=None, pausa=0.0, intentos=4):
    """GET educado: pausa antes; ante caídas de red reintenta con espera creciente."""
    time.sleep(pausa)
    for i in range(intentos):
        try:
            r = requests.get(url, params=params, headers={"User-Agent": UA}, timeout=60)
            break
        except requests.RequestException:
            if i == intentos - 1:
                raise
            time.sleep(30 * (i + 1))
    if url.endswith("robots.txt"):
        return r
    if r.status_code in (401, 403, 429) or "json" not in r.headers.get("content-type", ""):
        raise Bloqueado(f"{r.status_code} {r.headers.get('content-type', '')[:30]}")
    return r


def historia(con, medio, desde="2018-01", hasta=None, pausa=3.0) -> tuple[int, int]:
    """Baja mes a mes el archivo del medio. Devuelve (vistas, guardadas). El mes en curso se rehace siempre."""
    con.execute(ESQUEMA)
    sitio, dep = MEDIOS[medio]
    rp = urllib.robotparser.RobotFileParser()
    try:
        rp.parse(_get(sitio + "/robots.txt").text.splitlines())
    except requests.RequestException as e:
        print(f"  {medio}: sin robots.txt ({e.__class__.__name__}), se salta por ahora")
        return 0, 0
    api = sitio + "/wp-json/wp/v2/posts"
    if not rp.can_fetch(UA, api):
        print(f"  {medio}: robots.txt no permite la API, se salta")
        return 0, 0
    pausa = max(pausa, rp.crawl_delay(UA) or 0)
    hoy = date.today().isoformat()[:7]
    try:  # no recorrer meses anteriores a la primera nota del sitio
        primera = _get(api, {"per_page": 1, "order": "asc", "orderby": "date", "_fields": "date"}, pausa).json()
        desde = max(desde, (primera[0]["date"] if primera else hoy)[:7])
    except (Bloqueado, requests.RequestException, ValueError, KeyError) as e:
        print(f"  {medio}: {e.__class__.__name__} {e}; se deja el medio (seguir luego)")
        return 0, 0
    hechos = {r[0] for r in con.execute("SELECT mes FROM historia_conteo WHERE medio = ?", (medio,))}
    total = guardadas = 0
    for mes in meses(desde, hasta or hoy):
        if mes in hechos and mes != hoy:
            continue
        vistas = pasan = 0; pagina = 1
        while True:
            try:
                r = _get(api, {"after": f"{mes}-01T00:00:00", "before": f"{_siguiente(mes)}-01T00:00:00",
                               "per_page": 100, "page": pagina, "orderby": "date", "order": "asc",
                               "_fields": "date,link,title,excerpt"}, pausa)
            except (Bloqueado, requests.RequestException) as e:
                print(f"  {medio} {mes}: {e.__class__.__name__} {e}; se deja el medio (seguir luego)")
                return total, guardadas
            if r.status_code == 400 and pagina > 1:   # página fuera de rango
                break
            r.raise_for_status()
            notas = [n for n in notas_wp(r.json(), medio) if n["titular"]]
            buenas = [n for n in notas if filtro(n["titular"] + " " + n["resumen"]) is None]
            vistas += len(notas); pasan += len(buenas)
            guardadas += _guardar(con, buenas, f"historia:{medio}", dep)
            if pagina >= int(r.headers.get("X-WP-TotalPages") or 1):
                break
            pagina += 1
        total += vistas
        con.execute("INSERT OR REPLACE INTO historia_conteo VALUES (?, ?, ?, ?)", (medio, mes, vistas, pasan))
        con.commit()
        print(f"  {medio} {mes}: {vistas} notas, {pasan} pasan el filtro", flush=True)
    return total, guardadas


def _lugares_con_operacion(con):
    """Nombres normalizados de distritos y provincias con operación extractiva (tabla `operacion`, OEFA)."""
    try:
        ubigeos = {r[0] for r in con.execute("SELECT DISTINCT ubigeo FROM operacion WHERE length(ubigeo) = 6")}
    except Exception:
        return None
    nombres = catalogo()[3]
    lugares = {norm(nombres[c]) for u in ubigeos for c in (u, u[:4]) if c in nombres}
    lugares = sorted((x for x in lugares if len(x) > 4), key=len, reverse=True)  # "santa", "lima": demasiado comunes
    return re.compile(r"\b(?:" + "|".join(map(re.escape, lugares)) + r")\b") if lugares else None


# lo que frena una operación o su salida: carga pesada, paro nacional, minería, hidrocarburos
CLIENTE = re.compile(r"carga pesada|transportistas de carga|camioner|paro nacional|paro de transport|miner|\bmina\b|petrol|oleoducto|\blote \d|corredor minero")


def _del_que_recibe_avisos(con):
    """Regex (sobre texto normalizado) de la empresa que recibe los avisos y de los distritos y provincias de su zona y
    su ruta: sus notas se leen primero, para que una cola larga de otras zonas no retrase su aviso."""
    from tremor import avisos
    from tremor.prensa.recolectar import lugares_cliente
    try:
        nombres = [norm(n) for g in lugares_cliente(con, avisos.CLIENTE) for n in g]
    except Exception:  # sin base o sin la tabla `operacion`: solo el nombre de la empresa
        nombres = []
    return re.compile("|".join([avisos.EMPRESAS[avisos.CLIENTE][1], *(rf"\b{re.escape(n)}\b" for n in nombres)]))


def ordenar(con, filas):
    """Cola del codificador: primero lo vivo (feeds, Google News, radio), y dentro lo que le importa a un cliente
    minero (si no, con poco cupo las notas nuevas de otros temas dejan atrás un paro nacional de carga) y luego por fecha; después la historia, primero
    las notas con palabra de acción EGPP y lugar con operación, luego una de las dos, luego el resto.
    filas: (id, titular, resumen, publicado, departamento_consulta, consulta)."""
    lugar = _lugares_con_operacion(con)
    suyo = _del_que_recibe_avisos(con)

    def clave(r):
        t = norm(f"{r[1]} {r[2] or ''}")
        valor = 2 * bool(EGPP.search(t)) + bool(lugar and lugar.search(t))
        if not (r[5] or "").startswith("historia:"):  # lo vivo: primero lo del cliente que recibe avisos, luego lo minero
            return (0, -(6 * bool(suyo.search(t)) + 3 * bool(CLIENTE.search(t)) + valor))
        return (1, -valor)
    return sorted(sorted(filas, key=lambda r: r[3] or "", reverse=True), key=clave)  # estable: fecha desc dentro


def resumen(con):
    """Notas por medio y año, y cuántas pasan el filtro."""
    con.execute(ESQUEMA)
    return con.execute("""SELECT medio, substr(mes, 1, 4) AS anio, sum(vistas), sum(pasan) FROM historia_conteo
        GROUP BY 1, 2 ORDER BY 1, 2""").fetchall()
