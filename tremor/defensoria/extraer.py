"""Secciones, totales y fichas de casos de cada reporte (Historias 3 y 4 de la spec).

Solo reglas fijas: los reportes tienen títulos de sección y etiquetas de ficha estables. Cubre el
formato de 2012 en adelante. Los reportes de 2004 a 2011 quedan como `formato_antiguo`.
"""
import re
import unicodedata

from bs4 import BeautifulSoup

from tremor.defensoria.catalogo import CRUDOS

# Encabezado de departamento: "Amazonas" o, en 2012-2014, "Amazonas: Tres (3)" y "Amazonas / San Martín: un (1)...".
_DEP = re.compile(r"^(%s)(?:\s*(?::|/).*)?$" % "|".join(sorted({d.replace("_", " ") for d in
                  "Amazonas|Áncash|Ancash|Apurímac|Arequipa|Ayacucho|Cajamarca|Callao|Cusco|Huancavelica|"
                  "Huánuco|Ica|Junín|La Libertad|Lambayeque|Lima|Lima Metropolitana|Lima Provincias|Loreto|"
                  "Madre de Dios|Moquegua|Pasco|Piura|Puno|San Martín|Tacna|Tumbes|Ucayali|"
                  "Multirregional|Nacional".split("|")}, key=len, reverse=True)), re.I)

# Títulos de sección (PDF) → sección canónica. El orden importa: el primero que calza gana.
SECCIONES = [
    (r"conflictos activos que no registraron hechos", "activos_sin_hechos"),
    (r"pasado de estado activo a latente|trasladados del", "cambio_estado"),
    (r"detalle de los conflictos (sociales )?activos|conflictos (sociales )?(activos )?desarrollados en (un solo|m[aá]s de un) departamento|conflictos reactivados|"
     r"^conflictos (sociales )?activos\.",  # 2008-2011: "1.1 Conflictos activos. La Defensoría da cuenta..."
     "fichas_activos"),
    (r"detalle de los conflictos latentes|^conflictos latentes", "latentes"),
    (r"conflictos resueltos", "resueltos"),
    (r"salido del registro|casos fusionados|casos que salieron", "retirados"),
    (r"casos en observaci[oó]n", "observacion"),
    (r"conflictos sociales nuevos", "casos_nuevos"),
    (r"acciones colectivas de protesta", "acciones_protesta"),
    (r"hechos de violencia", "victimas"),
    (r"alertas", "alertas"),
    (r"di[aá]logo", "dialogo"),
    (r"cumplimiento de acuerdos", "acuerdos"),
    (r"estado de los conflictos|frecuencia|competencias|ubicaci[oó]n geogr[aá]fica|de acuerdo a tipo|socioambientales|unidad(es)? funcional|"
     r"fases de los|activos por tipo|otros indicadores|actuaciones defensoriales|glosario|violencia subversiva",
     "estadisticas"),
]
# Secciones del HTML (2026 en adelante), por su id.
SECCIONES_HTML = {
    "sec-casos": "fichas_activos", "sec-casos-multi": "fichas_activos",
    "sec-activos-sin-hechos": "activos_sin_hechos", "sec-latentes": "latentes",
    "sec-resueltos": "resueltos", "sec-nuevos": "casos_nuevos", "sec-violencia": "victimas",
    "sec-protestas": "acciones_protesta", "sec-alertas-prioritarias": "alertas",
    "sec-acuerdos": "acuerdos", "sec-mediacion": "dialogo", "sec-portada": "resumen",
}
_MES_RE = "enero|febrero|marzo|abril|mayo|junio|julio|agosto|setiembre|septiembre|octubre|noviembre|diciembre"
_TITULO = re.compile(r"^\s*(?:[IVX]+\.|\d{1,2}\.\d{1,2}(?:\.\d)?)\s+([A-ZÁÉÍÓÚÑ].{6,})$")
# 2012-2013: títulos sin numeración. Solo estos abren sección (las fichas tienen otras líneas en mayúsculas).
_TITULO_SUELTO = re.compile(r"^\s*(DETALLE DE LOS CONFLICTOS SOCIALES ACTIVOS|DETALLE DE LOS CONFLICTOS LATENTES|"
                            r"Conflictos (?:activos|latentes|resueltos|reactivados)\..*|ACCIONES COLECTIVAS DE PROTESTA|"
                            r"CONFLICTOS RESUELTOS|CASOS EN OBSERVACI[OÓ]N)\s*$")
_RUIDO = re.compile(r"^\s*(Reporte Mensual de Conflictos Sociales N.*|ADJUNT[ÍI]A PARA LA PREVENCI.*|\d{1,3}|"
                    r"Descripci[oó]n|Hechos del mes|Estado actual|NUEVO)\s*$", re.I)

PALABRAS = {w: i for i, w in enumerate("cero uno dos tres cuatro cinco seis siete ocho nueve diez once doce "
                                       "trece catorce quince dieciséis diecisiete dieciocho diecinueve veinte".split())}
PALABRAS.update({"ninguno": 0, "ninguna": 0, "un": 1, "una": 1})


def _sin_tildes(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def paginas(doc) -> list[tuple[int, str]]:
    """[(número de página, texto)] de un documento descargado."""
    ruta = CRUDOS / f"{doc['huella']}.{doc['formato']}"
    if doc["formato"] == "html":
        return [(1, _texto_html(ruta))]
    import pymupdf
    pymupdf.TOOLS.mupdf_display_errors(False)
    with pymupdf.open(ruta) as d:
        return [(i + 1, _texto_con_columnas(p)) for i, p in enumerate(d)]


DERECHA = "  "  # prefijo de las líneas de la columna derecha (espacio: \s lo absorbe en las demás reglas)


def _texto_con_columnas(pagina) -> str:
    """Texto de la página en el orden de PyMuPDF, marcando las líneas de la columna derecha.

    En las fichas la columna derecha trae el diálogo y los hechos del mes; cuando una ficha cruza de página,
    ese texto queda antes de los actores y sin la marca se pierde."""
    mitad = pagina.rect.width * 0.5
    lineas = []
    for b in pagina.get_text("blocks"):
        if b[6] != 0:
            continue
        pref = DERECHA if b[0] > mitad else ""
        lineas += [pref + l for l in b[4].splitlines()]
    return "\n".join(lineas)


def _texto_html(ruta) -> str:
    sopa = BeautifulSoup(ruta.read_text(encoding="utf-8", errors="replace"), "html.parser")
    for s in sopa(["script", "style"]):
        s.decompose()
    return sopa.get_text("\n")


def secciones(doc, pags) -> list[dict]:
    """Divide el reporte en secciones canónicas con su texto y su página de inicio."""
    if doc["formato"] == "html":
        # Los id "sec-*" son anclas: el contenido de cada sección va hasta el ancla siguiente.
        sopa = BeautifulSoup((CRUDOS / f"{doc['huella']}.html").read_text(encoding="utf-8", errors="replace"),
                             "html.parser")
        for t in sopa(["script", "style"]):
            t.decompose()
        for a in sopa.find_all(id=re.compile(r"^sec-")):
            a.insert_before(f"\n@@SEC {a['id']}@@\n")
        out = []
        for trozo in sopa.get_text("\n").split("\n@@SEC ")[1:]:
            id_, _, texto = trozo.partition("@@\n")
            out.append({"titulo": id_, "canonica": SECCIONES_HTML.get(id_, "otra"), "pagina": 1, "texto": texto})
        return out
    out, actual = [], {"titulo": "inicio", "canonica": "resumen", "pagina": 1, "lineas": []}
    for num, texto in pags:
        for linea in texto.splitlines():
            m = _TITULO.match(linea) or _TITULO_SUELTO.match(linea)
            if m:
                titulo = m.group(1).strip()
                canon = next((c for p, c in SECCIONES if re.search(p, titulo, re.I)), "no_mapeada")
                if canon == "no_mapeada" and not titulo.isupper():
                    actual["lineas"].append(linea)  # "1. Agricultura:" dentro de los hechos de una ficha
                    continue
                out.append(actual)
                actual = {"titulo": titulo, "canonica": canon, "pagina": num, "lineas": []}
                continue
            if not _RUIDO.match(linea):
                actual["lineas"].append(linea)
    out.append(actual)
    for s in out:
        s["texto"] = "\n".join(s.pop("lineas"))
    return out


def _num(s: str) -> int | None:
    s = s.strip().lower()
    if s.isdigit():
        return int(s)
    m = re.match(r"(\w+)", _sin_tildes(s))
    return PALABRAS.get(m.group(1)) if m else None


def totales(texto: str) -> dict:
    """Totales que el reporte declara de sí mismo en el resumen."""
    t = re.sub(r"\s+", " ", texto)
    out = {}
    m = re.search(r"Se da cuenta de (\d+) conflictos sociales(?: registrados)?:? (\d+) ?activos(.{0,120}?) y (\d+) latentes", t)
    if m:
        out = {"total": int(m.group(1)), "activos": int(m.group(2)), "latentes": int(m.group(4))}
        d = re.search(r"(\d+) est[aá]n en (?:proceso de )?di[aá]logo", m.group(3))
        if d:
            out["en_dialogo"] = int(d.group(1))
    else:
        m = re.search(r"Se da cuenta de (\d+) conflictos activos y (\d+) conflictos latentes", t)
        if m:
            out = {"activos": int(m.group(1)), "latentes": int(m.group(2))}
            out["total"] = out["activos"] + out["latentes"]
    if not out:  # 2005-2011: "da cuenta de (la existencia de) 77 conflictos, de los cuales 32 se encuentran activos
        # (42%), 45 en estado latente"; las cifras pueden ir en palabras ("siete permanecen activos").
        m = re.search(r"(\w+) conflictos(?: sociales)?(?:, de los cuales|:) (\w+) (?:se encuentran|permanecen) activos"
                      r" \(\d+%\),? (?:y |mientras que )?(\w+) (?:se encuentran |permanecen )?(?:en )?estado latente", t)
        if m and None not in (vals := [_num(g) for g in m.groups()]):
            out = {"total": vals[0], "activos": vals[1], "latentes": vals[2]}
    m = re.search(r"Acciones colectivas de protesta registradas:? (\d+)", t)
    if m:
        out["acciones"] = int(m.group(1))
    return out


# Etiquetas de la ficha de un caso, en el orden en que suelen aparecer.
ETIQUETAS = [
    ("codigo", r"C[oó]digo:"), ("tipo", r"Tipo:"),
    ("ingreso", r"Ingres[oó] (?:como (?:caso )?(?:nuevo|reactivado)|al registro):"), ("competencia", r"Competencia:"),
    ("fase_dialogo", r"Fase\s*/\s*Di[aá]logo:"), ("actuaciones", r"Actuaciones DP:"),
    ("descripcion", r"Caso:"), ("ubicacion", r"Ubicaci[oó]n:"),
    ("actores_primarios", r"Actores(?:\s+[Pp]rimarios)?:"), ("actores_secundarios", r"Actores\s+[Ss]ecundarios:"),
    ("actores_terciarios", r"Actores\s+[Tt]erciarios:"),
]
# En 2012 algunas fichas usan punto ("Caso.", "Ubicación."): se acepta solo al inicio de línea.
_ETIQ = re.compile("|".join(f"(?P<{k}>{p}|(?m:^)[ \\t]*{p[:-1]}\\.)" for k, p in ETIQUETAS))
_DIALOGO = re.compile(r"\b(NO HAY DI[AÁ]LOGO|HAY DI[AÁ]LOGO)\b", re.I)
_FASES = r"temprana|escalamiento|crisis|desescalamiento|acuerdos"


def fichas(texto: str) -> list[dict]:
    """Fichas de casos activos. Cada ficha empieza en su etiqueta 'Tipo:' (o 'Código:' si la precede)."""
    lineas = texto.splitlines()
    depto, inicios = None, []
    for i, l in enumerate(lineas):
        m = _DEP.match(l.strip())
        if m:
            depto = m.group(1)
        if re.match(r"\s*(C[oó]digo:|Tipo:)", l):
            # 'Tipo:' y 'Código:' seguidos, en cualquier orden, son la misma ficha.
            entre = [z for z in lineas[inicios[-1][0] + 1:i] if z.strip()] if inicios else []
            if inicios and len(entre) <= 2 and lineas[inicios[-1][0]].strip()[:4] != l.strip()[:4]:
                continue
            nombre = None
            for j in range(i - 1, max(i - 8, -1), -1):  # en el HTML el nombre va encima: "Wampis - X (Amazonas)"
                if re.search(r"\(([^)]+)\)\s*$", lineas[j]) and len(lineas[j]) < 160:
                    nombre = re.sub(r"\s*\([^)]+\)\s*$", "", lineas[j]).strip()
                    break
            inicios.append((i, depto, nombre))
    out = []
    for k, (i, dep, nombre) in enumerate(inicios):
        fin = inicios[k + 1][0] if k + 1 < len(inicios) else len(lineas)
        bloque = "\n".join(lineas[i:fin])
        f = _campos(bloque)
        if "descripcion" not in f and "ubicacion" not in f:
            continue  # 'Tipo:' suelto fuera de una ficha
        f["departamento"], f["nombre"] = dep, nombre
        out.append(f)
    return out


# Tipología de la Defensoría. El texto viene escrito de ~95 formas ("Asunto de Gobierno nacional",
# "Socioambiental. HAY DIÁLOGO"...); se lleva a la categoría por palabras clave.
TIPOS = [("socioambiental", "Socioambiental"), ("comunal", "Comunal"), ("nacional", "Asuntos de gobierno nacional"),
         ("regional", "Asuntos de gobierno regional"), ("local", "Asuntos de gobierno local"), ("laboral", "Laboral"),
         ("demarcaci", "Demarcación territorial"), ("electoral", "Electoral"), ("coca", "Cultivo ilegal de hoja de coca"),
         ("justicia", "Asuntos de administración de justicia"), ("universidad", "Conflictos en universidades"),
         ("otro", "Otros asuntos")]


def tipo_canonico(t: str) -> str | None:
    t = _sin_tildes((t or "").lower())
    return next((canon for clave, canon in TIPOS if clave in t), None)


def _campos(bloque: str) -> dict:
    derecha = "\n".join(l.strip() for l in bloque.splitlines() if l.startswith(DERECHA))
    if derecha:  # PDF a dos columnas: diálogo y hechos salen de la columna derecha
        bloque = "\n".join(l for l in bloque.splitlines() if not l.startswith(DERECHA))
    marcas = [(m.start(), m.end(), m.lastgroup) for m in _ETIQ.finditer(bloque)]
    f = {}
    for k, (ini, fin, clave) in enumerate(marcas):
        hasta = marcas[k + 1][0] if k + 1 < len(marcas) else len(bloque)
        if clave not in f:
            f[clave] = bloque[fin:hasta]
    resto = f.pop("actores_terciarios", "")
    m = _DIALOGO.search(resto)
    if derecha:
        f["actores_terciarios"] = resto[:m.start()] if m else resto
        md = _DIALOGO.search(derecha)
        f["dialogo"] = md.group(1).upper() if md else None
        f["hechos_mes"] = (derecha[:md.start()] + derecha[md.end():]) if md else derecha
        f["hechos_mes"] = re.sub(r"^\s*(Hechos del mes|Estado actual|NUEVO)\s*$", "", f["hechos_mes"], flags=re.M | re.I)
    elif m:
        f["actores_terciarios"], f["hechos_mes"] = resto[:m.start()], resto[m.end():]
        f["dialogo"] = m.group(1).upper()
    else:
        partes = re.split(r"\n\s*(?=(?:El|La|Los|Las|Del|Desde|Entre|Durante|En)\s[^\n]*\d)", resto, maxsplit=1)
        f["actores_terciarios"] = partes[0]
        f["hechos_mes"] = partes[1] if len(partes) > 1 else ""
    f = {k: re.sub(r"\s+", " ", v or "").strip(" .") for k, v in f.items()}
    f["tipo"] = tipo_canonico(f.get("tipo", ""))
    fd = f.pop("fase_dialogo", "")
    if fd:
        fase, _, dia = fd.partition("·")
        f["fase"], f["dialogo"] = fase.strip().lower() or None, dia.strip().upper() or f.get("dialogo")
    if f.get("codigo"):
        m = re.search(r"\d{3,4}-\d{4}", f["codigo"])
        f["codigo"] = m.group(0) if m else None
    return f


def contar_lista(texto: str) -> int:
    """Filas de una lista de casos (activos sin hechos o latentes)."""
    # Columna de inicio: "03/2025" (2026) o "Jul-17" (2025).
    fechas = len(re.findall(r"^\s*(?:\d{2}/\d{4}|[A-Z][a-z]{2}-\d{2})\s*$", texto, re.M))
    tipos = len(re.findall(r"^\s*Tipo\s+[a-záéíóú]", texto, re.M))  # "Tipo socioambiental"
    numerados = len(set(re.findall(r"^\s*(\d{1,3})\.\s*$", texto, re.M)))  # "1." en la columna N.°
    return max(fechas, tipos, numerados)


def declarado_en_seccion(texto: str) -> int | None:
    """Número que la propia sección declara: 'da cuenta de 47 conflictos latentes', 'Se registraron 56 casos'."""
    t = re.sub(r"\s+", " ", texto[:1500])
    m = re.search(r"(?:existencia de|registraron|se registraron) (\d+) (?:conflictos|casos)", t)
    return int(m.group(1)) if m else None


# "01/06/2017", "2/08/2026" o, en 2014-2015, "5 de octubre".
_FECHA = re.compile(r"^(\d{1,2}/\d{1,2}/\d{2,4}|\d{1,2} de (?:%s))" % _MES_RE, re.I)
COLUMNAS = ("fecha", "medida", "actores", "lugar", "demanda")


def acciones(doc, paginas_: list[int]) -> list[dict]:
    """Filas de la tabla de acciones colectivas de protesta, con find_tables() de PyMuPDF.

    Según el año, la tabla tiene celdas combinadas y la fecha no cae bajo su encabezado; por eso cada fila
    se lee por contenido: la primera celda con fecha y las cuatro celdas no vacías que la siguen (medida,
    actores, lugar y demanda). Al inicio de una página, las filas sin fecha de una tabla con las mismas
    columnas continúan la última fila (fila partida entre páginas)."""
    import pymupdf
    pymupdf.TOOLS.mupdf_display_errors(False)
    filas, ultima = [], None  # ultima: (número de columnas, índice de cada campo) de la última fila
    with pymupdf.open(CRUDOS / f"{doc['huella']}.pdf") as d:
        for num in paginas_:
            if num > len(d):
                continue
            for nt, t in enumerate(d[num - 1].find_tables().tables):
                # Pueden continuar la fila anterior las filas sin fecha de la misma tabla (texto partido en
                # varias líneas) o de la primera tabla de la página siguiente (fila partida entre páginas).
                misma = ultima is not None and (ultima[2] == (num, nt) or (nt == 0 and ultima[2][0] == num - 1))
                for celdas in t.extract():
                    celdas = [re.sub(r"\s+", " ", c or "").strip() for c in celdas]
                    llenas = [(i, c) for i, c in enumerate(celdas) if c]
                    k = next((j for j, (_, c) in enumerate(llenas) if _FECHA.match(c)), None)
                    if k is not None and len(llenas) - k >= 5:
                        campos = llenas[k:k + 4] + [(llenas[k + 4][0], " ".join(c for _, c in llenas[k + 4:]))]
                        fila = dict(zip(COLUMNAS, (c for _, c in campos)), pagina=num)
                        fila["fecha"] = _FECHA.match(fila["fecha"]).group(1)
                        filas.append(fila)
                        ultima = (len(celdas), [i for i, _ in campos], (num, nt))
                        misma = True
                    elif misma and llenas and len(celdas) == ultima[0]                             and not any(_sin_tildes(c.lower()).startswith("fecha") for _, c in llenas):
                        for i, c in llenas:  # cada trozo va al campo cuya columna está más cerca a su izquierda
                            col = max((n for n, ic in enumerate(ultima[1]) if ic <= i), default=0)
                            if col:
                                filas[-1][COLUMNAS[col]] += " " + c
        fechas = sum(len(_FECHA_SOLA.findall(d[p - 1].get_text())) for p in paginas_ if p <= len(d))
        if len(filas) < fechas:  # tabla sin líneas internas (p. ej. n.° 166, 173, 174)
            alt, centros = [], None
            for num in (p for p in paginas_ if p <= len(d)):
                fs, centros = _acciones_por_posicion(d[num - 1], centros)
                alt += [dict(f, pagina=num) for f in fs]
            if len(filas) < len(alt) <= fechas:  # más filas, pero nunca más que fechas tiene el texto
                return alt
    return filas


# La fecha sola en su línea; en 2014 viene partida: "1 de" / "septiembre".
_FECHA_SOLA = re.compile(r"^\s*(?:\d{1,2}/\d{1,2}/\d{2,4}|\d{1,2} de\s+(?:%s))\s*$" % _MES_RE, re.M | re.I)
_CABECERAS = ("Fecha", "Medida", "Actores", "Lugar", "Demanda")  # en 2014 "Lugar" se llama "Ámbito"


def _acciones_por_posicion(pagina, centros=None):
    """Filas de la tabla de protestas armadas por la posición de cada línea de texto, para tablas sin líneas.

    Cada línea va a la columna cuyo encabezado le queda más cerca; cada fecha abre una fila que va hasta la
    mitad del camino a la fecha siguiente (las celdas vienen centradas en vertical). Los centros de las
    columnas se toman del encabezado y se arrastran a las páginas siguientes que no lo repiten.
    ponytail: la última línea corta de una celda ancha puede caer en la columna vecina."""
    ws = pagina.get_text("words")
    cab = {}
    for w in sorted(ws, key=lambda w: w[1]):
        nombre = "Lugar" if w[4] == "Ámbito" else w[4]
        cab.setdefault(nombre, w) if nombre in _CABECERAS else None
    tope = 0
    if len(cab) == 5 and max(w[1] for w in cab.values()) - min(w[1] for w in cab.values()) < 15:
        centros = [(cab[k][0] + cab[k][2]) / 2 for k in _CABECERAS]
        tope = max(w[3] for w in cab.values())
    if not centros:
        return [], centros
    grupos = {}
    for w in ws:
        if w[1] >= tope and not re.fullmatch(r"\d{1,3}\.", w[4]):  # sin la columna N.°
            grupos.setdefault((w[5], w[6]), []).append(w)
    # 1.a pasada: cada línea a la columna cuyo encabezado le queda más cerca de su centro.
    prev = []
    for l in grupos.values():
        x0 = min(w[0] for w in l)
        medio = (x0 + max(w[2] for w in l)) / 2
        prev.append((min(range(5), key=lambda k: abs(medio - centros[k])), x0, l))
    # 2.a pasada: una línea pasa a la columna de su derecha solo si empieza donde empiezan las líneas de esa
    # columna (mediana del borde izquierdo). Corrige la última línea corta de una celda ancha ("(CNM)"),
    # cuyo centro cae cerca del encabezado vecino.
    bordes = []
    for k in range(5):
        xs = sorted(x0 for c, x0, _ in prev if c == k)
        bordes.append(xs[len(xs) // 2] if xs else None)
    lineas = []
    for c, x0, l in prev:
        if c < 4 and bordes[c + 1] is not None and x0 >= bordes[c + 1] - 3:
            c += 1
        lineas.append((c, (l[0][1] + l[0][3]) / 2, " ".join(w[4] for w in sorted(l, key=lambda w: w[0]))))
    lineas.sort(key=lambda l: l[1])
    fechas = [(y, t) for c, y, t in lineas if c == 0 and re.match(r"\d{1,2}(?:/\d{1,2}/\d{2,4}| de\b)", t)]
    filas = []
    for i, (y, t) in enumerate(fechas):
        y0 = (fechas[i - 1][0] + y) / 2 if i else tope
        y1 = (y + fechas[i + 1][0]) / 2 if i + 1 < len(fechas) else pagina.rect.height - 50
        fila = {"fecha": " ".join(t2 for c, y2, t2 in lineas if c == 0 and y0 <= y2 < y1)}
        for k, nombre in enumerate(COLUMNAS[1:], 1):
            fila[nombre] = " ".join(t2 for c, y2, t2 in lineas if c == k and y0 <= y2 < y1)
        filas.append(fila)
    return filas, centros


def acciones_en_texto(doc, paginas_: list[int]) -> int:
    """Fechas sueltas en líneas propias: cuántas filas trae la tabla según el texto, para separar un error
    del lector de una tabla que la propia Defensoría publica incompleta."""
    import pymupdf
    pymupdf.TOOLS.mupdf_display_errors(False)
    with pymupdf.open(CRUDOS / f"{doc['huella']}.pdf") as d:
        t = "\n".join(d[p - 1].get_text() for p in paginas_ if p <= len(d))
    return len(_FECHA_SOLA.findall(t))


def acciones_declaradas(texto: str) -> int | None:
    m = re.search(r"(?:registrado|registraron)\s+(\d[\d ]*)\s+acciones colectivas", re.sub(r"\s+", " ", texto))
    return int(m.group(1).replace(" ", "")) if m else None


def victimas_declaradas(texto: str) -> dict:
    """Fallecidos y heridos del mes según la frase del inicio de la sección ("se registró cuatro heridos")."""
    t = _sin_tildes(re.sub(r"\s+", " ", texto[:800]).lower())
    t = re.sub(r"\s*\(\d+\)", "", t)  # "cinco (05) heridos"
    # Solo la primera oración con cifras de víctimas: la siguiente suele traer el acumulado del año.
    for oracion in re.split(r"\.\s", t):
        out = {"fallecidos": 0, "heridos": 0}
        for cantidad, tipo in re.findall(r"(\d+|\w+) (?:personas )?(herid[oa]s?|fallecid[oa]s?|muert[oa]s?)", oracion):
            n = _num(cantidad)
            if n is not None:
                out["heridos" if tipo.startswith("herid") else "fallecidos"] += n
        if any(out.values()):
            return out
    return {"fallecidos": 0, "heridos": 0}


def victimas(doc, pagina: int) -> list[dict]:
    """Filas de la tabla "muertos y/o heridos": lugar o caso y seis valores (muertos total, civiles, PNP;
    heridos total, civiles, PNP). La primera fila es el TOTAL. Un nombre sin valores completa la fila anterior."""
    import pymupdf
    pymupdf.TOOLS.mupdf_display_errors(False)
    filas = []
    with pymupdf.open(CRUDOS / f"{doc['huella']}.pdf") as d:
        if pagina > len(d):
            return []
        for t in d[pagina - 1].find_tables().tables:
            for celdas in t.extract():
                llenas = [re.sub(r"\s+", " ", c).strip() for c in celdas if c and c.strip()]
                if llenas and re.match(r"(Cuadro|Fuente|Nota|Gr[aá]fico)", llenas[0]):
                    return filas  # termina la tabla; lo que sigue son los cuadros por mes
                valores = [c for c in llenas if re.fullmatch(r"\d+|-", c)]
                nombre = " ".join(c for c in llenas if not re.fullmatch(r"\d+|-", c))
                if len(re.findall(r"(?:Ene|Feb|Mar|Abr|May|Jun|Jul|Ago|Set|Sep|Oct|Nov|Dic)", nombre)) >= 3:
                    return filas  # fila del gráfico por mes que sigue a la tabla
                if len(valores) == 6 and nombre:
                    v = [0 if c == "-" else int(c) for c in valores]
                    filas.append({"lugar_caso": nombre, "fallecidos": v[0], "heridos": v[3], "pagina": pagina})
                elif nombre and not valores and filas and filas[-1]["lugar_caso"] != "TOTAL":
                    filas[-1]["lugar_caso"] += " – " + nombre
    return filas


_MESES_CORTOS = {m[:3]: i for i, m in enumerate("enero febrero marzo abril mayo junio julio agosto setiembre octubre noviembre diciembre".split(), 1)} | {"sep": 9}


def periodo(s: str | None) -> tuple[int, int] | None:
    """(año, mes) de "Diciembre de 2008", "Julio 2017", "12/2018" o "Jul-17"."""
    t = _sin_tildes((s or "").lower())
    m = re.search(r"(%s)\s+(?:de\s+|del\s+)?(\d{4})" % _MES_RE, t)
    if m:
        return int(m.group(2)), _MESES_CORTOS[m.group(1)[:3]]
    m = re.search(r"\b(\d{1,2})/(\d{4})\b", t)
    if m:
        return int(m.group(2)), int(m.group(1))
    m = re.search(r"\b([a-z]{3})-(\d{2})\b", t)
    if m and m.group(1) in _MESES_CORTOS:
        return 2000 + int(m.group(2)), _MESES_CORTOS[m.group(1)]
    return None


_INICIO = re.compile(r"^(?:\d{2}/\d{4}|[A-Z][a-z]{2}-\d{2})$")
_NUM = re.compile(r"^\d{1,3}\.$")
_SIN_NOVEDAD = re.compile(r"^(?:No se registran|nuevos|acontecimientos\.?)$", re.I)


def filas_lista(texto: str) -> list[dict]:
    """Casos de una lista (activos sin hechos o latentes), con lo que la lista trae de cada uno.

    2025-2026: "Inicio, Departamento, Denominación, Tipología" (la fila empieza en la fecha de inicio).
    2012-2024: filas numeradas "N." con departamento, ubicación, tipo y descripción."""
    ls = [l.strip() for l in texto.splitlines() if l.strip()]
    inicios = [i for i, l in enumerate(ls) if _INICIO.match(l)]
    filas = []
    if inicios:
        for a, b in zip(inicios, inicios[1:] + [len(ls)]):
            seg = [l for l in ls[a + 1:b] if not _NUM.match(l)]
            k = next((j for j in range(2, len(seg)) if tipo_canonico(seg[j])), None)
            if len(seg) < 2:
                continue
            nombre = " ".join(seg[1:k] if k else seg[1:2])
            filas.append({"ingreso": ls[a], "departamento": seg[0], "nombre": nombre, "descripcion": nombre,
                          "tipo": tipo_canonico(seg[k]) if k else None})
        return filas
    nums = []  # solo la primera numeración corrida: lo que viene tras un reinicio en "1." es otra lista
    for i, l in enumerate(ls):
        if _NUM.match(l):
            if nums and int(l[:-1]) <= int(ls[nums[-1]][:-1]):
                break
            nums.append(i)
    for a, b in zip(nums, nums[1:] + [len(ls)]):
        seg = ls[a + 1:b]
        if not seg:
            continue
        k = next((j for j, l in enumerate(seg) if re.match(r"(Tipo|Conflicto)\b", l)), None)
        tipo = tipo_canonico(" ".join(seg[k:k + 2])) if k is not None else None
        if k is not None and k <= 6:  # 2015-2024: ubicación hasta "Tipo x", luego la descripción
            ubic, desc = seg[1:k], seg[k + 1:]
        else:  # 2012-2014: "(Distrito ..., provincia ...)" tras el departamento; el tipo va en otra columna
            fin = next((j for j, l in enumerate(seg) if ")" in l), 0) if seg[1:2] and seg[1].startswith("(") else 0
            ubic = seg[1:fin + 1]
            desc = [l for j, l in enumerate(seg[fin + 1:], fin + 1)
                    if not (k is not None and j in (k, k + 1)) and not _SIN_NOVEDAD.match(l)]
        filas.append({"departamento": seg[0].title(), "ubicacion": " ".join(ubic).strip("() "),
                      "descripcion": re.sub(r"\s+", " ", " ".join(desc)).strip(), "tipo": tipo})
    return filas


def victimas_html(ruta) -> list[dict]:
    """Filas de la tabla "Departamento / Caso · Fallecidos · Heridos" del reporte en HTML (2026).

    Columnas: caso, y civiles, PNP, FF. AA. y total, primero de fallecidos y luego de heridos."""
    sopa = BeautifulSoup(ruta.read_text(encoding="utf-8", errors="replace"), "html.parser")
    tabla = next((t for t in sopa.find_all("table") if "Departamento / Caso" in t.get_text()), None)
    filas = []
    for tr in tabla.find_all("tr") if tabla else []:
        celdas = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
        if len(celdas) == 9 and celdas[4].isdigit() and celdas[8].isdigit():
            lugar = "TOTAL" if celdas[0].upper().startswith("TOTAL") else re.sub(r"\)\s.*", ")", celdas[0])
            filas.append({"lugar_caso": lugar, "fallecidos": int(celdas[4]), "heridos": int(celdas[8]), "pagina": None})
    return filas
