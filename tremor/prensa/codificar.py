"""Codifica cada nota con las variables del manual de la EGPP + estado anunciada/ocurrida/suspendida (FR-009).

El LLM devuelve nombres; el ubigeo lo pone lugares.resolver (research R3). Lotes de 25 notas por solicitud.
ponytail: una codificación por nota (la protesta principal); separar varias protestas por nota si la validación lo pide.
"""
import json
import re
from datetime import date, timedelta
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
Tampoco lo que hace una autoridad o una empresa: que la municipalidad paralice, clausure o bloquee una obra tras el
reclamo de vecinos es un acto administrativo, no protesta. Un reclamo verbal o escrito sin acción colectiva tampoco.
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
            respaldo(con, pendientes[i:])
            return solicitudes, hechas, True
        lote = pendientes[i:i + LOTE]
        entrada = [{"id": r[0], "fecha_publicacion": (r[3] or "")[:10], "departamento_de_la_busqueda": r[4],
                    "titular": r[1], "resumen": r[2] or None} for r in lote]
        try:
            por_id = _pedir(con, entrada)
        except SinCuota as e:
            print(f"  Sin cuota: {e}")
            respaldo(con, pendientes[i:])
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


# --- Respaldo sin LLM: cuando se acaba el cupo, lo que le importa a un cliente minero no espera al día siguiente ---
MESES = "enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre".split()
ACCION = [(r"bloque", "Bloqueo de vías"), (r"huelga", "Huelga"), (r"\bparo\b|paraliz", "Paro"), (r"march|moviliz", "Marcha"),
          (r"planton", "Plantón"), (r"\btoma\b|tomaron", "Toma de local")]
ACTOR = [(r"carga pesada|transportistas de carga|transporte de carga|camioner", "Transportistas de carga"),
         (r"transporte (publico|urbano)|combis?\b|colectiver|mototaxi|buses|transportistas de lima|empresas de transporte", "Transportistas urbanos"),
         (r"comunidad(es)? campesina|comuneros", "Comunidades campesinas"), (r"comunidad(es)? nativa|indigena", "Comunidades nativas"),
         (r"agricultor|regantes", "Agricultores"), (r"ronder", "Rondas campesinas")]
ANUNCIA = re.compile(r"anunci|convoc|alist|amenaz|advierte|preparan")  # gana sobre lo demás
OCURRE = re.compile(r"estall|bloquean|bloquearon|acatan|acataron|protestaron|marcharon|choques|enfrentamient|se registr|continua|cumple|segundo dia|tercer dia")
PRONTO = re.compile(r"acatar|se sumar|realizar[aá]n|iniciar[aá]n|desde el|a partir del?|este (lunes|martes|miercoles|jueves|viernes|sabado|domingo)|ma[nñ]ana|suspender[aá]n|dejar[aá]n")
SUSPENDE = re.compile(r"(suspend|levant|desconvoc|posterg|cancel)\w*\s+(el |la |su |del )?(paro|huelga|bloqueo|medida|paralizaci)")


def por_reglas(titular, resumen, publicado):
    """Codificación de respaldo con reglas (versión "reglas"): acción, actor, anunciada u ocurrida, fecha dicha en la
    nota ("el 16 de noviembre") y lugar por nombre de provincia o distrito. Solo si es del Perú: nombra un lugar
    peruano o dice Perú; si no, None y espera al LLM. ponytail: reglas gruesas, el LLM la reemplaza al volver el cupo."""
    from tremor.web import _lugares, _norm
    tit = _norm(titular or "")
    t = f"{tit}. {_norm((resumen or '')[:300])}"  # el resumen a veces trae la página entera (menús, otras ciudades)
    accion = next((a for p, a in ACCION if re.search(p, t)), None)
    if not accion:
        return None
    idx = _lugares()
    def en(x):
        return sorted({u for k, us in idx.items() if re.search(rf"\b{re.escape(k)}\b", x) for u in us}, key=len, reverse=True)
    lugares = [] if re.search(r"paro nacional|a nivel nacional|todo el pais", tit) else en(tit) or en(t)
    if not lugares and "peru" not in t and not re.search(r"paro nacional|a nivel nacional|todo el pais", tit):
        return None  # puede ser de otro país (camioneros de Chile): espera al LLM
    actor = next((a for p, a in ACTOR if re.search(p, t)), None)
    if not actor and re.search(r"transportista|transporte|chofer", t):  # sin más pista: en Lima es urbano; fuera, carga
        actor = "Transportistas urbanos" if lugares and all(x[:2] in ("15", "07") for x in lugares) else "Transportistas de carga"
    actor = actor or "Pobladores"
    sector = next((s for s, xs in CODIGOS["sector_actor"].items() if actor in xs), None)
    m = re.search(rf"\b(\d{{1,2}})(?:(?:,| y| al| hasta el) \d{{1,2}})* de ({'|'.join(MESES)})\b", t)  # "del 16 al 18": el 16
    fecha = f"{(publicado or '2000')[:4]}-{MESES.index(m.group(2)) + 1:02d}-{int(m.group(1)):02d}" if m else None
    d = None if m else re.search(r"\b(?:los dias|el dia|este (?:lunes|martes|miercoles|jueves|viernes|sabado|domingo)) (\d{1,2})\b", t)
    if d and publicado:  # "los días 16, 17 y 18" sin mes: este mes, o el siguiente si el día ya pasó
        y, mes, hoy = int(publicado[:4]), int(publicado[5:7]), int(publicado[8:10])
        if int(d[1]) < hoy:
            y, mes = (y + 1, 1) if mes == 12 else (y, mes + 1)
        fecha = f"{y}-{mes:02d}-{int(d[1]):02d}"
    pub = (publicado or "")[:10]
    if fecha and pub and fecha < pub and (date.fromisoformat(pub) - date.fromisoformat(fecha)).days > 3:
        return None  # recuerda algo pasado o es una nota vieja reindexada: espera al LLM
    def estado_de(x):
        return ("suspendida" if SUSPENDE.search(x) else "anunciada" if ANUNCIA.search(x) or (fecha and fecha > pub)
                else "ocurrida" if OCURRE.search(x) else "anunciada" if PRONTO.search(x) else None)
    estado = estado_de(tit) or estado_de(t) or "ocurrida"
    if not fecha and estado == "ocurrida":
        fecha = (publicado or "")[:10] or None
    u = (lugares[0] if len(lugares) == 1 or all(x.startswith(lugares[-1][:4]) for x in lugares)
         else lugares[0][:2] if all(x[:2] == lugares[0][:2] for x in lugares) else None) if lugares else None
    return {"es_protesta": 1, "estado": estado, "fecha_evento": fecha, "region": None, "provincia": None, "distrito": None,
            "localidad": None, "ubigeo": u, "precision": None if not u else "distrito" if len(u) == 6 else "provincia",
            "sector": sector, "actor": actor, "accion": accion, "adversario": None, "empresa": None, "operacion": None,
            "reclamo": None, "sub_reclamo": None, "heridos": None, "muertos": None, "detenidos": None,
            "tipo_conflicto": tipo_conflicto(actor, None, sector, None, t)}


def respaldo(con, pendientes):
    """Las notas vivas que le importan a un cliente y quedaron sin LLM: se codifican por reglas."""
    from tremor.prensa.historia import CLIENTE
    n, hace = 0, (date.today() - timedelta(days=15)).isoformat()
    # una previa del LLM vale más que las reglas, salvo si era un anuncio sin fecha (para eso se leyó el cuerpo)
    previa = {i for (i,) in con.execute("""SELECT nota_id FROM codificacion WHERE version = 'previa'
                                          AND NOT (estado = 'anunciada' AND fecha_evento IS NULL)""")}
    for r in pendientes:
        if r[0] in previa or (r[3] or "")[:10] < hace or not CLIENTE.search(norm(r[1] or "")):  # el resumen trae menús
            continue
        c = por_reglas(r[1], r[2], r[3])
        if c and (c["ubigeo"] or c["estado"] == "anunciada"):  # sin lugar, solo el aviso previo; lo ocurrido espera al LLM
            con.execute(f"INSERT OR REPLACE INTO codificacion VALUES (?, 'reglas', {','.join('?' * len(COLUMNAS))})",
                        (r[0], *[c[k] for k in COLUMNAS])); n += 1
    con.commit()
    print(f"  Respaldo por reglas: {n} notas para clientes, hasta que vuelva el cupo")
    return n
