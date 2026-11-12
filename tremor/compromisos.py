"""Compromisos con fecha en los conflictos de la Defensoría y si se cumplieron.

Una oración con un acuerdo o una reunión programada ("se acordó una nueva reunión para el 7 de julio de 2026") y una
fecha posterior al mes del reporte es un compromiso. Se sigue en los tres reportes siguientes del mismo caso: si
nombran esa fecha, se dice qué pasó (se realizó, no se realizó o solo se menciona) con la página del PDF; si un
reporte ya cubre ese mes y no la nombra, queda "sin noticia". Cada uno lleva el PDF abierto en su página.

    python -m tremor.compromisos
"""
import re
import sys
import time
from datetime import date

from tremor.db import conectar

MESES = "enero febrero marzo abril mayo junio julio agosto setiembre octubre noviembre diciembre".split()
CLAVE = re.compile(r"acord|compromet|se reunir|pr[oó]xima (?:reuni|sesi)|nueva (?:reuni|sesi)|programad|convoc|"
                   r"se instalar|plazo|se realizar|se llevar[aá] a cabo|fecha prevista", re.I)
FECHA = re.compile(r"\b(\d{1,2})(?:\s*(?:,|y|al)\s*\d{1,2})*\s+de\s+(" + "|".join(MESES) + r"|septiembre)(?:\s+(?:de|del)\s+(\d{4}))?", re.I)
HECHO = re.compile(r"se realiz|se llev[oó] a cabo|se reunieron|sesion[oó]|se desarroll|se instal[oó]|particip", re.I)
TIPOS = [("Mesa de diálogo", r"mesa|grupo de trabajo|comit[eé] de"), ("Visita o inspección", r"visita|inspecci|monitoreo|verificaci"),
         ("Pago", r"\bpago|\bpagar|indemniz|compensaci"), ("Obra o proyecto", r"\bobra|licitaci|ejecuci|expediente t[eé]cnico|perfil"),
         ("Entrega de información", r"inform|respuesta|entreg|present|remit|alcanz"), ("Reunión", r"reuni|sesi[oó]n|cita|convoc")]


def tipo(frase):
    """Qué se pactó, en dos o tres palabras: la web no publica la frase (puede nombrar personas), sí su página."""
    return next((t for t, r in TIPOS if re.search(r, frase, re.I)), "Compromiso")


NO_HECHO = re.compile(r"no se (?:realiz|llev)|se suspendi|se posterg|se reprogram|no asisti|sin la presencia|frustr", re.I)


# La fecha tiene que ir pegada a una forma de futuro o de plazo ("para el 7 de julio", "a más tardar el", "se realizará
# el"). Sin eso es un hecho ya ocurrido que el reporte narra del mes siguiente ("el 9 de octubre se reunieron").
FUTURO = re.compile(r"(?:\bpara|\bhasta|m[aá]s tardar|\bantes de|se realizar[aá]n?|se llevar[aá]n? a cabo|se llevar[ií]a"
                    r"|se reunir[aá]n?|se instalar[aá]|programad[oa]s?|fecha|pr[oó]xim[oa]|se compromet\w*|"
                    r"comprometi[oó]|convoc\w*)\s+(?:\w+\s+){0,3}$", re.I)


def fechas(oracion, anio, mes, futuro=True):
    """Fechas que nombra la oración, posteriores al mes del reporte y anunciadas en futuro (el año que falta es el del
    reporte o el siguiente). Con futuro=False, todas: sirve para buscar el seguimiento."""
    fin = date(anio + mes // 12, mes % 12 + 1, 1)  # primer día del mes siguiente al reporte
    salida = []
    for x in FECHA.finditer(oracion):
        if futuro and not FUTURO.search(oracion[max(0, x.start() - 60):x.start()]):
            continue
        d, m, a = x.groups()
        mm = MESES.index(m.lower().replace("septiembre", "setiembre")) + 1
        aa = int(a) if a else anio + (mm < mes)
        try:
            f = date(aa, mm, int(d))
        except ValueError:
            continue
        if f >= fin or not futuro:
            salida.append(f)
    return salida


def compromisos(texto, anio, mes):
    """[(fecha, oración)] de un texto de "hechos del mes"."""
    return [(f, o.strip()) for o in re.split(r"(?<=[.;])\s+", texto or "") if CLAVE.search(o) and not re.search(r"se venci|\bparo|huelga|bloqueo|movilizaci", o, re.I)
            for f in fechas(o, anio, mes)]


def seguimiento(f, despues):
    """despues: [(reporte_num, anio, mes, pagina, texto)] de los reportes siguientes del caso. Devuelve
    (estado, reporte_num, pagina, oración)."""
    for num, anio, mes, pag, texto in despues:
        for o in re.split(r"(?<=[.;])\s+", texto or ""):
            # la misma fecha, o una a dos días (la reunión del 7 que se hizo el 8)
            gs = fechas(o, f.year, f.month, futuro=False)
            estado = "no se realizó" if NO_HECHO.search(o) else "se realizó" if HECHO.search(o) else "mencionado"
            if f in gs or (estado != "mencionado" and any(abs((g - f).days) <= 2 for g in gs)):
                return estado, num, pag, o.strip()
    cubre = any((a, m) >= (f.year, f.month) and len(t or "") > 40 for _, a, m, _, t in despues)  # el caso sí tiene hechos ese mes
    return ("sin noticia" if cubre else "pendiente"), None, None, None


plano = lambda s: re.sub(r"[\W_]+", "", (s or "").lower())  # sin espacios ni guiones: el PDF parte las líneas


def pagina_real(paginas, frase):
    """Página del PDF donde está la frase. La de caso_mes es donde empieza la ficha o la sección, no la frase."""
    f = plano(frase)
    for trozo in (f[:50], f[len(f) // 2:len(f) // 2 + 50], f[-50:]):
        donde = [i + 1 for i, t in enumerate(paginas) if len(trozo) >= 20 and trozo in t]
        if donde:
            return donde[0]
    return None


def textos_pdf(huella, url):
    """Texto plano de cada página del reporte (se baja una vez a datos/crudos/defensoria). [] si no se puede."""
    import pymupdf
    pymupdf.TOOLS.mupdf_display_errors(False)
    import requests
    from tremor.defensoria.catalogo import CRUDOS
    ruta = CRUDOS / f"{huella}.pdf"
    if not ruta.exists():
        try:
            r = requests.get(url, timeout=120, headers={"User-Agent": "Mozilla/5.0 (tremor; investigacion PUCP)"})
            if not r.content.startswith(b"%PDF"):
                return []  # Wayback a veces responde con una página de bloqueo
            ruta.parent.mkdir(parents=True, exist_ok=True)
            ruta.write_bytes(r.content)
            time.sleep(2)
        except Exception:
            return []
    try:
        with pymupdf.open(ruta) as d:
            return [plano(p.get_text()) for p in d]
    except Exception:
        return []


def cargar(con):
    con.execute("""CREATE TABLE IF NOT EXISTS compromiso (caso_id INTEGER, reporte_num INTEGER, fecha TEXT, frase TEXT,
                   pagina INTEGER, enlace TEXT, estado TEXT, visto_num INTEGER, visto_pagina INTEGER, visto_frase TEXT,
                   visto_enlace TEXT, PRIMARY KEY (caso_id, reporte_num, fecha, frase))""")
    # el reporte en PDF (con página) o, si solo salió en HTML (el 271), su página web
    pdf = {n: (u, h, f) for n, u, h, f in con.execute("""SELECT reporte_num, url, huella, formato FROM documento
            WHERE rol = 'principal' AND formato IN ('pdf', 'html') ORDER BY formato = 'pdf'""")}
    paginas = {}  # reporte → {frase: página}; se llena abajo, un PDF a la vez

    def enlace(n, frase):
        p = paginas.get(n, {}).get(frase)
        return pdf.get(n) and (pdf[n][0] + (f"#page={p}" if p else "")), p
    filas = con.execute("""SELECT cm.caso_id, cm.reporte_num, r.anio, r.mes, cm.pagina, cm.hechos_mes FROM caso_mes cm
                           JOIN reporte r ON r.num = cm.reporte_num ORDER BY cm.caso_id, cm.reporte_num""").fetchall()
    por_caso = {}
    for fila in filas:
        por_caso.setdefault(fila[0], []).append(fila[1:])
    hallados = []
    for caso, meses in por_caso.items():
        for k, (num, anio, mes, _, texto) in enumerate(meses):
            for f, frase in compromisos(texto, anio, mes):
                estado, vn, _, vf = seguimiento(f, meses[k + 1:k + 4])
                hallados.append((caso, num, f, frase, estado, vn, vf))
    buscar = {}
    for _, num, _, frase, _, vn, vf in hallados:
        buscar.setdefault(num, set()).add(frase)
        if vn:
            buscar.setdefault(vn, set()).add(vf)
    # Las páginas ya buscadas se conservan: cada corrida solo baja el PDF del reporte nuevo. Una frase sin página se
    # vuelve a buscar solo en los tres últimos reportes (allí la falla suele ser de descarga, no del texto).
    recientes = {n for n, in con.execute("SELECT num FROM reporte ORDER BY num DESC LIMIT 3")}
    previas = {}
    for n, fr, p, vn, vf, vp in con.execute("SELECT reporte_num, frase, pagina, visto_num, visto_frase, visto_pagina FROM compromiso"):
        previas[(n, fr)] = p
        if vn:
            previas[(vn, vf)] = vp
    for n, frases in sorted(buscar.items()):
        paginas[n] = {fr: previas[(n, fr[:600])] for fr in frases
                      if (n, fr[:600]) in previas and (previas[(n, fr[:600])] or n not in recientes)}
        nuevas = frases - set(paginas[n])
        if nuevas and n in pdf and pdf[n][2] == "pdf":
            textos = textos_pdf(pdf[n][1], pdf[n][0])
            paginas[n] |= {fr: pagina_real(textos, fr) for fr in nuevas}
    salida = []
    for caso, num, f, frase, estado, vn, vf in hallados:
        (url, p), (vurl, vp) = enlace(num, frase), (enlace(vn, vf) if vn else (None, None))
        salida.append((caso, num, f.isoformat(), frase[:600], p, url, estado, vn, vp, vf and vf[:600], vurl))
    con.execute("DELETE FROM compromiso")
    con.executemany("INSERT OR IGNORE INTO compromiso VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", salida)
    con.commit()
    return salida


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    s = cargar(conectar())
    from collections import Counter
    print(f"{len(s)} compromisos en {len({x[0] for x in s})} casos:", dict(Counter(x[6] for x in s)))
