"""Avisos por Telegram para cada empresa cliente: protesta anunciada u ocurrida en la zona de sus unidades,
mención de la empresa en radio y subida del riesgo del modelo en su zona. Cada aviso se manda una sola vez
(tabla aviso_enviado). El envío es el de Base_legislativa (congreso_live/notify.py).

    python -m tremor.avisos            # sin TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID solo imprime (prueba)
    python -m tremor.avisos --dias 7   # mira más atrás (por defecto, 3 días)

El chat es del cliente: solo recibe los avisos de su empresa (TREMOR_CLIENTE, por defecto Bateas).
ponytail: un cliente por chat; con más clientes, un chat por empresa (columna en EMPRESAS)."""
import json
import os
import re
import sqlite3
import sys
from datetime import date, datetime, timedelta, timezone
from urllib.parse import quote

import csv

import requests

from tremor.db import DATOS, RAIZ, ahora, conectar

MESES = "ene feb mar abr may jun jul ago set oct nov dic".split()
# ubigeo de 2, 4 o 6 dígitos → departamento, provincia o distrito
NOMBRE = {}
for f in csv.DictReader(open(RAIZ / "tremor" / "ubigeo.csv", encoding="utf-8")):
    NOMBRE.update({f["ubigeo"][:2]: f["region"], f["ubigeo"][:4]: f"provincia de {f['provincia']}", f["ubigeo"]: f["distrito"]})

# nombre: (cómo figura en operacion.empresa, alias en notas y radio)
EMPRESAS = {
    "Bateas": ("minera bateas", r"minera bateas|\bbateas\b|caylloma|cailloma"),
    "Raura": ("minera raura", r"\braura\b"),
    "Poderosa": ("minera poderosa", r"minera poderosa|\bpataz\b"),
    "Las Bambas": ("minera las bambas", r"las bambas|\bmmg\b|ferrobamba|chalcobamba"),
    "Southern": ("southern peru", r"southern|toquepala|cuajone|t[ií]a mar[ií]a"),
    "Antamina": ("minera antamina", r"antamina"),
    "Yanacocha": ("minera yanacocha", r"yanacocha|\bconga\b"),
    "Buenaventura": ("buenaventura", r"buenaventura|uchucchacua|yumpag|tambomayo|orcopampa|julcani|san gabriel"),
}
LUCHA = r"\bparo\b|bloque|huelga|\btoma\b|protest|moviliza|marcha|plant[oó]n|enfrentamiento"
CADENA = json.load(open(RAIZ / "docs" / "cadena.json", encoding="utf-8"))
CLIENTE = os.environ.get("TREMOR_CLIENTE", "Bateas")
SUBE = 0.05  # puntos sobre lo habitual que hacen avisar una subida del riesgo


def zona(con, empresa, vecinos):
    """Distritos de las unidades de la empresa y sus vecinos, con el nombre de la unidad que los trae."""
    z = {}
    for u, ub in con.execute("SELECT unidad, ubigeo FROM operacion WHERE lower(empresa) LIKE ? AND unidad NOT LIKE 'Pasivos%'",
                             (f"%{empresa}%",)):  # un pasivo ambiental no despacha: no hace zona
        for d in [ub, *vecinos.get(ub, [])]:
            z.setdefault(d, u)
    return z


SECTOR = r"transportistas urbanos|docente|maestr|profesor|m[eé]dic|enfermer|salud|judicial|estatal|municipal|universit|estudiant"


def eventos(web, z, alias, desde):
    """Protestas en la zona o la ruta, o que nombran a la empresa. Lee los eventos ya depurados de la página (web.json):
    una protesta contada una vez, sin las suspendidas, y sin avisar como corte de despachos el transporte urbano ni
    los gremios que paran sin bloquear (docentes, salud)."""
    for e in web["eventos"]:
        f, ub, actor, acc = e.get("fecha_evento") or e.get("fecha_anuncio") or "", str(e["ubigeo"]), e.get("actor") or "", e.get("accion") or ""
        pl = e.get("plazo") if isinstance(e.get("plazo"), str) and e["plazo"] >= date.today().isoformat() else None
        vieja = e["estado"] == "anunciada" and not pl and f < hoy()  # anunciada y ya pasó sin noticia de que ocurriera
        pasada = e["estado"] == "ocurrida" and not pl and f < hoy()  # lo que ya pasó no le sirve al cliente: solo lo de hoy
        if e.get("suspendido") or vieja or pasada or max(f, pl or "") < desde or e.get("leida") is False:  # sin leer la nota, no se avisa
            continue
        transporte = "ransportista" in actor and "urbano" not in actor.lower() and not e.get("urbano")
        sin_bloqueo = re.search(SECTOR, actor, re.I) and not re.search(r"bloque|toma", acc, re.I)
        nombra = re.search(alias, f"{e.get('empresa') or ''} {e.get('operacion') or ''}", re.I)
        en_zona = ub in z and not (sin_bloqueo and z[ub].startswith("en su ruta")) and (
            e.get("tipo_conflicto") not in (None, "otro") or re.search(LUCHA.replace("|marcha", ""), acc, re.I))
        if nombra or (ub == "00" and transporte) or en_zona:
            # la clave es el contenido, no el id: los eventos se renumeran en cada corrida y el aviso se repetía
            yield {"clave": f"evento:{ub}:{acc}:{f}" + (f":plazo{pl}" if pl else ""), "actor": actor, "reclamo": e.get("reclamo") or "", "estado": "plazo" if pl else "sin_fecha" if e.get("sin_fecha") else e["estado"], "fecha": pl or f,
                   "ubigeo": ub, "accion": acc or "Protesta", "unidad": z.get(ub), "medio": e.get("medio") or "", "enlace": e.get("enlace") or "",
                   "titular": e.get("titular") or "", "transporte": transporte, "punto": (e.get("puntos") or [""])[0]}


def cambios(web, z, enviados):
    """Seguimiento de lo ya avisado: la protesta se suspendió o postergó, algunos lugares o gremios se retiran, o pasó la
    fecha sin noticia de que se hiciera. Solo de protestas que el cliente ya recibió (enviados: sus claves), un aviso
    por cambio."""
    for e in web["eventos"]:
        f, ub, acc = e.get("fecha_evento") or e.get("fecha_anuncio") or "", str(e["ubigeo"]), e.get("accion") or ""
        orig = f"evento:{ub}:{acc}:{f}"
        if orig not in enviados:
            continue
        que = f"{acc or 'Protesta'} {'en todo el país' if ub == '00' else 'en ' + lugar(ub)} del {dia(f)}"
        fuente = f"\n\n📰 *Fuente:* [{e.get('medio') or 'nota'}]({e['enlace']})" if e.get("enlace") else ""
        ret = [u for u in e.get("retiran") or [] if u in z]
        gre = e.get("gremios_retiran") or []
        if e.get("suspendido") or e.get("estado") == "suspendida":
            pos = e.get("postergado")
            yield ("cae:" + orig, f"{'⏸' if pos else '✅'} *PROTESTA {'POSTERGADA' if pos else 'SUSPENDIDA'}*\n_{e.get('titular') or que}_\n\n"
                   f"{que}: según la prensa, {'se postergó; todavía sin nueva fecha' if pos else 'se suspendió o se levantó'}.{fuente}", None)
        elif ret or gre:
            quienes = ", ".join([*gre, *(mayus(lugar(u)) for u in ret)])
            yield (f"retira:{orig}:{'-'.join(ret + gre)}", f"↩️ *SE RETIRAN DE LA PROTESTA*\n_{e.get('titular') or que}_\n\n"
                   f"{que}: anuncian que no se suman: {quienes}. El resto de la convocatoria sigue.{fuente}", None)
        # "sin noticia" solo de lo que podía frenar a la empresa: en su zona, o una medida que corta vías; no de una
        # marcha de un gremio que solo pasa por la ruta (municipales, docentes, salud): esa fue ruido para Bateas
        elif (e.get("estado") == "anunciada" and f and f < hoy() and f >= (date.today() - timedelta(days=3)).isoformat()
              and (ub in z or re.search(r"bloque|toma|paro", acc, re.I)) and not re.search(SECTOR, e.get("actor") or "", re.I)):
            yield ("nohubo:" + orig, f"❔ *SIN NOTICIA DE QUE SE REALIZARA*\n\n{que}: la fecha pasó y la prensa no informó que se "
                   f"hiciera. Pudo levantarse o no tener cobertura; conviene confirmarlo en la zona.", None)


def hoy():
    """La fecha en el Perú (GitHub corre en UTC: después de las 19:00 de Lima ya es mañana)."""
    return (datetime.now(timezone.utc) - timedelta(hours=5)).date().isoformat()


def sutran(con, z, desde):
    """Alertas de la SUTRAN en la zona o la ruta: toda protesta, y en la ruta toda vía interrumpida (huaico, accidente,
    El Niño): al de logística le sirve igual, pero el aviso dice la causa."""
    from tremor.tiempos import MOTIVO
    for codigo, motivo, sub, estado, titulo, desc, ub, fecha, lat, lng in con.execute(
            "SELECT codigo, motivo, submotivo, estado_via, titulo, descripcion, ubigeo, fecha_evento, lat, lng FROM sutran_alerta "
            "WHERE visto_ultimo >= ?", ((datetime.now() - timedelta(hours=6)).isoformat(timespec="seconds"),)):  # solo los cortes vigentes
        if (ub or "") not in z:
            continue
        protesta, ruta = motivo == "humano", z[ub].startswith("en su ruta")
        if not protesta and not (ruta and (estado or "").startswith("interrump")):
            continue
        causa = "El Niño" if "nino" in (sub or "") else MOTIVO.get(motivo, motivo or "causa sin precisar")
        yield {"clave": f"sutran:{codigo}", "estado": "ocurrida", "fecha": fecha or desde, "ubigeo": ub,
               "accion": "Bloqueo de vías" if protesta else f"Vía interrumpida por {causa}", "unidad": z[ub],
               "medio": "SUTRAN", "enlace": "https://alertasviales.sutran.gob.pe", "titular": (titulo or "").capitalize(),
               "transporte": False, "punto": (desc or "")[:200], "segun": "SUTRAN", "coord": (lat, lng) if lat and lng else None}


DURA = r"\b(\d+|veinticuatro|cuarenta y ocho|setenta y dos)\s+horas|\bindefinid\w*|\b(\d+|un|dos|tres|cuatro|cinco)\s+d[ií]as\b"


def de_radio(con, e):
    """Si la protesta salió solo de la radio: la hora de emisión y la frase donde se nombra la medida (sin ella el aviso no
    dice quién, cuándo ni cuánto dura)."""
    try:  # releída por el LLM (codificar.verificar_radio): solo las concretas, con quiénes, cuándo y duración dichos
        filas = con.execute("SELECT n.publicado, n.resumen, v.quienes, v.cuando, v.duracion FROM nota n JOIN radio_verificada v "
                            "ON v.nota_id = n.id AND v.concreta = 1 WHERE n.consulta = 'radio' AND n.medio = ? AND n.enlace = ? "
                            "ORDER BY n.publicado DESC", (e["medio"], e["enlace"])).fetchall()
    except sqlite3.OperationalError:  # base sin la tabla todavía
        filas = []
    for pub, txt, quienes, cuando, duracion in filas:
        m = re.search(LUCHA, txt or "", re.I)
        if m:
            a, b = max(0, m.start() - 110), m.end() + 140
            return pub, ("…" if a else "") + txt[a:b].strip() + ("…" if b < len(txt) else ""), {"quienes": quienes, "dicho_cuando": cuando, "duracion": duracion}
    return None


def lentas(con, nombre, ahora_=None):
    """Tramos de su ruta que TomTom mide lentos o cerrados en las últimas 3 horas, con la causa (tiempos.causa). Un
    aviso por tramo y día. Sin la tabla (sin clave de TomTom) no hay nada."""
    from datetime import datetime
    hm = lambda s: f"{s // 3600} h {s % 3600 // 60:02d} min" if s >= 3600 else f"{s // 60} min"
    desde = ((ahora_ or datetime.now()) - timedelta(hours=3)).isoformat(timespec="seconds")
    try:
        filas = con.execute("SELECT tramo, hora, segundos, sin_trafico, senal, causa FROM tiempo_viaje WHERE cliente = ? AND hora >= ? "
                            "AND senal IS NOT NULL ORDER BY hora DESC", (nombre, desde)).fetchall()
    except sqlite3.OperationalError:
        return []
    from tremor.tarjeta import tarjeta
    ruta = CADENA.get(nombre, {}).get("tramos", [])
    out, vistos = [], set()
    for tramo, hora, seg, sin, sen, causa in filas:
        if tramo in vistos:
            continue
        vistos.add(tramo)
        png = tarjeta(f"Ruta lenta: {re.sub(r', (\w+)$', r' (\1)', tramo)}", hm(seg), [f"Lo normal: {hm(sin)}", f"Medido a las {hora[11:16]}"], [], set(),
                      [u for t in ruta[:1] for u in t["ubigeos"][:1]], leyenda="Tramo lento", ruta=ruta, cortes=[tramo],
                      empresa=EMPRESAS[nombre][0]) if ruta and (DATOS / "distritos.geojson").exists() else None
        out.append((f"ruta:{tramo}:{hora[:10]}",
                    f"🐢 *RUTA LENTA · {re.sub(r', (\w+)$', r' (\1)', tramo)}*\n"
                    f"_Su ruta de salida tarda {hm(seg)}; lo normal es {hm(sin)}_\n\n"
                    f"🛣 *Qué pasa:* {sen[0].upper()}{sen[1:]} (medido a las {hora[11:16]})\n"
                    f"🔎 *Causa:* {causa or 'causa sin confirmar'}\n\n"
                    f"✅ *Qué hacer*\nConfirmar con sus transportistas antes de despachar y ver rutas u horarios alternos.\n\n"
                    f"🔗 *Conoce más aquí:* {APP}?e={quote(nombre)}", png))
    return out


def radio(con, alias, desde):
    """Fragmentos de radio que nombran a la empresa junto a una medida de lucha."""
    for id_, medio, pub, txt in con.execute("SELECT id, medio, publicado, resumen FROM nota WHERE consulta = 'radio' AND publicado >= ?", (desde,)):
        m = re.search(alias, txt or "", re.I)
        if m and re.search(LUCHA, txt, re.I):
            i = max(0, m.start() - 120)
            yield {"clave": f"radio:{id_}", "medio": medio, "hora": pub[11:16], "dia": pub[:10], "texto": " ".join(txt[i:i + 280].split())}


def empujan(razones):
    """De las razones del cambio, solo las que de verdad están sobre lo habitual: el modelo a veces anota como "sube"
    una señal que está por debajo (efecto de combinación), y eso al cliente lo confunde."""
    out = []
    for grupo in razones.split(" · "):
        if not grupo.startswith("sube: "):
            continue
        for p in grupo.removeprefix("sube: ").split("; "):
            p = p.removesuffix(", en la zona en los últimos 3 meses")
            m = re.search(r": (\d+) \(lo habitual, (\d+)\)", p)
            if (m and int(m[1]) > int(m[2])) or (not m and re.search(r"por encima|más protestas|duplicarse", p)):
                out.append(re.sub(r"^(.*?) (?:muy )?por encima de lo habitual en la zona$", r"más \1 que lo habitual", p).replace(" sin paro", ""))
    return out


def riesgo(web, z):
    """Zonas de la empresa cuyo riesgo está claramente sobre lo habitual en esta corrida del modelo."""
    for a in web["alerta"]:
        c = a.get("cambio_zona_ext")
        if a["ubigeo"] in z and a.get("operacion_extractiva") and c is not None and c >= SUBE:
            sube = "; ".join(empujan(a.get("razones_cambio_ext") or "")[:3])
            dep, prov, dis = (a["lugar"].title().split(" / ") + ["", ""])[:3]
            base = (a.get("razones_zona_extractivo") or "").split(" · ")[0].removeprefix("en la zona (distrito y vecinos): ")
            for x, y in ((" medidas de fuerza en 12 meses", " paros, bloqueos u otras medidas de fuerza en el último año"),
                         (" casos activos", " conflictos activos ante la Defensoría del Pueblo"), (" caso activo", " conflicto activo ante la Defensoría del Pueblo")):
                base = base.replace(x, y)
            yield {"clave": f"riesgo:{web['mes_base']}:{a['ubigeo']}", "ubigeo": a["ubigeo"], "lugar": f"{dis} ({prov}, {dep})", "unidad": z[a["ubigeo"]],
                   "propio": z[a["ubigeo"]] and a["ubigeo"] in {u for u, n in z.items() if not n.startswith("en su ruta")},
                   "p": a["prob_zona_extractivo"], "normal": a["normal_zona_ext"], "sube": sube, "base": base, "ventana": web["ventana"]}


def lugar(ub):
    return "lugar sin precisar" if ub in (None, "", "00") else NOMBRE.get(ub, ub).title().replace("Provincia De", "la provincia de")


def meses(v):
    """'2026-10 a 2026-12' → 'octubre a diciembre de 2026'."""
    largo = "enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre".split()
    a, b = v.split(" a ")
    return f"{largo[int(a[5:7]) - 1]} a {largo[int(b[5:7]) - 1]} de {b[:4]}"


def dia(f):
    return f"{int(f[8:10])} {MESES[int(f[5:7]) - 1]}" if f and len(f) >= 10 else "fecha sin precisar"


APP = "https://nicosil02.github.io/tremor/app.html"


def pct(x):
    return f"{round(x * 100)}%"


def mayus(s):
    return s[:1].upper() + s[1:]  # .capitalize() bajaría "Candarave" a "candarave"


def piezas(nombre, evs, rad, rie, unidad, vecinos, tramos):
    """Un aviso por pieza, como las alertas de monitoreo: tarjeta (imagen con mapa real) y un texto por subtítulos
    (zona, periodo, nivel, qué puede pasar, por qué, qué hacer, enlace). unidad: {ubigeo: unidad} de sus operaciones;
    tramos: ubigeos de su ruta. Devuelve [(clave, texto, png o None)]."""
    from tremor.tarjeta import nivel, tarjeta
    suyos = list(unidad)
    camino, empresa = CADENA.get(nombre, {}).get("tramos", []), EMPRESAS[nombre][0]
    salida = [u for t in camino[:1] for u in t["ubigeos"][:1]]  # donde arranca su ruta: la mina
    cortados = lambda foco: [t["nombre"] for t in camino if set(t["ubigeos"]) & foco]
    cerca = lambda u, propios=(): list(dict.fromkeys([u, *vecinos.get(u, []), *propios]))  # el distrito, sus vecinos y su unidad
    vinetas = lambda s: [f"• {x.strip()[0].upper()}{x.strip()[1:]}" for x in re.split(r";\s*", s or "") if x.strip()]
    out = []
    for r in rie:
        n = nivel(r["p"])[0]
        ruta = r["unidad"].startswith("en su ruta")
        donde = r["unidad"].replace("en su ruta, tramo", "en su ruta de salida, tramo") if ruta else f"en la zona de su unidad {r['unidad']}"
        dis = r["lugar"].split(" (")[0]
        porque = vinetas(r["base"]) + vinetas(r["sube"])
        texto = (f"🔺 *ALERTA DE RIESGO · {dis}*\n"
                 f"_Sube el riesgo de conflicto {donde}_\n\n"
                 f"📍 *Zona:* {r['lugar']}\n"
                 f"🗓 *Periodo:* {meses(r['ventana'])}\n"
                 f"📈 *Nivel:* {n}, {pct(r['p'])} (lo habitual en la zona es {pct(r['normal'])})\n\n"
                 f"⚠️ *¿Qué puede pasar?*\nUn paro, bloqueo o toma contra una operación minera en el distrito o sus vecinos. "
                 f"Todavía no hay una protesta anunciada contra la empresa.\n\n"
                 + (f"🔎 *¿Por qué sube?*\n" + "\n".join(porque) + "\n\n" if porque else "")
                 + "✅ *Qué hacer*\nReforzar el seguimiento de la zona y el diálogo con las comunidades vecinas.\n\n"
                 f"🔗 *Conoce más aquí:* {APP}?e={quote(nombre)}&d={r['ubigeo']}")
        mapa = cerca(r["ubigeo"], [u for u, x in unidad.items() if x == r["unidad"]])
        png = tarjeta(f"Sube el riesgo de conflicto en {dis}", pct(r["p"]), [f"Nivel {n.lower()}", meses(r["ventana"]).capitalize()],
                      mapa, {r["ubigeo"]}, [u for u in suyos if u in mapa], p=r["p"], ruta=camino,
                      cortes=cortados({r["ubigeo"]}), empresa=empresa)
        out.append((r["clave"], texto, png))
    for e in sorted(evs, key=lambda e: e["estado"] != "anunciada"):
        cuando = {"anunciada": f"Anunciada para el {dia(e['fecha'])}", "plazo": f"Plazo que vence el {dia(e['fecha'])}",
                  "sin_fecha": f"Anunciada el {dia(e['fecha'])}, todavía sin fecha"}.get(e["estado"], f"Ocurrió el {dia(e['fecha'])}")
        ruta = (e["unidad"] or "").startswith("en su ruta")
        prov = [x for x in unidad if len(e["ubigeo"]) == 4 and x.startswith(e["ubigeo"])]  # protesta ubicada solo en la provincia
        if prov and not e["unidad"]:
            e = {**e, "unidad": ", ".join(dict.fromkeys(unidad[x] for x in prov))}
        fuerza = bool(re.search(r"paro|huelga|bloque|toma|invasi|enfrent", (e["accion"] or "").lower()))
        donde = ("Todo el país" if e["ubigeo"] == "00" else mayus(lugar(e["ubigeo"]))
                 + (f", {e['unidad'].replace('en su ruta, tramo', 'en su ruta de salida, tramo')}" if ruta
                    else f", zona de su unidad {e['unidad']}" if e["unidad"] else ""))
        efecto = ("Puede frenar sus despachos de concentrado y la llegada de insumos." if e["transporte"]
                  else "Puede cortar el paso de sus camiones por ese tramo." if ruta else "Puede afectar el acceso y la operación de su unidad." if fuerza
                  else "Es un reclamo hacia la operación que puede escalar a un paro o bloqueo.")
        hacer = ("Adelantar o reprogramar despachos y coordinar con sus transportistas rutas y horarios." if e["transporte"] or ruta
                 else "Confirmar con relaciones comunitarias y seguridad, y seguir la convocatoria." if fuerza
                 else "Revisar el pedido con relaciones comunitarias y preparar una respuesta antes de que escale.")
        oido = e.get("dicho")  # solo la radio: sin nota escrita, se cita lo que se dijo al aire
        fuente = (f"{e['medio']}, en vivo el {dia(e['emitido'])} a las {e['emitido'][11:16]}" if oido
                  else f"[{e['medio']}]({e['enlace']})" if e["enlace"] else e["medio"])
        enlace = f"{APP}?e={quote(nombre)}" + (f"&d={e['ubigeo']}" if len(e["ubigeo"]) == 6 else "")
        corte = (e["accion"] or "").startswith("Vía interrumpida")  # huaico, accidente, El Niño (SUTRAN): no es protesta
        cab = (f"🛑 *VÍA INTERRUMPIDA · {e['accion'][21:].capitalize()}*" if corte else f"📻 *MENCIÓN EN RADIO · {e['accion']}*" if oido
               else f"🚧 *ALERTA DE PROTESTA · {e['accion'] or 'Protesta'}*")
        dura = e.get("duracion") or (m.group(0) if (m := re.search(DURA, f"{e['titular']} {oido or ''}", re.I)) else None)
        quien = ((f"👥 *Quiénes:* {e.get('quienes') or e['actor']}\n" if e.get("quienes") or e.get("actor") else "")
                 + (f"🗣 *Fecha que dijo la radio:* {e['dicho_cuando']}\n" if e.get("dicho_cuando") else "") + (f"📣 *Por qué:* reclamo {e['reclamo'].lower()}\n" if e.get("reclamo") else "")
                 + ("" if corte else f"⏱ *Duración:* {dura or 'no se informó'}\n"))
        texto = (f"{cab}\n"
                 f"_{e['titular'] or e['accion']}_\n\n"
                 f"📍 *Dónde:* {donde}\n"
                 f"🗓 *Cuándo:* {cuando}\n" + quien + "\n"
                 + (f"🎙 *Qué se dijo:* «{oido}»\n_Solo lo dijo la radio; no hay nota escrita que lo confirme._\n\n" if oido else "") +
                 f"⚠️ *¿Qué puede pasar?*\n{efecto}" + (f"\nSegún {e.get('segun', 'la prensa')}: {e['punto']}" if e["punto"] else "") + "\n\n"
                 f"✅ *Qué hacer*\n{hacer}\n\n"
                 f"📰 *Fuente:* {fuente}\n"
                 f"🔗 *Conoce más aquí:* {enlace}")
        nacional = e["ubigeo"] == "00" and e["transporte"]  # paro de transportistas: toda su ruta, sin distritos sueltos
        foco = {u for u in [e["ubigeo"]] if len(u) == 6}
        propios = [u for u, x in unidad.items() if x == e["unidad"]]
        if len(e["ubigeo"]) == 4:  # provincia: se pinta entera
            foco = {u for u in vecinos if u.startswith(e["ubigeo"])}
        mapa = (list(tramos) or suyos) if e["ubigeo"] == "00" else cerca(e["ubigeo"], propios) if len(e["ubigeo"]) == 6 else [*foco, *prov]
        cortes = [t["nombre"] for t in camino] if nacional else cortados(foco)
        cifra, sub = ((dia(e["fecha"]), ["Fecha del anuncio", "Todavía sin fecha de protesta"]) if e["estado"] == "sin_fecha"
                      else (dia(e["fecha"]), [cuando.split(" para el")[0].split(" el ")[0], "Todo el país" if e["ubigeo"] == "00" else mayus(lugar(e["ubigeo"]))]))
        png = tarjeta(re.sub(r",? según .*$", "", e["titular"] or e["accion"]), cifra, sub, [] if nacional and camino else mapa, foco,
                      [u for u in suyos if u in mapa or (cortes and u in salida)],
                      leyenda="Su ruta de salida" if e["ubigeo"] == "00" else "Lugar del corte" if corte else "Lugar de la protesta",
                      ruta=camino, cortes=cortes, empresa=empresa, punto=e.get("coord")) if mapa else None
        out.append((e["clave"], texto, png))
    for r in rad:
        out.append((r["clave"], f"📻 *MENCIÓN EN RADIO · {r['medio']}*\n\n🗓 *Cuándo:* {dia(r['dia'])}, {r['hora']}\n"
                                f"🗣 *Qué dijo:* «{r['texto']}»", None))
    return out


def enviar(texto, png=None):
    """Telegram con Markdown: la imagen con el texto al pie (si pasa de 1024 caracteres, la imagen y luego el texto);
    si un * o _ suelto rompe el formato, reintenta en texto plano. Sin claves, imprime y guarda la imagen."""
    token, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not (token and chat):
        print(texto, "\n")
        if png:
            (DATOS / "exportes" / f"aviso_{abs(hash(texto)) % 10**6}.png").write_bytes(png)
        return False
    api = f"https://api.telegram.org/bot{token}"
    for modo in ("Markdown", None):
        extra = {"parse_mode": modo} if modo else {}
        if png and len(texto) <= 1024:
            r = requests.post(f"{api}/sendPhoto", timeout=60, files={"photo": ("aviso.png", png, "image/png")},
                              data={"chat_id": chat, "caption": texto, **extra})
        else:
            if png:
                requests.post(f"{api}/sendPhoto", timeout=60, files={"photo": ("aviso.png", png, "image/png")}, data={"chat_id": chat})
                png = None  # si el texto falla en Markdown, el reintento no repite la imagen
            r = requests.post(f"{api}/sendMessage", timeout=20,
                              data={"chat_id": chat, "text": texto[:4096], "disable_web_page_preview": True, **extra})
        if r.ok:
            return True
    print("Telegram rechazó el mensaje:", r.status_code)
    return False


def main(dias=7, reenviar=False, muestra=False):  # 7: GitHub a veces corre el workflow pocas veces al día
    """muestra: las piezas de las 7 empresas en datos/exportes/muestra/ (imagen y texto), sin enviar nada; para revisarlas
    a ojo antes de cambiar el formato."""
    con = conectar()
    con.execute("CREATE TABLE IF NOT EXISTS aviso_enviado (clave TEXT, empresa TEXT, enviado TEXT, PRIMARY KEY (clave, empresa))")
    web = json.load(open(DATOS / "exportes" / "web.json", encoding="utf-8"))
    desde = (date.today() - timedelta(days=dias)).isoformat()
    ya = set() if reenviar or muestra else set(con.execute("SELECT clave || '|' || empresa FROM aviso_enviado").fetchall())  # --reenviar: prueba
    for nombre, (empresa, alias) in EMPRESAS.items():
        if nombre != CLIENTE and not muestra:
            continue
        z = zona(con, empresa, web["vecinos"])
        unidad = dict(con.execute("SELECT ubigeo, unidad FROM operacion WHERE lower(empresa) LIKE ?", (f"%{empresa}%",)).fetchall())
        tramos = [u for t in CADENA.get(nombre, {}).get("tramos", []) for u in t["ubigeos"]]
        for t in CADENA.get(nombre, {}).get("tramos", []):  # su ruta de salida (docs/cadena.json)
            for u in t["ubigeos"]:
                z.setdefault(u, "en su ruta, tramo " + re.sub(r", (\w+)$", r" (\1)", t["nombre"]))  # "Puerto de Matarani (zinc)"
        nuevo = lambda xs: [x for x in xs if (f"{x['clave']}|{nombre}",) not in ya]
        evs, rad, rie = nuevo([*eventos(web, z, alias, desde), *sutran(con, z, desde)]), nuevo(radio(con, alias, desde)), nuevo(riesgo(web, z))
        for e in evs:
            if r := de_radio(con, e):
                e["emitido"], e["dicho"], extra = r
                e.update({k: v for k, v in extra.items() if v})
        enviados = {c for (c,) in con.execute("SELECT clave FROM aviso_enviado WHERE empresa = ?", (nombre,))}
        ruta = [x for x in [*lentas(con, nombre), *cambios(web, z, enviados)] if (f"{x[0]}|{nombre}",) not in ya]
        for clave, texto, png in [*piezas(nombre, evs, rad, rie, unidad, web["vecinos"], tramos), *ruta]:
            if muestra:
                d = DATOS / "exportes" / "muestra"; d.mkdir(parents=True, exist_ok=True)
                base = f"{nombre}_{clave}".replace(":", "_").replace(" ", "_")
                (d / f"{base}.txt").write_text(texto, encoding="utf-8")
                if png:
                    (d / f"{base}.png").write_bytes(png)
                continue
            if enviar(texto, png):
                con.execute("INSERT OR IGNORE INTO aviso_enviado VALUES (?, ?, ?)", (clave, nombre, ahora()))
                con.commit()
    # en CSV para que la corrida siempre publique la base cuando se avisó algo (si no, la siguiente reenvía lo mismo)
    with open(DATOS / "exportes" / "aviso_enviado.csv", "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows([("clave", "empresa", "enviado"), *con.execute("SELECT * FROM aviso_enviado ORDER BY enviado")])


if __name__ == "__main__":
    main(int(sys.argv[sys.argv.index("--dias") + 1]) if "--dias" in sys.argv else 7, "--reenviar" in sys.argv, "--muestra" in sys.argv)
