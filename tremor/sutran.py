"""Alertas viales de la SUTRAN (mapa alertasviales.sutran.gob.pe), incluidas las protestas que bloquean vías.

La API pública (`/public/alerts`) devuelve solo las alertas vigentes, así que cada corrida guarda lo que ve y
actualiza su estado: la historia se arma acumulando. `python -m tremor.sutran`
"""
import sys

import requests

from tremor.db import ahora, conectar
from tremor.lugares import resolver

URL = "https://api.sigea.sutran.gob.pe/public/alerts"
COLS = ["codigo", "motivo", "submotivo", "estado_via", "titulo", "descripcion", "situacion", "lat", "lng", "region",
        "provincia", "distrito", "ubigeo", "precision", "via", "km", "fecha_evento", "vigente_desde", "vigente_hasta",
        "fuente"]


def iso(f):
    """'04/11/2026' → '2026-11-04'."""
    d, m, a = (f or "//").split("/")[:3]
    return f"{a}-{m}-{d}" if a else None


def fila(a: dict) -> dict:
    ubigeo, precision = resolver(a.get("region"), a.get("provincia"), a.get("distrito"), None)
    return {"codigo": a.get("codigo"), "motivo": a.get("motivo"), "submotivo": a.get("submotivo"),
            "estado_via": a.get("estadoVia"), "titulo": a.get("titulo"), "descripcion": a.get("descripcion"),
            "situacion": a.get("situacionActual"), "lat": a.get("lat"), "lng": a.get("lng"), "region": a.get("region"),
            "provincia": a.get("provincia"), "distrito": a.get("distrito"), "ubigeo": ubigeo, "precision": precision,
            "via": a.get("viaCodigo"), "km": a.get("km"), "fecha_evento": iso(a.get("fechaEvento")),
            "vigente_desde": iso(a.get("vigenteDesde")), "vigente_hasta": iso(a.get("vigenteHasta")),
            "fuente": a.get("fuente")}


def recolectar(con) -> tuple[int, int]:
    r = requests.get(URL, timeout=60, headers={"User-Agent": "Mozilla/5.0 (tremor)"}); r.raise_for_status()
    alertas, t, nuevas = r.json()["data"], ahora(), 0
    for a in alertas:
        f = fila(a)
        cur = con.execute(f"UPDATE sutran_alerta SET {', '.join(c + ' = ?' for c in COLS)}, visto_ultimo = ?, "
                          "interrumpido_alguna_vez = max(interrumpido_alguna_vez, ?) WHERE id = ?",
                          (*f.values(), t, int(f["estado_via"] == "interrumpido"), a["id"]))
        if not cur.rowcount:
            con.execute(f"INSERT INTO sutran_alerta (id, {', '.join(COLS)}, visto_primero, visto_ultimo, "
                        f"interrumpido_alguna_vez) VALUES ({', '.join('?' * (len(COLS) + 4))})",
                        (a["id"], *f.values(), t, t, int(f["estado_via"] == "interrumpido")))
            nuevas += 1
    con.commit()
    return len(alertas), nuevas


CONTEXTO = ("Te doy una alerta de la SUTRAN sobre una vía bloqueada por una protesta en el Perú y notas de prensa "
            "numeradas de esos días. Usa las notas que probablemente hablan de esta protesta: misma ciudad o provincia, "
            "fechas cercanas y un motivo compatible con la alerta (no hace falta que nombren la vía). Con ellas y la "
            "alerta, di en UNA oración formal de máximo 16 palabras quiénes protestan (por rol, nunca nombres de "
            "personas), por qué y contra quién. Si ninguna nota sirve, resume solo lo que dice la alerta. "
            'Responde JSON {"contexto": "<oración>", "notas": [<números de las notas usadas>]}.')


def contexto(con, pausa=1.0) -> int:
    """Para cada bloqueo vigente, busca qué dicen los medios (Google News del lugar en esos días y las notas ya
    guardadas: feeds regionales y radio) y resume quién protesta y por qué, aunque no sea contra una operación."""
    import json
    import time
    from datetime import date, timedelta
    from urllib.parse import quote
    from tremor.llm import chat_json, SinCuota, RespuestaInvalida
    from tremor.prensa.recolectar import GNEWS, UA, PALABRAS, parsear, _guardar
    con.execute("""CREATE TABLE IF NOT EXISTS sutran_contexto (id TEXT PRIMARY KEY, contexto TEXT, fuentes TEXT,
                   actualizado TEXT NOT NULL)""")
    vivas = con.execute("""SELECT id, titulo, descripcion, distrito, provincia, region, via, km, fecha_evento
                           FROM sutran_alerta WHERE motivo = 'humano' AND (vigente_hasta IS NULL OR vigente_hasta >= date('now'))
                           AND id NOT IN (SELECT id FROM sutran_contexto WHERE contexto IS NOT NULL)""").fetchall()
    hechos = 0
    for id_, tit, desc, dist, prov, reg, via, km, f in vivas:
        f0 = date.fromisoformat(f or date.today().isoformat())
        lugares = [x.title() for x in {dist, prov} if x]
        q = f'{PALABRAS} ({" OR ".join(f'"{x}"' for x in lugares)}) after:{f0 - timedelta(3)} before:{f0 + timedelta(4)}'
        try:
            r = requests.get(GNEWS.format(q=quote(q)), timeout=30, headers=UA); r.raise_for_status()
            _guardar(con, list(parsear(r.text)), f"sutran:{id_}", reg)
        except requests.RequestException as e:
            print(f"  {dist}: {e.__class__.__name__}")
        time.sleep(pausa)
        # las notas del lugar en esos días, también las de feeds y radio guardadas antes
        from tremor.lugares import norm
        claves = [norm(x) for x in lugares]
        notas = [n for n in con.execute("""SELECT medio, titular, resumen, enlace FROM nota
                                           WHERE substr(publicado, 1, 10) BETWEEN ? AND ? ORDER BY publicado""",
                                        (str(f0 - timedelta(3)), str(f0 + timedelta(4))))
                 if any(k in norm(f"{n[1]} {n[2] or ''}") for k in claves)]
        from tremor.prensa.recolectar import ACCION  # primero las que hablan de una protesta
        notas = sorted(notas, key=lambda n: not ACCION.search(f"{n[1]} {n[2] or ''}"))[:12]
        if not notas:
            con.execute("INSERT OR REPLACE INTO sutran_contexto VALUES (?, NULL, '[]', datetime('now'))", (id_,))
            continue
        texto = f"SUTRAN: {tit}. {desc}. Vía {via} {km}, {dist}, {prov}, {reg}, {f}.\n\n" + "\n".join(
            f"[{i}] {m}: {t}. {(r or '')[:300]}" for i, (m, t, r, _) in enumerate(notas))
        try:
            out = chat_json(con, CONTEXTO, texto, "sutran-contexto-3")
        except SinCuota:
            break
        except RespuestaInvalida:
            continue
        usadas = [notas[i] for i in out.get("notas") or [] if isinstance(i, int) and 0 <= i < len(notas)]
        fuentes = [{"medio": m, "titular": t, "enlace": e} for m, t, _, e in usadas[:3]]
        con.execute("INSERT OR REPLACE INTO sutran_contexto VALUES (?, ?, ?, datetime('now'))",
                    (id_, out.get("contexto"), json.dumps(fuentes, ensure_ascii=False)))
        hechos += bool(out.get("contexto"))
    con.commit()
    return hechos


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    con = conectar()
    vistas, nuevas = recolectar(con)
    protestas = con.execute("SELECT count(*) FROM sutran_alerta WHERE motivo = 'humano'").fetchone()[0]
    print(f"SUTRAN: {vistas} alertas vigentes, {nuevas} nuevas; {protestas} por causas humanas (protestas) acumuladas.")
    print(f"  contexto de prensa para {contexto(con)} bloqueos vigentes.")
