"""Secciones, totales y fichas de casos de cada reporte (Historias 3 y 4 de la spec).

Solo reglas fijas: los reportes tienen títulos de sección y etiquetas de ficha estables. Cubre el
formato de 2012 en adelante. Los reportes de 2004 a 2011 quedan como `formato_antiguo`.
"""
import re
import unicodedata

from bs4 import BeautifulSoup

from tremor.defensoria.catalogo import CRUDOS

_DEP = re.compile(r"^(%s)$" % "|".join(sorted({d.replace("_", " ") for d in
                  "Amazonas|Áncash|Ancash|Apurímac|Arequipa|Ayacucho|Cajamarca|Callao|Cusco|Huancavelica|"
                  "Huánuco|Ica|Junín|La Libertad|Lambayeque|Lima|Lima Metropolitana|Lima Provincias|Loreto|"
                  "Madre de Dios|Moquegua|Pasco|Piura|Puno|San Martín|Tacna|Tumbes|Ucayali|"
                  "Multirregional|Nacional".split("|")}, key=len, reverse=True)), re.I)

# Títulos de sección (PDF) → sección canónica. El orden importa: el primero que calza gana.
SECCIONES = [
    (r"conflictos activos que no registraron hechos", "activos_sin_hechos"),
    (r"pasado de estado activo a latente|trasladados del", "cambio_estado"),
    (r"detalle de los conflictos (sociales )?activos|conflictos (sociales )?(activos )?desarrollados en (un solo|m[aá]s de un) departamento|conflictos reactivados",
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
_TITULO = re.compile(r"^\s*(?:[IVX]+\.|\d\.\d(?:\.\d)?)\s+([A-ZÁÉÍÓÚÑ].{6,})$")
# 2012-2013: títulos sin numeración. Solo estos abren sección (las fichas tienen otras líneas en mayúsculas).
_TITULO_SUELTO = re.compile(r"^\s*(DETALLE DE LOS CONFLICTOS SOCIALES ACTIVOS|DETALLE DE LOS CONFLICTOS LATENTES|"
                            r"Conflictos (?:latentes|resueltos|reactivados)\..*|ACCIONES COLECTIVAS DE PROTESTA|"
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
        return [(i + 1, p.get_text()) for i, p in enumerate(d)]


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
    ("actores_primarios", r"Actores\s+primarios:"), ("actores_secundarios", r"Actores\s+secundarios:"),
    ("actores_terciarios", r"Actores\s+terciarios:"),
]
_ETIQ = re.compile("|".join(f"(?P<{k}>{p})" for k, p in ETIQUETAS))
_DIALOGO = re.compile(r"\b(NO HAY DI[AÁ]LOGO|HAY DI[AÁ]LOGO)\b", re.I)
_FASES = r"temprana|escalamiento|crisis|desescalamiento|acuerdos"


def fichas(texto: str) -> list[dict]:
    """Fichas de casos activos. Cada ficha empieza en su etiqueta 'Tipo:' (o 'Código:' si la precede)."""
    lineas = texto.splitlines()
    depto, inicios = None, []
    for i, l in enumerate(lineas):
        if _DEP.match(l.strip()):
            depto = l.strip()
        if re.match(r"\s*(C[oó]digo:|Tipo:)", l):
            # 'Tipo:' y 'Código:' seguidos, en cualquier orden, son la misma ficha.
            if inicios and i - inicios[-1][0] <= 3 and lineas[inicios[-1][0]].strip()[:4] != l.strip()[:4]:
                continue
            nombre = None
            for j in range(i - 1, max(i - 4, -1), -1):  # en el HTML el nombre va encima: "Wampis - X (Amazonas)"
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


def _campos(bloque: str) -> dict:
    marcas = [(m.start(), m.end(), m.lastgroup) for m in _ETIQ.finditer(bloque)]
    f = {}
    for k, (ini, fin, clave) in enumerate(marcas):
        hasta = marcas[k + 1][0] if k + 1 < len(marcas) else len(bloque)
        if clave not in f:
            f[clave] = bloque[fin:hasta]
    resto = f.pop("actores_terciarios", "")
    m = _DIALOGO.search(resto)
    if m:
        f["actores_terciarios"], f["hechos_mes"] = resto[:m.start()], resto[m.end():]
        f["dialogo"] = m.group(1).upper()
    else:
        partes = re.split(r"\n\s*(?=(?:El|La|Los|Las|Del|Desde|Entre|Durante|En)\s[^\n]*\d)", resto, maxsplit=1)
        f["actores_terciarios"] = partes[0]
        f["hechos_mes"] = partes[1] if len(partes) > 1 else ""
    f = {k: re.sub(r"\s+", " ", v).strip(" .") for k, v in f.items()}
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
