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


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    con = conectar()
    vistas, nuevas = recolectar(con)
    protestas = con.execute("SELECT count(*) FROM sutran_alerta WHERE motivo = 'humano'").fetchone()[0]
    print(f"SUTRAN: {vistas} alertas vigentes, {nuevas} nuevas; {protestas} por causas humanas (protestas) acumuladas.")
