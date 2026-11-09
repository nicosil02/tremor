"""Avisos por Telegram para cada empresa cliente: protesta anunciada u ocurrida en la zona de sus unidades,
mención de la empresa en radio y subida del riesgo del modelo en su zona. Cada aviso se manda una sola vez
(tabla aviso_enviado). El envío es el de Base_legislativa (congreso_live/notify.py).

    python -m tremor.avisos            # sin TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID solo imprime (prueba)
    python -m tremor.avisos --dias 7   # mira más atrás (por defecto, 3 días)

ponytail: un solo chat para todas las empresas; con clientes reales, un chat por empresa (columna en EMPRESAS)."""
import json
import os
import re
import sys
from datetime import date, timedelta

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
}
LUCHA = r"\bparo\b|bloque|huelga|\btoma\b|protest|moviliza|marcha|plant[oó]n|enfrentamiento"
CADENA = json.load(open(RAIZ / "docs" / "cadena.json", encoding="utf-8"))
SUBE = 0.05  # puntos sobre lo habitual que hacen avisar una subida del riesgo


def zona(con, empresa, vecinos):
    """Distritos de las unidades de la empresa y sus vecinos, con el nombre de la unidad que los trae."""
    z = {}
    for u, ub in con.execute("SELECT unidad, ubigeo FROM operacion WHERE lower(empresa) LIKE ?", (f"%{empresa}%",)):
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
        if e.get("suspendido") or vieja or max(f, pl or "") < desde:
            continue
        transporte = "ransportista" in actor and "urbano" not in actor.lower() and not e.get("urbano")
        sin_bloqueo = re.search(SECTOR, actor, re.I) and not re.search(r"bloque|toma", acc, re.I)
        nombra = re.search(alias, f"{e.get('empresa') or ''} {e.get('operacion') or ''}", re.I)
        en_zona = ub in z and not (sin_bloqueo and z[ub].startswith("en su ruta")) and (
            e.get("tipo_conflicto") not in (None, "otro") or re.search(LUCHA.replace("|marcha", ""), acc, re.I))
        if nombra or (ub == "00" and transporte) or en_zona:
            yield {"clave": f"evento:{e['id']}" + (f":plazo{pl}" if pl else ""), "estado": "plazo" if pl else e["estado"], "fecha": pl or f,
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
                out.append(p)
    return out


def riesgo(web, z):
    """Zonas de la empresa cuyo riesgo está claramente sobre lo habitual en esta corrida del modelo."""
    for a in web["alerta"]:
        c = a.get("cambio_zona_ext")
        if a["ubigeo"] in z and a.get("operacion_extractiva") and c is not None and c >= SUBE:
            sube = "; ".join(empujan(a.get("razones_cambio_ext") or "")[:3])
            yield {"clave": f"riesgo:{web['mes_base']}:{a['ubigeo']}", "lugar": a["lugar"].split(" / ")[-1].title(),
                   "p": a["prob_zona_extractivo"], "normal": a["normal_zona_ext"], "sube": sube, "ventana": web["ventana"]}


def lugar(ub):
    return "lugar sin precisar" if ub in (None, "", "00") else NOMBRE.get(ub, ub).title().replace("Provincia De", "la provincia de")


def dia(f):
    return f"{int(f[8:10])} {MESES[int(f[5:7]) - 1]}" if f and len(f) >= 10 else "fecha sin precisar"


def mensaje(nombre, evs, rad, rie):
    pct = lambda x: f"{round(x * 100)}%"
    lineas = [f"*Tremor, avisos para {nombre}*"]
    for e in sorted(evs, key=lambda e: e["estado"] != "anunciada"):
        cuando = {"anunciada": "Anunciada para el", "plazo": "Vence un plazo, amenazan con nueva medida, el"}.get(e["estado"], "Ocurrió el")
        cerca = f", {e['unidad']}" if (e["unidad"] or "").startswith("en su ruta") else f", zona de {e['unidad']}" if e["unidad"] else ""
        fuente = f"[{e['medio']}]({e['enlace']})" if e["enlace"] else e["medio"]
        ruta = " Puede afectar sus despachos e insumos." if e["transporte"] else ""
        donde = f" Según la prensa: {e['punto']}" if e["punto"] else ""
        lineas.append(f"\n• *{e['titular'] or e['accion']}*\n{cuando} {dia(e['fecha'])} en {lugar(e['ubigeo'])}{cerca}.{ruta}{donde} {fuente}")
    for r in rad:
        lineas.append(f"\n• {r['medio']} lo mencionó el {dia(r['dia'])} a las {r['hora']}: «{r['texto']}»")
    for r in rie:
        lineas.append(f"\n• El riesgo de conflicto en la zona de {r['lugar']} está en {pct(r['p'])}, "
                      f"{round((r['p'] - r['normal']) * 100)} puntos sobre lo habitual ({r['ventana']})." + (f" Lo empuja: {r['sube']}." if r["sube"] else ""))
    return "\n".join(lineas)


def enviar(texto):
    """Telegram con Markdown; si un * o _ suelto rompe el formato, reintenta en texto plano. Sin claves, imprime."""
    token, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not (token and chat):
        print(texto, "\n")
        return False
    for modo in ("Markdown", None):
        r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage", timeout=20,
                          data={"chat_id": chat, "text": texto[:4096], "disable_web_page_preview": True, **({"parse_mode": modo} if modo else {})})
        if r.ok:
            return True
    print("Telegram rechazó el mensaje:", r.status_code)
    return False


def main(dias=3):
    con = conectar()
    con.execute("CREATE TABLE IF NOT EXISTS aviso_enviado (clave TEXT, empresa TEXT, enviado TEXT, PRIMARY KEY (clave, empresa))")
    web = json.load(open(DATOS / "exportes" / "web.json", encoding="utf-8"))
    desde = (date.today() - timedelta(days=dias)).isoformat()
    ya = set(con.execute("SELECT clave || '|' || empresa FROM aviso_enviado").fetchall())
    for nombre, (empresa, alias) in EMPRESAS.items():
        z = zona(con, empresa, web["vecinos"])
        for t in CADENA.get(nombre, {}).get("tramos", []):  # su ruta de salida (docs/cadena.json)
            for u in t["ubigeos"]:
                z.setdefault(u, f"en su ruta, tramo {t['nombre']}")
        nuevo = lambda xs: [x for x in xs if (f"{x['clave']}|{nombre}",) not in ya]
        evs, rad, rie = nuevo(eventos(web, z, alias, desde)), nuevo(radio(con, alias, desde)), nuevo(riesgo(web, z))
        if not (evs or rad or rie):
            continue
        if enviar(mensaje(nombre, evs, rad, rie)):
            con.executemany("INSERT OR IGNORE INTO aviso_enviado VALUES (?, ?, ?)", [(x["clave"], nombre, ahora()) for x in evs + rad + rie])
            con.commit()


if __name__ == "__main__":
    main(int(sys.argv[sys.argv.index("--dias") + 1]) if "--dias" in sys.argv else 3)
