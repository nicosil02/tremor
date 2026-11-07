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


# Dimensiones de la Consulta Amigable: número que va en la URL (tomado del MCP de Noelia León).
DIMENSIONES = {"nivel": "1", "sector": "2", "pliego": "3", "ejecutora": "4", "municipalidad": "7", "funcion": "8",
               "fuente": "14", "rubro": "15", "departamento": "21", "mes": "23", "generica": "24",
               "categoria_presupuestal": "30", "producto_proyecto": "31", "division_funcional": "33"}


def filas_mef(pagina: str) -> list[dict]:
    """Cualquier tabla de la Consulta Amigable → filas con código (para filtrar), nombre, PIA, PIM, devengado y avance %."""
    n = lambda x: int(x.replace(",", "")) if x else 0
    filas = []
    for tr in re.findall(r'<tr[^>]*id="tr\d+".*?</tr>', pagina, re.S):
        c = [_texto(td) for td in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
        if len(c) > 7:  # columnas: -, nombre, PIA, PIM, certificación, compromiso, atención, devengado, girado, avance
            codigo = re.search(r'name="grp1" value="([^"/]*)', tr)
            filas.append({"codigo": codigo[1].strip() if codigo else None, "nombre": c[1], "pia": n(c[2]), "pim": n(c[3]), "devengado": n(c[7]),
                          "avance_pct": float(c[9]) if len(c) > 9 and c[9] else None})
    return filas


def por_municipalidad(filas: list[dict]) -> dict:
    """Filas por municipalidad → {ubigeo: (nombre, pim, devengado)}. La fila dice '010101-300001: MUNICIPALIDAD…'."""
    salida = {}
    for f in filas:
        if m := re.match(r"(\d{6})-\d+: (.*)", f["nombre"]):
            salida[m[1]] = (m[2], f["pim"], f["devengado"])
    return salida


def consulta(desglose: str, filtros: dict | None, anio: int) -> tuple[str, list[dict]]:
    """Consulta Amigable libre: desglose y filtros por nombre de dimensión. Devuelve (url, filas)."""
    ruta = "".join(f"{DIMENSIONES[k]}={v}&" for k, v in (filtros or {}).items()) + f"{DIMENSIONES[desglose]}="
    url = f"{MEF}?_uhc=yes&0=&{ruta}&y={anio}&ap=ActProy"
    for espera in (0, 5, 20):
        time.sleep(espera)
        try:
            p = requests.get(url + "&cpage=1&psize=5000", headers=UA, timeout=180).text
        except requests.RequestException:
            continue
        if f'selected="selected" value="{anio}"' in p:
            return url, filas_mef(p)
    raise RuntimeError(f"Consulta Amigable sin respuesta: {url}")


def mef(con, desde=2012):
    con.execute(ESQUEMA)
    for anio in range(desde, date.today().year + 1):
        total = por_municipalidad(consulta("municipalidad", {"nivel": "M"}, anio)[1])
        canon = por_municipalidad(consulta("municipalidad", {"nivel": "M", "rubro": "18"}, anio)[1])
        con.executemany("INSERT OR REPLACE INTO mef_municipal VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        [(u, anio, nom, pim, dev, *canon.get(u, ("", 0, 0))[1:], ahora()) for u, (nom, pim, dev) in total.items()])
        con.commit()
        print(f"  MEF {anio}: {len(total)} municipalidades, {sum(v[2] for v in canon.values()) / 1e9:.1f} mil millones de canon devengado")


# --- BCRP: precios de los metales y producción minera mensual por departamento -------------------------------
# Método del MCP del BCRP del autor (agente-socioeconomico-peru/tarea_4/mcp/server.py), llamado directo.
BCRP = "https://estadisticas.bcrp.gob.pe/estadisticas/series"
PRECIOS = {"PN01652XM": "Cobre - LME (¢US$ por libras)", "PN01654XM": "Oro - LME (US$ por onzas troy)",
           "PN01660XM": "Petróleo - WTI (US$ por barriles)"}
MESES = {"ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6, "jul": 7, "ago": 8, "set": 9, "sep": 9,
         "oct": 10, "nov": 11, "dic": 12}


def periodo_bcrp(nombre: str) -> str:
    """'Ene.2004' → '2004-01'."""
    mes, anio = nombre.split(".")
    return f"{anio}-{MESES[mes[:3].lower()]:02d}"


def series_mineras() -> dict:
    """Series mensuales del grupo 'Producción de productos mineros según departamentos', del catálogo oficial."""
    texto = requests.get(f"{BCRP}/metadata", headers=UA, timeout=120).content.decode("latin-1")
    filas = [l.split(";") for l in texto.splitlines()[1:]]
    return {f[0]: f[3] for f in filas if len(f) > 10 and "mineros seg" in f[2] and f[10] == "Mensual"}


def bcrp(con, desde="2004-1"):
    con.execute("""CREATE TABLE IF NOT EXISTS bcrp_mensual (serie TEXT NOT NULL, nombre TEXT, periodo TEXT NOT NULL,
                   valor REAL, fuente TEXT, consultado TEXT NOT NULL, PRIMARY KEY (serie, periodo))""")
    series = PRECIOS | series_mineras()
    for codigo, nombre in series.items():
        url = f"{BCRP}/api/{codigo}/json/{desde}/{date.today().year}-12"
        for espera in (0, 3, 10):  # la API responde HTML cuando se le pide muy rápido
            time.sleep(espera)
            try:
                periodos = requests.get(url, headers=UA, timeout=60).json()["periods"]
                break
            except (requests.RequestException, ValueError, KeyError):
                periodos = None
        if periodos is None:
            print(f"  BCRP sin respuesta: {codigo}")
            continue
        con.executemany("INSERT OR REPLACE INTO bcrp_mensual VALUES (?, ?, ?, ?, ?, ?)",
                        [(codigo, nombre, periodo_bcrp(p["name"]), float(p["values"][0]), url, ahora())
                         for p in periodos if p["values"][0] not in ("n.d.", "")])
        con.commit()
    print(f"  BCRP: {len(series)} series, {con.execute('SELECT COUNT(*) FROM bcrp_mensual').fetchone()[0]} filas")


# --- ENAHO: pobreza monetaria por departamento y año -------------------------------------------------------
# Método de las skills del autor (enaho-skills): pobreza de la sumaria ponderada por factor07 × mieperho, que
# equivale a los miembros con p204 == 1 (lo verifica limpiando-enaho). Solo hace falta el módulo 34.
ENAHO = "https://proyectos.inei.gob.pe/iinei/srienaho/descarga/STATA/{codigo}-Modulo34.zip"
CODIGOS_ENAHO = {2004: 280, 2005: 281, 2006: 282, 2007: 283, 2008: 284, 2009: 285, 2010: 279, 2011: 291, 2012: 324,
                 2013: 404, 2014: 440, 2015: 498, 2016: 546, 2017: 603, 2018: 634, 2019: 687, 2020: 737, 2021: 759,
                 2022: 784, 2023: 906, 2024: 966}  # shortcut: falta 2025, agregar su código cuando el INEI lo publique
POBREZA_OFICIAL = {2004: 58.7, 2005: 55.6, 2006: 49.1, 2007: 42.4, 2008: 37.3, 2009: 33.5, 2010: 30.8, 2011: 27.8,
                   2012: 25.8, 2013: 23.9, 2014: 22.7, 2015: 21.8, 2016: 20.7, 2017: 21.7, 2018: 20.5, 2019: 20.2,
                   2020: 30.1, 2021: 25.9, 2022: 27.5, 2023: 29.0, 2024: 27.6}  # INEI, pobreza monetaria nacional (%)


def pobreza(sumaria) -> list[tuple]:
    """Sumaria (DataFrame) → [(ccdd, pobreza %, extrema %, hogares)]. pobreza: 1 extremo, 2 no extremo, 3 no pobre."""
    s = sumaria.assign(ccdd=sumaria.ubigeo.astype(str).str.zfill(6).str[:2],
                       peso=sumaria.factor07.astype(float) * sumaria.mieperho, cod=sumaria.pobreza.astype(int))
    s = s.assign(pobre=s.peso * (s.cod <= 2), extremo=s.peso * (s.cod == 1))
    g = s.groupby("ccdd")[["peso", "pobre", "extremo"]].sum()
    return [(c, round(100 * r.pobre / r.peso, 2), round(100 * r.extremo / r.peso, 2), int((s.ccdd == c).sum()))
            for c, r in g.iterrows()] + [("00", round(100 * g.pobre.sum() / g.peso.sum(), 2),
                                          round(100 * g.extremo.sum() / g.peso.sum(), 2), len(s))]


def enaho(con, anios=None):
    import zipfile
    import pandas as pd
    from tremor.db import DATOS
    con.execute("""CREATE TABLE IF NOT EXISTS enaho_departamento (ccdd TEXT NOT NULL, anio INTEGER NOT NULL,
                   pobreza REAL, pobreza_extrema REAL, hogares INTEGER, fuente TEXT, consultado TEXT NOT NULL,
                   PRIMARY KEY (ccdd, anio))""")  # ccdd '00' = nacional
    carpeta = DATOS / "crudos" / "enaho"
    carpeta.mkdir(parents=True, exist_ok=True)
    for anio in anios or CODIGOS_ENAHO:
        url, ruta = ENAHO.format(codigo=CODIGOS_ENAHO[anio]), carpeta / f"{CODIGOS_ENAHO[anio]}-Modulo34.zip"
        if not ruta.exists():
            parcial = ruta.with_suffix(".part")  # un corte nunca deja un zip a medias
            parcial.write_bytes(requests.get(url, headers=UA, timeout=600).content)
            parcial.replace(ruta)
        with zipfile.ZipFile(ruta) as z:
            dta = min((n for n in z.namelist() if n.lower().endswith(".dta") and "sumaria" in n.lower()), key=len)  # "sumaria-2017-12" no trae pobreza
            with z.open(dta) as f:
                s = pd.read_stata(f, convert_categoricals=False)
        filas = pobreza(s.rename(columns=str.lower))
        nacional = filas[-1][1]
        if anio in POBREZA_OFICIAL and abs(nacional - POBREZA_OFICIAL[anio]) > 0.5:
            raise RuntimeError(f"ENAHO {anio}: pobreza nacional {nacional}% no cuadra con la oficial {POBREZA_OFICIAL[anio]}%")
        con.executemany("INSERT OR REPLACE INTO enaho_departamento VALUES (?, ?, ?, ?, ?, ?, ?)",
                        [(c, anio, p, e, h, url, ahora()) for c, p, e, h in filas])
        con.commit()
        print(f"  ENAHO {anio}: pobreza nacional {nacional}%, {len(filas) - 1} departamentos")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(prog="python -m tremor.territorio")
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("mef"); m.add_argument("--desde", type=int, default=2012)
    sub.add_parser("bcrp")
    e = sub.add_parser("enaho"); e.add_argument("--anios", type=int, nargs="*")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    {"mef": lambda con: mef(con, a.desde), "bcrp": bcrp, "enaho": lambda con: enaho(con, a.anios)}[a.cmd](conectar())
