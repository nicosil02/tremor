"""Extrae cada reporte, lo compara con sus propios totales y guarda el panel caso-mes (Historia 4)."""
import csv
import json
import math
import re

from tremor.db import DATOS
from tremor.defensoria import extraer as x

# ponytail: diferencia de hasta 3 casos se acepta como "aproximado". En esos meses el detalle de la
# Defensoría trae fichas reales de más o de menos frente a su propio resumen (revisado en 239 y 252).
TOLERANCIA = 3
EXPORTES = DATOS / "exportes"


def procesar(doc) -> dict:
    """Todo lo que se puede leer de un reporte, sin tocar la base."""
    pags = x.paginas(doc)
    secs = x.secciones(doc, pags)
    portada = "\n".join(s["texto"] for s in secs if s["titulo"] == "sec-portada")
    tot = x.totales(portada or "\n".join(t for _, t in pags[:6]))
    fichas, pagina_de = [], {}
    for s in secs:
        if s["canonica"] == "fichas_activos":
            for f in x.fichas(s["texto"]):
                f["pagina"] = s["pagina"]
                fichas.append(f)
    # Fichas que el propio texto trae (etiqueta "Caso" al inicio de línea), para distinguir un error
    # del lector de un reporte que publica menos fichas de las que declara.
    en_texto = sum(len(re.findall(r"^\s*Caso[:.]", s["texto"], re.M))
                   for s in secs if s["canonica"] == "fichas_activos")
    sin = sum(x.contar_lista(s["texto"]) for s in secs if s["canonica"] == "activos_sin_hechos")
    lat = sum(x.contar_lista(s["texto"]) for s in secs if s["canonica"] == "latentes")
    lista = [dict(f, estado="latente" if s["canonica"] == "latentes" else "activo", pagina=s["pagina"])
             for s in secs if s["canonica"] in ("activos_sin_hechos", "latentes") for f in x.filas_lista(s["texto"])]
    # Acciones colectivas de protesta (Historia 5): solo en los PDF con la tabla de detalle.
    ks = [i for i, s in enumerate(secs) if s["canonica"] == "acciones_protesta"]
    pags_acc = sorted({p for k in ks for p in range(secs[k]["pagina"],
                       (secs[k + 1]["pagina"] if k + 1 < len(secs) else len(pags)) + 1)})
    acc = x.acciones(doc, pags_acc) if doc["formato"] == "pdf" and pags_acc else []
    if "acciones" not in tot:
        decl = next((v for k in ks if (v := x.acciones_declaradas(secs[k]["texto"]))), None)
        if decl is not None:
            tot["acciones"] = decl
    acc_texto = x.acciones_en_texto(doc, pags_acc) if acc else 0
    # Víctimas: el total que declara el texto manda; el detalle por caso se guarda solo si la fila TOTAL de
    # la tabla coincide con él (en algunos meses find_tables corre las celdas de columna, p. ej. n.° 200).
    sv = next((s for s in secs if s["canonica"] == "victimas"), None)
    vict_decl = x.victimas_declaradas(sv["texto"]) if sv else None
    if not sv:
        vict = []
    elif doc["formato"] == "pdf":
        vict = x.victimas(doc, sv["pagina"])
    else:
        vict = x.victimas_html(x.CRUDOS / f"{doc['huella']}.html")
    return {"totales": tot, "fichas": fichas, "fichas_en_texto": en_texto, "acciones": acc, "acciones_en_texto": acc_texto,
            "victimas": vict, "victimas_declaradas": vict_decl, "sin_hechos": sin, "latentes": lat, "lista": lista,
            "secciones": [(s["titulo"], s["canonica"], s["pagina"]) for s in secs]}


def veredicto(r: dict) -> tuple[str, dict]:
    tot = r["totales"]
    if "activos" not in tot:
        return "sin_totales", {}
    d = {"activos_declarados": tot["activos"], "activos_leidos": len(r["fichas"]) + r["sin_hechos"],
         "latentes_declarados": tot["latentes"], "latentes_leidos": r["latentes"]}
    difs = [abs(d["activos_declarados"] - d["activos_leidos"])]
    if d["latentes_leidos"] * 2 < d["latentes_declarados"]:
        d["nota"] = "el reporte no lista todos los latentes (2012); se validan solo los activos"
    else:
        difs.append(abs(d["latentes_declarados"] - d["latentes_leidos"]))
    if d["activos_leidos"] == 0:
        d["nota"] = "texto del PDF desarmado (p. ej. '18 4 conflictos'); no se puede leer con reglas"
    dif = max(difs)
    if r.get("acciones"):
        d["acciones_declaradas"], d["acciones_leidas"] = tot.get("acciones"), len(r["acciones"])
        d["acciones_en_texto"] = r["acciones_en_texto"]
    if dif > TOLERANCIA and r.get("fichas_en_texto") == len(r["fichas"]) and d["activos_leidos"]:
        d["nota"] = (f"el reporte publica {len(r['fichas'])} fichas y todas se leyeron; "
                     "faltan en la fuente, no en la lectura")
        return "fuente_incompleta", d
    return ("valido" if dif == 0 else "aproximado" if dif <= TOLERANCIA else "fallido"), d


STOP = set("para como entre sobre desde contra hasta porque donde cuando este esta estos estas dicho dicha "
           "tambien ante bajo cual cuales pero segun sector parte sus las los del que por con una uno".split())
# Umbral elegido midiendo en los 182 reportes: con 0.3 quedan ~1 600 casos frente a ~1 530 códigos oficiales,
# y los 96 enlaces verificables con código de 2026 salen todos bien. Por debajo de 0.3 empieza a unir
# comunidades distintas que solo comparten palabras como "minera" o "comunidad".
UMBRAL = 0.3
PESOS = (0.6, 0.2, 0.2)  # descripción, ubicación, actores primarios


def tokens(s):
    return frozenset(w for w in re.findall(r"[a-z0-9]{4,}", x._sin_tildes((s or "").lower())) if w not in STOP)


def depto(d):
    d = x._sin_tildes((d or "").lower()).strip()
    return "lima" if d.startswith("lima") else d


def _parecido(a, b, idf):
    """Jaccard ponderado por IDF: pesan más los nombres propios que 'comunidad' o 'minera'."""
    if not (a and b):
        return 0.0
    peso = lambda conj: sum(idf.get(t, 8.0) for t in conj)
    total = peso(a | b)
    return peso(a & b) / total if total else 0.0


def puntaje(f, c, idf):
    """Parecido de texto, corregido por la fecha de ingreso: si ambos la tienen y difiere, son casos distintos;
    si coincide (mismo mes y año, mismo departamento), es casi seguro el mismo caso."""
    if f["_ing"] and c["_ing"] and f["_ing"] != c["_ing"]:
        return 0.0
    p = (PESOS[0] * _parecido(f["_d"], c["_d"], idf) + PESOS[1] * _parecido(f["_u"], c["_u"], idf)
         + PESOS[2] * _parecido(f["_a"], c["_a"], idf))
    return p + BONO_INGRESO if f["_ing"] and f["_ing"] == c["_ing"] else p


BONO_INGRESO = 0.3


def _con_tokens(f):
    return dict(f, _d=tokens(f.get("descripcion")) | tokens(f.get("nombre")), _u=tokens(f.get("ubicacion")),
                _a=tokens(f.get("actores_primarios")), _dep=depto(f.get("departamento")),
                _ing=x.periodo(f.get("ingreso")))


def calcular_idf(textos):
    df, n = {}, 0
    for t in textos:
        n += 1
        for w in tokens(t):
            df[w] = df.get(w, 0) + 1
    return {w: math.log(n / k) for w, k in df.items()}


def enlazar_reporte(fichas, casos, idf):
    """Asigna cada ficha a un caso conocido o a ninguno (None = caso nuevo).

    Primero por código; luego, dentro del mismo departamento, se ordenan todos los pares ficha-caso por
    puntaje y se asignan de mayor a menor, cada caso una sola vez por reporte. Cada caso se compara con su
    versión más reciente, porque la Defensoría reescribe la descripción con los años."""
    fs = [_con_tokens(f) for f in fichas]
    asignado, usados = {}, set()
    por_codigo = {c["codigo"]: cid for cid, c in casos.items() if c.get("codigo")}
    for i, f in enumerate(fs):
        cid = por_codigo.get(f.get("codigo"))
        if cid is not None and cid not in usados:
            asignado[i] = (cid, 1.0)
            usados.add(cid)
    pares = []
    for i, f in enumerate(fs):
        if i in asignado:
            continue
        for cid, c in casos.items():
            if c["_dep"] == f["_dep"] and cid not in usados:
                p = puntaje(f, c, idf)
                if p >= UMBRAL:
                    pares.append((p, i, cid))
    for p, i, cid in sorted(pares, reverse=True):
        if i not in asignado and cid not in usados:
            asignado[i] = (cid, round(p, 3))
            usados.add(cid)
    return [asignado.get(i, (None, 0.0)) for i in range(len(fs))]


def caso_de_victima(lugar: str, del_mes, idf, umbral: float = 0.5):
    """Caso del mes al que corresponde una fila de víctimas ("ÁNCASH – Caso Huaripampa - Nyrstar").

    Mismo departamento y la mayor parte (ponderada por IDF) de las palabras de la fila presentes en el caso.
    Se mide qué parte de la fila está en el caso, no Jaccard: la fila es corta y la ficha larga."""
    cod = re.search(r"\((\d{3,4}-\d{4})\)", lugar or "")  # 2026: "Piura · Comunidad X (1193-1020)"
    if cod:
        cid = next((cid for cid, c in del_mes if c.get("codigo") == cod.group(1)), None)
        if cid is not None:
            return cid
        lugar = lugar[:cod.start()]
    if "·" in (lugar or ""):
        dep, _, resto = lugar.partition("·")
        lugar = f"{resto} ({dep.strip()})"
    m = re.search(r"\(([^)]+)\)\W*$", lugar or "")  # 2025-2026: "Caso: Atupa y Antahurán – Barrick (Áncash)"
    if m:
        dep, resto = m.group(1), lugar[:m.start()]
    else:  # 2014-2024: "ÁNCASH – Caso Huaripampa - Nyrstar"
        dep, _, resto = (lugar or "").replace("–", "-").partition(" - ")
    t = tokens(resto) - {"caso"}
    if not t:
        return None
    peso = lambda conj: sum(idf.get(w, 8.0) for w in conj)
    mejor = max(((peso(t & (c["_d"] | c["_u"] | c["_a"])) / (peso(t) or 1), cid) for cid, c in del_mes
                 if c["_dep"] == depto(dep)), default=(0, None))
    return mejor[1] if mejor[0] >= umbral else None


def _cargar_casos(con):
    return {c["id"]: _con_tokens({"descripcion": c["descripcion"], "ubicacion": c["ubicacion"],
                                  "actores_primarios": c["actores"], "departamento": c["departamento"],
                                  "codigo": c["codigo"], "ingreso": c["ingreso"], "nombre": c["nombre"]})
            for c in con.execute("SELECT * FROM caso")}


# Antes del n.° 50 (abril de 2008) las fichas no siguen un formato estable: solo se guardan los totales.
PRIMERO_CON_FICHAS = 50


def validar(con, desde: int = 1) -> dict:
    """Procesa los reportes pendientes en orden, para que el enlace vaya del pasado al presente."""
    cuenta = {}
    docs = con.execute("SELECT d.* FROM documento d LEFT JOIN reporte r ON r.num = d.reporte_num"
                       " WHERE d.rol = 'principal' AND d.reporte_num >= ? AND r.num IS NULL"
                       " ORDER BY d.reporte_num", (desde,)).fetchall()
    leidos = [(doc, procesar(doc)) for doc in docs]
    # IDF sobre todas las fichas conocidas: las ya guardadas y las de esta corrida.
    textos = [" ".join(filter(None, (f.get("descripcion"), f.get("ubicacion"), f.get("actores_primarios"))))
              for _, r in leidos for f in r["fichas"] + r.get("lista", [])]
    textos += [" ".join(filter(None, fila)) for fila in
               con.execute("SELECT descripcion, ubicacion, actores_primarios FROM caso_mes")]
    idf = calcular_idf(textos)
    casos = _cargar_casos(con)
    for doc, r in leidos:
        n = doc["reporte_num"]
        if n < PRIMERO_CON_FICHAS:
            r.update(fichas=[], lista=[], acciones=[], victimas=[], victimas_declaradas=None)
            estado, det = ("solo_totales" if "activos" in r["totales"] else "sin_totales"), {}
        else:
            estado, det = veredicto(r)
        tot = r["totales"]
        con.execute("INSERT INTO reporte (num, anio, mes, huella, total, activos, latentes, en_dialogo,"
                    " acciones_declaradas, estado, detalle_validacion) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (n, doc["anio"], doc["mes"], doc["huella"], tot.get("total"), tot.get("activos"),
                     tot.get("latentes"), tot.get("en_dialogo"), tot.get("acciones"), estado,
                     json.dumps(det, ensure_ascii=False)))
        for titulo, canon, pag in r["secciones"]:
            con.execute("INSERT OR IGNORE INTO seccion (reporte_num, titulo_original, canonica, pagina_inicio)"
                        " VALUES (?,?,?,?)", (n, titulo, canon, pag))
        for k, ac in enumerate(r.get("acciones", []), 1):
            con.execute("INSERT INTO accion_protesta (reporte_num, n, fecha, medida, actores, lugar, demanda, pagina)"
                        " VALUES (?,?,?,?,?,?,?,?)", (n, k, ac["fecha"], ac["medida"], ac["actores"], ac["lugar"],
                                                      ac["demanda"], ac["pagina"]))
        tomados = {c.get("codigo") for c in casos.values()}
        items = r["fichas"] + r.get("lista", [])
        del_mes = []  # (caso, tokens) de este reporte, para enlazar las víctimas
        for k, (f, (cid, conf)) in enumerate(zip(items, enlazar_reporte(items, casos, idf))):
            ficha = k < len(r["fichas"])  # las filas de las listas traen menos texto: no pisan la versión del caso
            # Un código ya tomado (la misma ficha repetida en el reporte) no se vuelve a asignar.
            codigo = f.get("codigo") if f.get("codigo") not in tomados else None
            if codigo:
                tomados.add(codigo)
            if cid is None:
                cid = con.execute("INSERT INTO caso (codigo, nombre, tipo, departamento, descripcion, ubicacion,"
                                  " actores, ingreso) VALUES (?,?,?,?,?,?,?,?)",
                                  (codigo, f.get("nombre"), f.get("tipo"), f.get("departamento"),
                                   f.get("descripcion"), f.get("ubicacion"), f.get("actores_primarios"),
                                   f.get("ingreso"))).lastrowid
                casos[cid] = _con_tokens(f)
            else:
                if ficha:  # se guarda la versión más reciente del caso
                    con.execute("UPDATE caso SET descripcion = ?, ubicacion = ?, actores = ? WHERE id = ?",
                                (f.get("descripcion"), f.get("ubicacion"), f.get("actores_primarios"), cid))
                con.execute("UPDATE caso SET codigo = COALESCE(codigo, ?), nombre = COALESCE(?, nombre),"
                            " ingreso = COALESCE(ingreso, ?), tipo = COALESCE(tipo, ?) WHERE id = ?",
                            (codigo, f.get("nombre"), f.get("ingreso"), f.get("tipo"), cid))
                previo = casos[cid]
                base = f if ficha else {**previo, "nombre": previo.get("nombre") or f.get("nombre")}
                casos[cid] = _con_tokens(dict(base, codigo=previo.get("codigo") or codigo,
                                              ingreso=previo.get("ingreso") or f.get("ingreso"),
                                              departamento=previo.get("departamento") or f.get("departamento")))
            del_mes.append((cid, _con_tokens(f)))
            con.execute("INSERT INTO caso_mes (caso_id, reporte_num, estado, con_hechos, fase, dialogo,"
                        " competencia, ubicacion, actores_primarios, actores_secundarios, actores_terciarios,"
                        " descripcion, hechos_mes, pagina, enlace_confianza)"
                        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (cid, n, f.get("estado", "activo"), int(ficha), f.get("fase"), f.get("dialogo"),
                         f.get("competencia"), f.get("ubicacion"), f.get("actores_primarios"),
                         f.get("actores_secundarios"), f.get("actores_terciarios"), f.get("descripcion"),
                         f.get("hechos_mes"), f["pagina"], conf))
        if r.get("victimas_declaradas"):
            vd, filas_v = r["victimas_declaradas"], r.get("victimas", [])
            total = next((v for v in filas_v if v["lugar_caso"] == "TOTAL"), None)
            if total and (total["fallecidos"], total["heridos"]) == (vd["fallecidos"], vd["heridos"]):
                filas_v = [v for v in filas_v if v["lugar_caso"] != "TOTAL"]
            else:
                filas_v = [{"lugar_caso": "TOTAL del mes (sin detalle por caso: la tabla no cuadra con el texto)",
                            "pagina": None, **vd}] if vd["fallecidos"] or vd["heridos"] else []
            for v in filas_v:
                con.execute("INSERT INTO victimas (reporte_num, caso_id, lugar_caso, fallecidos, heridos, pagina)"
                            " VALUES (?,?,?,?,?,?)", (n, caso_de_victima(v["lugar_caso"], del_mes, idf), v["lugar_caso"],
                                                    v["fallecidos"], v["heridos"], v["pagina"]))
        con.commit()
        cuenta[estado] = cuenta.get(estado, 0) + 1
    return cuenta


def exportar(con):
    """CSV de reportes y del panel caso-mes en datos/exportes/."""
    EXPORTES.mkdir(parents=True, exist_ok=True)
    consultas = {
        "reportes.csv": "SELECT num, anio, mes, total, activos, latentes, en_dialogo, acciones_declaradas,"
                        " estado, detalle_validacion FROM reporte ORDER BY num",
        "casos.csv": "SELECT id, codigo, nombre, tipo, departamento FROM caso ORDER BY id",
        "caso_mes.csv": "SELECT cm.reporte_num, r.anio, r.mes, cm.caso_id, c.codigo, c.tipo, c.departamento,"
                        " cm.fase, cm.dialogo, cm.competencia, cm.actores_primarios, cm.actores_secundarios,"
                        " cm.actores_terciarios, cm.hechos_mes, cm.pagina, cm.enlace_confianza"
                        " FROM caso_mes cm JOIN caso c ON c.id = cm.caso_id JOIN reporte r ON r.num = cm.reporte_num"
                        " ORDER BY cm.reporte_num, cm.caso_id",
        "acciones_protesta.csv": "SELECT a.reporte_num, r.anio, r.mes, a.n, a.fecha, a.medida, a.actores, a.lugar,"
                                 " a.demanda, a.pagina FROM accion_protesta a JOIN reporte r ON r.num = a.reporte_num"
                                 " ORDER BY a.reporte_num, a.n",
        "victimas.csv": "SELECT v.reporte_num, r.anio, r.mes, v.lugar_caso, v.fallecidos, v.heridos, v.pagina"
                        " FROM victimas v JOIN reporte r ON r.num = v.reporte_num ORDER BY v.reporte_num",
    }
    for nombre, sql in consultas.items():
        cur = con.execute(sql)
        with open(EXPORTES / nombre, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow([c[0] for c in cur.description])
            w.writerows(cur)
