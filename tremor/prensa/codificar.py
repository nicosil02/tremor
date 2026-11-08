"""Codifica cada nota con las variables del manual de la EGPP + estado anunciada/ocurrida/suspendida (FR-009).

El LLM devuelve nombres; el ubigeo lo pone lugares.resolver (research R3). Lotes de 25 notas por solicitud.
ponytail: una codificación por nota (la protesta principal); separar varias protestas por nota si la validación lo pide.
"""
import json
import re
from pathlib import Path

from tremor.egpp import tipo_conflicto
from tremor.llm import RespuestaInvalida, SinCuota, chat_json
from tremor.lugares import norm, resolver

VERSION = "v2"
LOTE = 15
CODIGOS = json.loads((Path(__file__).resolve().parent.parent / "codigos_egpp.json").read_text(encoding="utf-8"))
ESTADOS = {"anunciada", "ocurrida", "suspendida"}

SISTEMA = f"""Eres codificador de la Base de Protestas Sociales del Perú (EGPP PUCP). Para cada nota de prensa decide
si informa una protesta EN EL PERÚ y codifícala.

Protesta = acción colectiva (2+ personas), pública, contenciosa (contra los intereses de alguien) y episódica.
No son protesta: elecciones, actos oficiales, deportes, procesos judiciales sobre protestas pasadas, opiniones.
A diferencia de la EGPP, también cuentan las protestas ANUNCIADAS (convocadas para una fecha futura).

Responde SOLO un JSON {{"notas": [...]}} con un objeto por nota, con estas claves:
- id: el mismo id recibido
- es_protesta: true/false (false también si ocurre fuera del Perú)
- estado: "anunciada" (aún no ocurre), "ocurrida" (ocurre u ocurrió) o "suspendida" (se levantó o canceló)
- fecha_evento: AAAA-MM-DD de la protesta (resuelve "mañana", "el lunes", "desde el 15" con la fecha de publicación); null si no se sabe
- region, provincia, distrito, localidad: nombres tal como permite inferir la nota (localidad = comunidad, centro poblado,
  carretera o puente); null si no se sabe. No inventes: si solo dice el departamento, deja el resto en null.
- sector y actor: de las listas (actor debe pertenecer al sector)
- accion: de la lista de acciones
- adversario: de la lista; empresa: nombre de la empresa si se nombra; operacion: proyecto, mina, lote o unidad si se nombra
- reclamo y sub_reclamo: de las listas (sub_reclamo debe pertenecer al reclamo)
- heridos, muertos, detenidos: números si la nota los da; si no, null
Si la protesta ocurre FUERA DEL PERÚ (Argentina, Bolivia, Chile, Colombia, Ecuador, México, Venezuela, España, Francia…),
es_protesta = false aunque la nota sea de un medio peruano.
"departamento_de_la_busqueda" es solo la búsqueda que trajo la nota, NO es el lugar: no lo copies en region salvo que la
nota hable de ese lugar.
Si es_protesta es false, las demás claves pueden ser null. Usa exactamente los textos de las listas o null.

SECTORES Y ACTORES: {json.dumps(CODIGOS["sector_actor"], ensure_ascii=False)}
ACCIONES: {json.dumps(CODIGOS["accion"], ensure_ascii=False)}
ADVERSARIOS: {json.dumps(CODIGOS["adversario"], ensure_ascii=False)}
RECLAMOS Y SUB-RECLAMOS: {json.dumps(CODIGOS["reclamo"], ensure_ascii=False)}"""

_FECHA = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _num(x):
    try:
        return int(x) if x is not None and str(x).strip() != "" else None
    except (TypeError, ValueError):
        return None


def limpiar(item: dict) -> dict:
    """Respuesta del LLM → valores válidos: lo que no está en las listas queda en None (FR-009)."""
    g = lambda k: (item.get(k) or None) if isinstance(item.get(k), (str, type(None))) else None
    sector = g("sector") if g("sector") in CODIGOS["sector_actor"] else None
    actores = CODIGOS["sector_actor"].get(sector) or [a for v in CODIGOS["sector_actor"].values() for a in v]
    reclamo = g("reclamo") if g("reclamo") in CODIGOS["reclamo"] else None
    subs = CODIGOS["reclamo"].get(reclamo) or [s for v in CODIGOS["reclamo"].values() for s in v]
    es = item.get("es_protesta") is True
    return {
        "es_protesta": int(es),
        "estado": g("estado") if g("estado") in ESTADOS else None,
        "fecha_evento": g("fecha_evento") if _FECHA.match(g("fecha_evento") or "") else None,
        **{k: g(k) for k in ("region", "provincia", "distrito", "localidad", "empresa", "operacion")},
        "sector": sector, "actor": g("actor") if g("actor") in actores else None,
        "accion": g("accion") if g("accion") in CODIGOS["accion"] else None,
        "adversario": g("adversario") if g("adversario") in CODIGOS["adversario"] else None,
        "reclamo": reclamo, "sub_reclamo": g("sub_reclamo") if g("sub_reclamo") in subs else None,
        **{k: _num(item.get(k)) for k in ("heridos", "muertos", "detenidos")},
    }


COLUMNAS = ["es_protesta", "estado", "fecha_evento", "region", "provincia", "distrito", "localidad", "ubigeo",
            "precision", "sector", "actor", "accion", "adversario", "empresa", "operacion", "reclamo", "sub_reclamo",
            "heridos", "muertos", "detenidos", "tipo_conflicto"]


def ubicar(c, texto, pista):
    """ubigeo con lugares.resolver; si solo hay departamento y la nota no lo nombra, el LLM lo copió de la
    búsqueda (o la protesta es de otro país): queda sin lugar."""
    ubigeo, precision = resolver(c["region"], c["provincia"], c["distrito"], c["localidad"], pista=pista)
    if precision == "departamento" and norm(c["region"] or "") not in norm(texto):
        return None, None
    return ubigeo, precision


def _pedir(con, entrada) -> dict:
    """Un lote → {id: respuesta}. Si el modelo devuelve JSON inválido, parte el lote en dos (hasta una nota)."""
    try:
        resp = chat_json(con, SISTEMA, json.dumps(entrada, ensure_ascii=False), VERSION)
        return {str(x.get("id")): x for x in resp.get("notas", []) if isinstance(x, dict)}
    except RespuestaInvalida as e:
        if len(entrada) == 1:
            print(f"  Nota {entrada[0]['id']} sin codificar: {e}")
            return {}
        m = len(entrada) // 2
        return _pedir(con, entrada[:m]) | _pedir(con, entrada[m:])


def codificar(con, max_solicitudes=200) -> tuple[int, int, bool]:
    """Codifica las notas que pasaron el filtro y no tienen codificación de esta versión.
    Devuelve (solicitudes, notas, quedó_pendiente)."""
    from tremor.prensa.historia import ordenar  # lo vivo primero; la historia por valor (lugar con operación)
    pendientes = ordenar(con, con.execute("""SELECT n.id, n.titular, n.resumen, n.publicado, n.departamento_consulta,
        n.consulta FROM nota n
        WHERE n.filtro IS NULL AND NOT EXISTS (SELECT 1 FROM codificacion c WHERE c.nota_id = n.id AND c.version = ?)
        """, (VERSION,)).fetchall())
    solicitudes = hechas = 0
    for i in range(0, len(pendientes), LOTE):
        if solicitudes >= max_solicitudes:
            return solicitudes, hechas, True
        lote = pendientes[i:i + LOTE]
        entrada = [{"id": r[0], "fecha_publicacion": (r[3] or "")[:10], "departamento_de_la_busqueda": r[4],
                    "titular": r[1], "resumen": r[2] or None} for r in lote]
        try:
            por_id = _pedir(con, entrada)
        except SinCuota as e:
            print(f"  Sin cuota: {e}")
            return solicitudes, hechas, True
        solicitudes += 1
        for r in lote:
            if r[0] not in por_id:
                continue  # el LLM la omitió: se reintenta en la próxima corrida
            c = limpiar(por_id[r[0]])
            texto = " ".join(x for x in (r[1], r[2], c["empresa"], c["operacion"]) if x)
            c["ubigeo"], c["precision"] = ubicar(c, texto, r[4]) if c["es_protesta"] else (None, None)
            c["tipo_conflicto"] = tipo_conflicto(c["actor"], c["reclamo"], c["sector"], c["adversario"], texto) \
                if c["es_protesta"] else None
            con.execute(f"INSERT OR REPLACE INTO codificacion VALUES (?, ?, {','.join('?' * len(COLUMNAS))})",
                        (r[0], VERSION, *[c[k] for k in COLUMNAS]))
            hechas += 1
        con.commit()
    return solicitudes, hechas, False
