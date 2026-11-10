"""Tiempo de viaje de cada tramo de la ruta del cliente (docs/cadena.json), cada hora, con el tráfico en vivo de TomTom.

Un bloqueo que nadie reporta igual se nota en la vía: el tramo tarda el doble, el ruteador manda un desvío largo o
marca un cierre. Se guarda la serie (`tiempo_viaje`) para calibrar contra las alertas de la SUTRAN antes de avisar con
ella. Sin `TOMTOM_API_KEY` no hace nada. `python -m tremor.tiempos`
ponytail: un solo proveedor; Google Routes (`TRAFFIC_AWARE`) se suma si TomTom resulta ciego en la sierra.
"""
import os
import statistics
import sys

import requests

from tremor.avisos import CADENA
from tremor.db import ahora, conectar
from tremor.llm import _env

URL = ("https://api.tomtom.com/routing/1/calculateRoute/{}/json?traffic=true&travelMode=truck&computeTravelTimeFor=all"
       "&sectionType=traffic")


def medir(puntos, clave):
    """[[lat, lon], [lat, lon]] → (segundos con tráfico, sin tráfico, metros, ¿cierre?)."""
    r = requests.get(URL.format(":".join(f"{a},{b}" for a, b in puntos)), params={"key": clave}, timeout=60)
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}")  # sin raise_for_status: su mensaje lleva la URL, y la URL la clave
    ruta = r.json()["routes"][0]
    s = ruta["summary"]
    cierre = any(x.get("simpleCategory") == "ROAD_CLOSURE" for x in ruta.get("sections", []))
    return s["travelTimeInSeconds"], s.get("noTrafficTravelTimeInSeconds") or s["travelTimeInSeconds"], s["lengthInMeters"], cierre


def senal(seg, sin, metros, metros_normal, cierre):
    """Qué dice la medición, o None si el tramo está normal. Umbrales por calibrar contra la SUTRAN."""
    if cierre:
        return "el ruteador marca la vía cerrada"
    if metros_normal and metros > 1.3 * metros_normal:
        return f"el ruteador desvía por {(metros - metros_normal) / 1000:.0f} km más"
    if sin and seg >= 1.5 * sin:
        return f"tarda {seg / sin:.1f} veces lo normal"
    return None


def recolectar(con):
    _env()
    clave = os.environ.get("TOMTOM_API_KEY")
    if not clave:
        print("Tiempos de viaje: falta TOMTOM_API_KEY, no se mide.")
        return 0
    con.execute("CREATE TABLE IF NOT EXISTS tiempo_viaje (cliente TEXT, tramo TEXT, hora TEXT, segundos INTEGER, "
                "sin_trafico INTEGER, metros INTEGER, cierre INTEGER, senal TEXT)")
    n, hora = 0, ahora()
    for cliente, c in CADENA.items():
        for t in c["tramos"]:
            if not t.get("puntos"):
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
            con.execute("INSERT INTO tiempo_viaje VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (cliente, t["nombre"], hora, seg, sin, m, int(cierre),
                         senal(seg, sin, m, statistics.median(prev) if prev else None, cierre)))
            n += 1
    con.commit()
    print(f"Tiempos de viaje: {n} tramos medidos.")
    return n


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    recolectar(conectar())
