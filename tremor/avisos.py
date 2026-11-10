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
import sys
from datetime import date, timedelta
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


SECTOR = r"transportistas urbanos|docente|maestr|profesor|m[eé]dic|enfermer|salud|judicial|estatal|universit|estudiant"


def eventos(web, z, alias, desde):
    """Protestas en la zona o la ruta, o que nombran a la empresa. Lee los eventos ya depurados de la página (web.json):
    una protesta contada una vez, sin las suspendidas, y sin avisar como corte de despachos el transporte urbano ni
    los gremios que paran sin bloquear (docentes, salud)."""
    for e in web["eventos"]:
        f, ub, actor, acc = e.get("fecha_evento") or e.get("fecha_anuncio") or "", str(e["ubigeo"]), e.get("actor") or "", e.get("accion") or ""
        pl = e.get("plazo") if isinstance(e.get("plazo"), str) and e["plazo"] >= date.today().isoformat() else None
        vieja = e["estado"] == "anunciada" and not pl and f < date.today().isoformat()  # anunciada y ya pasó sin noticia de que ocurriera
        if e.get("suspendido") or vieja or max(f, pl or "") < desde or e.get("leida") is False:  # sin leer la nota, no se avisa
            continue
        transporte = "ransportista" in actor and "urbano" not in actor.lower() and not e.get("urbano")
        sin_bloqueo = re.search(SECTOR, actor, re.I) and not re.search(r"bloque|toma", acc, re.I)
        nombra = re.search(alias, f"{e.get('empresa') or ''} {e.get('operacion') or ''}", re.I)
        en_zona = ub in z and not (sin_bloqueo and z[ub].startswith("en su ruta")) and (
            e.get("tipo_conflicto") not in (None, "otro") or re.search(LUCHA.replace("|marcha", ""), acc, re.I))
        if nombra or (ub == "00" and transporte) or en_zona:
            yield {"clave": f"evento:{e['id']}" + (f":plazo{pl}" if pl else ""), "estado": "plazo" if pl else "sin_fecha" if e.get("sin_fecha") else e["estado"], "fecha": pl or f,
                   "ubigeo": ub, "accion": acc or "Protesta", "unidad": z.get(ub), "medio": e.get("medio") or "", "enlace": e.get("enlace") or "",
                   "titular": e.get("titular") or "", "transporte": transporte, "punto": (e.get("puntos") or [""])[0]}


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
        png = tarjeta(f"Sube el riesgo de conflicto en {dis}", pct(r["p"]), [f"Nivel {n.lower()}", meses(r["ventana"]).capitalize()],
                      cerca(r["ubigeo"], [u for u, x in unidad.items() if x == r["unidad"]]), {r["ubigeo"]}, suyos, p=r["p"])
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
        fuente = f"[{e['medio']}]({e['enlace']})" if e["enlace"] else e["medio"]
        enlace = f"{APP}?e={quote(nombre)}" + (f"&d={e['ubigeo']}" if len(e["ubigeo"]) == 6 else "")
        texto = (f"🚧 *ALERTA DE PROTESTA · {e['accion'] or 'Protesta'}*\n"
                 f"_{e['titular'] or e['accion']}_\n\n"
                 f"📍 *Dónde:* {donde}\n"
                 f"🗓 *Cuándo:* {cuando}\n\n"
                 f"⚠️ *¿Qué puede pasar?*\n{efecto}" + (f"\nSegún la prensa: {e['punto']}" if e["punto"] else "") + "\n\n"
                 f"✅ *Qué hacer*\n{hacer}\n\n"
                 f"📰 *Fuente:* {fuente}\n"
                 f"🔗 *Conoce más aquí:* {enlace}")
        foco = set(tramos) if e["ubigeo"] == "00" and e["transporte"] else {u for u in [e["ubigeo"]] if len(u) == 6}
        propios = [u for u, x in unidad.items() if x == e["unidad"]]
        if len(e["ubigeo"]) == 4:  # provincia: se pinta entera
            foco = {u for u in vecinos if u.startswith(e["ubigeo"])}
        mapa = (suyos + list(tramos)) if e["ubigeo"] == "00" else cerca(e["ubigeo"], propios) if len(e["ubigeo"]) == 6 else [*foco, *prov]
        cifra, sub = ((dia(e["fecha"]), ["Fecha del anuncio", "Todavía sin fecha de protesta"]) if e["estado"] == "sin_fecha"
                      else (dia(e["fecha"]), [cuando.split(" para el")[0].split(" el ")[0], "Todo el país" if e["ubigeo"] == "00" else mayus(lugar(e["ubigeo"]))]))
        png = tarjeta(re.sub(r",? según .*$", "", e["titular"] or e["accion"]), cifra, sub, mapa, foco, suyos,
                      leyenda="Su ruta de salida" if e["ubigeo"] == "00" else "Lugar de la protesta") if mapa else None
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


def main(dias=3, reenviar=False, muestra=False):
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
        evs, rad, rie = nuevo(eventos(web, z, alias, desde)), nuevo(radio(con, alias, desde)), nuevo(riesgo(web, z))
        for clave, texto, png in piezas(nombre, evs, rad, rie, unidad, web["vecinos"], tramos):
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


if __name__ == "__main__":
    main(int(sys.argv[sys.argv.index("--dias") + 1]) if "--dias" in sys.argv else 3, "--reenviar" in sys.argv, "--muestra" in sys.argv)
