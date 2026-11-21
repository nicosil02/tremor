"""Emergencias viales del COE-MTC (reporte diario diurno, hoja 'Transportes').

Reemplaza a la API cerrada de SUTRAN: el MTC publica el mismo dato (vías interrumpidas/restringidas en la Red
Vial Nacional, con causa, vía, km, lugar y coordenadas) como XLSX oficial y abierto. Cada corrida baja el reporte
más reciente y acumula lo visto, como `tremor.sutran`. `python -m tremor.mtc`
"""
import re
import sys

import requests

from tremor.db import ahora, conectar
from tremor.lugares import resolver
from tremor.sutran import UA  # mismo bot identificado

LISTADO = "https://www.gob.pe/institucion/mtc/informes-publicaciones/2826745-reportes-diarios-diurnos"
RE_XLSX = re.compile(r"https://cdn\.www\.gob\.pe/[^\"']+?coe-mtc-(\d\d)-(\d\d)-(\d\d)[^\"']*?\.xlsx[^\"']*")
RE_VIA = re.compile(r"\bPE-[0-9A-Z]+", re.I)
RE_KM = re.compile(r"Km\s*[\d+]+(?:\s*-\s*Km\s*[\d+]+)?", re.I)
COLS = ["fecha_evento", "region", "provincia", "distrito", "ubigeo", "precision", "via", "km", "estado",
        "motivo", "submotivo", "metraje", "descripcion", "lat", "lng"]


def url_reciente(html: str) -> str:
    """De la página de listado, la URL del XLSX con la fecha DD-MM-YY más nueva."""
    urls = {(m[3], m[2], m[1]): m[0] for m in RE_XLSX.finditer(html)}  # clave (año, mes, día) → URL
    if not urls:
        raise RuntimeError("no se encontró ningún reporte XLSX en el listado del MTC")
    return urls[max(urls)]


def lugar(celda) -> tuple[str | None, str | None, str | None]:
    """'Áncash\\nPallasca / Santa Rosa' → (región, provincia, distrito)."""
    t = (celda or "").replace("\n", " ").strip()
    reg, _, resto = t.partition(" ")  # el depto es la primera palabra; el resto es 'Prov / Dist'
    if "/" in resto:
        prov, _, dist = resto.partition("/")
        return reg or None, prov.strip() or None, dist.strip() or None
    return reg or None, resto.strip() or None, None


def estado(s: str) -> str:
    s = (s or "").lower()
    return "interrumpido" if "interrump" in s else "restringido" if "restring" in s else "normal" if "normal" in s else ""


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def fila(r: tuple) -> dict | None:
    """Una fila de datos de la hoja 'Transportes' → dict, o None si no es un evento."""
    if r[0] is None or str(r[0]).strip().lower() in ("", "total", "n°", "nº"):
        return None
    oc = (r[7] or "").strip()
    if not oc:  # sin descripción de ocurrencia no es un evento (fila de resumen/pie)
        return None
    region, prov, dist = lugar(r[3])
    ubigeo, prec = resolver(region, prov, dist, None)
    via = RE_VIA.search(r[4] or "")
    km = RE_KM.search(r[4] or "")
    motivo = "humano" if oc.lower().startswith("acci") else "natural"
    sub = oc.split("\n", 1)[0].split(" - ", 1)[-1].strip() if " - " in oc.split("\n", 1)[0] else None
    f = r[2]
    return {"id": str(r[1]).strip(), "fecha_evento": f.date().isoformat() if hasattr(f, "date") else (f or None),
            "region": region, "provincia": prov, "distrito": dist, "ubigeo": ubigeo, "precision": prec,
            "via": via.group(0).upper() if via else None, "km": km.group(0) if km else None,
            "estado": estado(r[5]), "motivo": motivo, "submotivo": sub, "metraje": r[6],
            "descripcion": oc, "lat": num(r[11]), "lng": num(r[12])}


def recolectar(con) -> tuple[int, int]:
    import io

    import openpyxl
    html = requests.get(LISTADO, timeout=60, headers={"User-Agent": UA}).text
    url = url_reciente(html)
    xlsx = requests.get(url, timeout=120, headers={"User-Agent": UA}); xlsx.raise_for_status()
    wb = openpyxl.load_workbook(io.BytesIO(xlsx.content), read_only=True, data_only=True)
    rows = list(wb["Transportes"].iter_rows(values_only=True))[4:]  # fila 3 es el encabezado
    t, nuevas, vistas = ahora(), 0, 0
    for r in rows:
        f = fila(r)
        if not f:
            continue
        vistas += 1
        interr = int(f["estado"] == "interrumpido")
        cur = con.execute(f"UPDATE mtc_via SET {', '.join(c + ' = ?' for c in COLS)}, visto_ultimo = ?, "
                          "interrumpido_alguna_vez = max(interrumpido_alguna_vez, ?) WHERE id = ?",
                          (*(f[c] for c in COLS), t, interr, f["id"]))
        if not cur.rowcount:
            con.execute(f"INSERT INTO mtc_via (id, {', '.join(COLS)}, visto_primero, visto_ultimo, "
                        f"interrumpido_alguna_vez) VALUES ({', '.join('?' * (len(COLS) + 4))})",
                        (f["id"], *(f[c] for c in COLS), t, t, interr))
            nuevas += 1
    con.commit()
    return vistas, nuevas


CONTEXTO = ("Te doy un bloqueo de vía por manifestación en el Perú (reporte del COE-MTC) y notas de prensa numeradas "
            "de esos días. Usa las notas que probablemente hablan de esta protesta: misma ciudad o provincia, fechas "
            "cercanas y un motivo compatible (no hace falta que nombren la vía). Con ellas y el reporte, di en UNA "
            "oración formal de máximo 16 palabras quiénes protestan (por rol, nunca nombres de personas), por qué y "
            "contra quién. Si ninguna nota sirve, resume solo lo que dice el reporte. "
            'Responde JSON {"contexto": "<oración>", "notas": [<números de las notas usadas>]}.')


def contexto(con, pausa=1.0) -> int:
    """Para cada bloqueo por manifestación vigente (visto en los últimos 2 días), busca qué dicen los medios y
    resume quién protesta y por qué. Mismo cruce que antes tenía SUTRAN; escribe mtc_contexto (lo lee la página)."""
    import json
    import time
    from datetime import date, timedelta
    from urllib.parse import quote
    from tremor.lugares import norm
    from tremor.llm import chat_json, SinCuota, RespuestaInvalida
    from tremor.prensa.recolectar import GNEWS, UA as UA_GNEWS, PALABRAS, ACCION, parsear, _guardar
    con.execute("""CREATE TABLE IF NOT EXISTS mtc_contexto (id TEXT PRIMARY KEY, contexto TEXT, fuentes TEXT,
                   actualizado TEXT NOT NULL)""")
    vivas = con.execute("""SELECT id, descripcion, distrito, provincia, region, via, km, fecha_evento FROM mtc_via
                           WHERE motivo = 'humano' AND submotivo = 'Manifestación' AND visto_ultimo >= date('now', '-2 day')
                           AND id NOT IN (SELECT id FROM mtc_contexto WHERE contexto IS NOT NULL)""").fetchall()
    hechos = 0
    for id_, desc, dist, prov, reg, via, km, f in vivas:
        f0 = date.fromisoformat(f or date.today().isoformat())
        lugares = [x.title() for x in {dist, prov} if x]
        if not lugares:
            continue
        q = f'{PALABRAS} ({" OR ".join(f'"{x}"' for x in lugares)}) after:{f0 - timedelta(3)} before:{f0 + timedelta(4)}'
        try:
            r = requests.get(GNEWS.format(q=quote(q)), timeout=30, headers=UA_GNEWS); r.raise_for_status()
            _guardar(con, list(parsear(r.text)), f"mtc:{id_}", reg)
        except requests.RequestException as e:
            print(f"  {dist}: {e.__class__.__name__}")
        time.sleep(pausa)
        claves = [norm(x) for x in lugares]
        notas = [n for n in con.execute("""SELECT medio, titular, resumen, enlace FROM nota
                                           WHERE substr(publicado, 1, 10) BETWEEN ? AND ? ORDER BY publicado""",
                                        (str(f0 - timedelta(3)), str(f0 + timedelta(4))))
                 if any(k in norm(f"{n[1]} {n[2] or ''}") for k in claves)]
        notas = sorted(notas, key=lambda n: not ACCION.search(f"{n[1]} {n[2] or ''}"))[:12]
        if not notas:
            con.execute("INSERT OR REPLACE INTO mtc_contexto VALUES (?, NULL, '[]', datetime('now'))", (id_,))
            continue
        texto = f"MTC: {desc}. Vía {via} {km}, {dist}, {prov}, {reg}, {f}.\n\n" + "\n".join(
            f"[{i}] {m}: {t}. {(rr or '')[:300]}" for i, (m, t, rr, _) in enumerate(notas))
        try:
            out = chat_json(con, CONTEXTO, texto, "mtc-contexto-1")
        except SinCuota:
            break
        except RespuestaInvalida:
            continue
        usadas = [notas[i] for i in out.get("notas") or [] if isinstance(i, int) and 0 <= i < len(notas)]
        fuentes = [{"medio": m, "titular": t, "enlace": e} for m, t, _, e in usadas[:3]]
        con.execute("INSERT OR REPLACE INTO mtc_contexto VALUES (?, ?, ?, datetime('now'))",
                    (id_, out.get("contexto"), json.dumps(fuentes, ensure_ascii=False)))
        hechos += bool(out.get("contexto"))
    con.commit()
    return hechos


def demo():
    assert lugar("Áncash\nPallasca / Santa Rosa") == ("Áncash", "Pallasca", "Santa Rosa")
    assert lugar("Lima\nLima / Lima") == ("Lima", "Lima", "Lima")
    assert estado("TRÁNSITO INTERRUMPIDO") == "interrumpido" and estado("TRÁNSITO RESTRINGIDO") == "restringido"
    r = (141, "VIALES-006845", None, "Huánuco\nHuánuco / Pillco Marca",
         "Red Vial Nacional: PE-18A, Tramo: Ambo - Huánuco, Sector: X Km 205+200 - Km 229+080",
         "TRÁNSITO RESTRINGIDO", "-", "Acción humana - Manifestación\nDebido al alza de combustible...",
         None, None, None, "-9.97", "-76.24", None, None)
    f = fila(r)
    assert f["motivo"] == "humano" and f["submotivo"] == "Manifestación", f
    assert f["via"] == "PE-18A" and f["km"].startswith("Km 205") and f["lat"] == -9.97
    assert url_reciente('x "https://cdn.www.gob.pe/a/coe-mtc-18-11-26-manana.xlsx?v=1" '
                        'y "https://cdn.www.gob.pe/b/coe-mtc-20-11-26-manana.xlsx?v=1"').startswith("https://cdn.www.gob.pe/b/")
    print("demo OK")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if "--demo" in sys.argv:
        demo()
    else:
        con = conectar()
        vistas, nuevas = recolectar(con)
        prot = con.execute("SELECT count(*) FROM mtc_via WHERE motivo = 'humano' AND submotivo = 'Manifestación'").fetchone()[0]
        print(f"MTC: {vistas} emergencias viales vigentes, {nuevas} nuevas; {prot} por manifestación (acumuladas).")
        print(f"  contexto de prensa para {contexto(con)} bloqueos por manifestación vigentes.")
