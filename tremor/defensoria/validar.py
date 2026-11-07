"""Extrae cada reporte, lo compara con sus propios totales y guarda el panel caso-mes (Historia 4)."""
import csv
import difflib
import json
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
    sin = sum(x.contar_lista(s["texto"]) for s in secs if s["canonica"] == "activos_sin_hechos")
    lat = sum(x.contar_lista(s["texto"]) for s in secs if s["canonica"] == "latentes")
    return {"totales": tot, "fichas": fichas, "sin_hechos": sin, "latentes": lat,
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
    return ("valido" if dif == 0 else "aproximado" if dif <= TOLERANCIA else "fallido"), d


def _clave(s: str | None) -> str:
    return re.sub(r"[^a-z0-9 ]", "", x._sin_tildes((s or "").lower()))[:200]


def enlazar(con, f: dict, usados: set, num: int) -> tuple[int, float]:
    """caso.id para una ficha: por código si lo tiene; si no, por la descripción en el mismo departamento."""
    if f.get("codigo"):
        fila = con.execute("SELECT id FROM caso WHERE codigo = ?", (f["codigo"],)).fetchone()
        if fila and fila[0] not in usados:
            return fila[0], 1.0
    desc = _clave(f.get("descripcion"))
    mejor, puntaje = None, 0.0
    # Candidatos: casos del departamento vistos en los últimos 12 reportes (un caso dormido más de un año
    # vuelve como caso nuevo; ponytail: ventana fija, ampliarla si aparecen duplicados por reactivación).
    candidatos = con.execute(
        "SELECT DISTINCT c.id, c.descripcion FROM caso c JOIN caso_mes cm ON cm.caso_id = c.id"
        " WHERE c.departamento IS ? AND cm.reporte_num >= ?", (f.get("departamento"), num - 12))
    sm = difflib.SequenceMatcher(None, b=desc)
    for cid, cdesc in candidatos:
        if cid in usados:  # un caso aparece una sola vez por reporte
            continue
        sm.set_seq1(cdesc or "")
        if sm.real_quick_ratio() <= puntaje or sm.quick_ratio() <= max(puntaje, 0.8):
            continue
        p = sm.ratio()
        if p > puntaje:
            mejor, puntaje = cid, p
    if mejor is not None and puntaje >= 0.8:
        if f.get("codigo"):
            con.execute("UPDATE OR IGNORE caso SET codigo = ? WHERE id = ? AND codigo IS NULL", (f["codigo"], mejor))
        return mejor, round(puntaje, 3)
    # Un código ya tomado (la misma ficha repetida en el reporte) no se vuelve a asignar.
    libre = f.get("codigo") and not con.execute("SELECT 1 FROM caso WHERE codigo = ?", (f["codigo"],)).fetchone()
    cur = con.execute("INSERT INTO caso (codigo, nombre, tipo, departamento, descripcion) VALUES (?, ?, ?, ?, ?)",
                      (f["codigo"] if libre else None, f.get("nombre"), f.get("tipo"), f.get("departamento"), desc))
    return cur.lastrowid, 0.0


def validar(con, desde: int = 90) -> dict:
    """Procesa los reportes pendientes (en orden, para que el enlace vaya del pasado al presente)."""
    cuenta = {}
    docs = con.execute("SELECT d.* FROM documento d LEFT JOIN reporte r ON r.num = d.reporte_num"
                       " WHERE d.rol = 'principal' AND d.reporte_num >= ? AND r.num IS NULL"
                       " ORDER BY d.reporte_num", (desde,)).fetchall()
    for doc in docs:
        n = doc["reporte_num"]
        r = procesar(doc)
        estado, det = veredicto(r)
        tot = r["totales"]
        con.execute("INSERT INTO reporte (num, anio, mes, huella, total, activos, latentes, en_dialogo,"
                    " acciones_declaradas, estado, detalle_validacion) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (n, doc["anio"], doc["mes"], doc["huella"], tot.get("total"), tot.get("activos"),
                     tot.get("latentes"), tot.get("en_dialogo"), tot.get("acciones"), estado, json.dumps(det)))
        for titulo, canon, pag in r["secciones"]:
            con.execute("INSERT OR IGNORE INTO seccion (reporte_num, titulo_original, canonica, pagina_inicio)"
                        " VALUES (?,?,?,?)", (n, titulo, canon, pag))
        usados = set()
        for f in r["fichas"]:
            caso_id, conf = enlazar(con, f, usados, n)
            usados.add(caso_id)
            con.execute("INSERT INTO caso_mes (caso_id, reporte_num, estado, con_hechos, fase, dialogo,"
                        " competencia, actores_primarios, actores_secundarios, actores_terciarios, descripcion,"
                        " hechos_mes, pagina, enlace_confianza) VALUES (?,?,'activo',1,?,?,?,?,?,?,?,?,?,?)",
                        (caso_id, n, f.get("fase"), f.get("dialogo"), f.get("competencia"),
                         f.get("actores_primarios"), f.get("actores_secundarios"), f.get("actores_terciarios"),
                         f.get("descripcion"), f.get("hechos_mes"), f["pagina"], conf))
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
    }
    for nombre, sql in consultas.items():
        cur = con.execute(sql)
        with open(EXPORTES / nombre, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow([c[0] for c in cur.description])
            w.writerows(cur)
