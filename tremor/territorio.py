"""Perfil territorial del distrito (variables del lugar para el modelo).

MEF: presupuesto de cada municipalidad por año desde 2012 en la Consulta Amigable, total y del rubro 18 (canon,
sobrecanon, regalías, renta de aduanas y participaciones). La URL guarda la consulta y un GET devuelve la tabla,
sin sesión (método del MCP de Noelia León, github.com/NoeliaLRuiz/mcp-consulta-amigable).
`python -m tremor.territorio mef [--desde 2012]`
"""
import argparse
import html
import re
import sys
import time
from datetime import date

import requests

from tremor.db import ahora, conectar

MEF = "https://apps5.mineco.gob.pe/transparencia/Navegador/Navegar_7.aspx"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/130.0 Safari/537.36 (tremor)"}
ESQUEMA = """CREATE TABLE IF NOT EXISTS mef_municipal (
    ubigeo TEXT NOT NULL, anio INTEGER NOT NULL, municipalidad TEXT,
    pim_total INTEGER, devengado_total INTEGER, pim_canon INTEGER, devengado_canon INTEGER,
    consultado TEXT NOT NULL, PRIMARY KEY (ubigeo, anio))"""


def _texto(celda):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", celda))).strip()


def parsear_mef(pagina: str) -> dict:
    """Tabla por municipalidad → {ubigeo: (nombre, pim, devengado)}. La fila dice '010101-300001: MUNICIPALIDAD…'."""
    salida = {}
    for tr in re.findall(r'<tr[^>]*id="tr\d+".*?</tr>', pagina, re.S):
        c = [_texto(td) for td in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
        m = re.match(r"(\d{6})-\d+: (.*)", c[1])
        if m:
            n = lambda x: int(x.replace(",", "")) if x else 0
            salida[m[1]] = (m[2], n(c[3]), n(c[7]))  # columnas: PIA, PIM, certificación, compromiso, atención, devengado
    return salida


def _mef(ruta, anio):
    for espera in (0, 5, 20):
        time.sleep(espera)
        try:
            p = requests.get(f"{MEF}?_uhc=yes&0=&{ruta}&y={anio}&ap=ActProy&cpage=1&psize=5000", headers=UA, timeout=180).text
        except requests.RequestException:
            continue
        if f'selected="selected" value="{anio}"' in p:
            return parsear_mef(p)
    raise RuntimeError(f"Consulta Amigable sin respuesta para {anio}")


def mef(con, desde=2012):
    con.execute(ESQUEMA)
    for anio in range(desde, date.today().year + 1):
        total, canon = _mef("1=M&7=", anio), _mef("1=M&15=18&7=", anio)
        con.executemany("INSERT OR REPLACE INTO mef_municipal VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        [(u, anio, nom, pim, dev, *canon.get(u, ("", 0, 0))[1:], ahora()) for u, (nom, pim, dev) in total.items()])
        con.commit()
        print(f"  MEF {anio}: {len(total)} municipalidades, {sum(v[2] for v in canon.values()) / 1e9:.1f} mil millones de canon devengado")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(prog="python -m tremor.territorio")
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("mef"); m.add_argument("--desde", type=int, default=2012)
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    mef(conectar(), a.desde)
