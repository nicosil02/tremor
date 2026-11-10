"""Tiempo de viaje de cada tramo de la ruta del cliente (docs/cadena.json), cada hora, con el tráfico en vivo de TomTom.

Un bloqueo que nadie reporta igual se nota en la vía: el tramo tarda el doble, el ruteador manda un desvío largo o
marca un cierre. Se guarda la serie (`tiempo_viaje`) para calibrar contra las alertas de la SUTRAN antes de avisar con
ella. Sin `TOMTOM_API_KEY` no hace nada. `python -m tremor.tiempos`
ponytail: un solo proveedor; Google Routes (`TRAFFIC_AWARE`) se suma si TomTom resulta ciego en la sierra.
"""
import os
import statistics
import sys
import time
from datetime import datetime, timedelta

import requests

from tremor.avisos import CADENA
from tremor.db import ahora, conectar
from tremor.llm import _env

URL = ("https://api.tomtom.com/routing/1/calculateRoute/{}/json?traffic=true&travelMode=truck&computeTravelTimeFor=all"
       "&sectionType=traffic")


def medir(puntos, clave):
    """[[lat, lon], [lat, lon]] → (segundos con tráfico, sin tráfico, metros, ¿cierre?)."""
    for espera in (1, 3, 8, 0):  # 429: TomTom gratis limita las consultas por segundo; Las Bambas, al final, se quedaba sin medir
        r = requests.get(URL.format(":".join(f"{a},{b}" for a, b in puntos)), params={"key": clave}, timeout=60)
        if r.status_code != 429 or not espera:
            break
        time.sleep(espera)
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}")  # sin raise_for_status: su mensaje lleva la URL, y la URL la clave
    ruta = r.json()["routes"][0]
    s = ruta["summary"]
    cierre = any(x.get("simpleCategory") == "ROAD_CLOSURE" for x in ruta.get("sections", []))
    return s["travelTimeInSeconds"], s.get("noTrafficTravelTimeInSeconds") or s["travelTimeInSeconds"], s["lengthInMeters"], cierre


def senal(seg, sin, metros, metros_normal, cierre):
    """Qué dice la medición, o None si el tramo está normal. Umbrales por calibrar contra la SUTRAN."""
    if cierre:
        return "vía cerrada"
    if metros_normal and metros > 1.3 * metros_normal:
        return f"desvío de {(metros - metros_normal) / 1000:.0f} km"
    if sin and seg >= 1.5 * sin:
        return f"tarda {seg / sin:.1f} veces lo normal"
    return None


# Una vía lenta no siempre es una protesta: huaicos, lluvias, El Niño, accidentes, obras. La causa se busca en este orden.
MOTIVO = {"humano": "protesta", "fenomenos_naturales": "fenómeno natural", "accidentes": "accidente", "infraestructura": "obras"}


def _llueve(puntos):
    """mm de lluvia en las últimas 6 horas, el mayor de los puntos del tramo (Open-Meteo, sin clave; uso no comercial)."""
    try:
        r = requests.get("https://api.open-meteo.com/v1/forecast", timeout=30, params={
            "latitude": ",".join(str(a) for a, _ in puntos), "longitude": ",".join(str(b) for _, b in puntos),
            "hourly": "precipitation", "past_hours": 6, "forecast_hours": 0})
        js = r.json()
        return max(sum(x for x in p["hourly"]["precipitation"] if x) for p in (js if isinstance(js, list) else [js]))
    except (requests.RequestException, KeyError, TypeError, ValueError):
        return None


def causa(con, t, hoy, lluvia=None):
    """Por qué está lenta la vía: SUTRAN (trae el motivo), protesta en la prensa, lluvia fuerte o emergencia del mes."""
    us = t["ubigeos"]
    cerca = lambda u: bool(u) and any(u[:min(len(u), len(x), 4)] == x[:min(len(u), len(x), 4)] for x in us)
    deps = {x[:2] for x in us}
    for motivo, sub, titulo, u, via in con.execute(
            "SELECT motivo, submotivo, titulo, ubigeo, via FROM sutran_alerta WHERE visto_ultimo >= ? AND estado_via <> 'normal'",
            ((hoy - timedelta(hours=6)).isoformat(timespec="seconds"),)):
        if cerca(u) or (via and via == t.get("via") and (u or "")[:2] in deps):
            tipo = "El Niño" if "nino" in (sub or "") else MOTIVO.get(motivo, motivo)
            return f"{tipo} según SUTRAN: {titulo.capitalize()[:90]}"
    d = hoy.date()
    for u, accion in con.execute("SELECT ubigeo, accion FROM evento_prensa WHERE COALESCE(fecha_evento, fecha_anuncio) "
                                 "BETWEEN ? AND ?", ((d - timedelta(1)).isoformat(), d.isoformat())):
        if cerca(u):
            return f"protesta según la prensa ({(accion or 'medida de fuerza').lower()})"
    if lluvia and lluvia >= 10:
        return f"lluvia fuerte: {lluvia:.0f} mm en 6 horas"
    for u, tipo in con.execute("SELECT ubigeo, tipo FROM emergencia WHERE anio = ? AND mes = ?", (d.year, d.month)):
        if u in us:
            return f"emergencia por {str(tipo).lower()} este mes (INDECI)"
    return "causa sin confirmar"


def recolectar(con):
    _env()
    clave = os.environ.get("TOMTOM_API_KEY")
    if not clave:
        print("Tiempos de viaje: falta TOMTOM_API_KEY, no se mide.")
        return 0
    con.execute("CREATE TABLE IF NOT EXISTS tiempo_viaje (cliente TEXT, tramo TEXT, hora TEXT, segundos INTEGER, "
                "sin_trafico INTEGER, metros INTEGER, cierre INTEGER, senal TEXT, causa TEXT)")
    n, hora = 0, ahora()
    for cliente, c in CADENA.items():
        for t in c["tramos"]:
            if not t.get("puntos") or t.get("modo") != "Camión":  # TomTom mide carreteras: el tren no
                continue
            try:
                seg, sin, m, cierre = medir(t["puntos"], clave)
            except RuntimeError as e:
                print(f"  {cliente} / {t['nombre']}: {e}")
                continue
            except (requests.RequestException, KeyError, IndexError) as e:
                print(f"  {cliente} / {t['nombre']}: {type(e).__name__}")  # solo el tipo: el texto puede traer la URL con la clave
                continue
            prev = [x[0] for x in con.execute("SELECT metros FROM tiempo_viaje WHERE cliente = ? AND tramo = ? AND cierre = 0",
                                              (cliente, t["nombre"]))]
            s = senal(seg, sin, m, statistics.median(prev) if prev else None, cierre)
            try:
                c = causa(con, t, datetime.fromisoformat(hora), _llueve(t["puntos"])) if s else None
            except Exception as e:  # sqlite.OperationalError: una tabla que aún no existe en una base nueva
                c = f"causa sin confirmar ({type(e).__name__})"
            con.execute("INSERT INTO tiempo_viaje VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (cliente, t["nombre"], hora, seg, sin, m, int(cierre), s, c))
            n += 1
    con.commit()
    print(f"Tiempos de viaje: {n} tramos medidos.")
    return n


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    recolectar(conectar())
