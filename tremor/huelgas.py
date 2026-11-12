"""Huelgas del MTPE: serie mensual de minería y total nacional desde 2010, y anual por región.

Anuario Estadístico Sectorial, capítulo de huelgas (Excel): cuadro actividad económica × mes (2011 C-4, 2025 C-95)
y actividad × dirección/gerencia regional (2011 C-11, 2025 C-102). Los zips viejos (2010–2017) solo quedan en
Wayback; los nuevos están en cdn.www.gob.pe. Los meses del año en curso salen del "Reporte mensual de huelgas" (PDF).
`python -m tremor.huelgas`
"""
import io
import re
import sys
import time
import warnings
import zipfile

import pandas as pd
import requests

from tremor.db import DATOS, conectar
from tremor.lugares import norm, resolver
from tremor.territorio import UA

CRUDOS = DATOS / "crudos" / "mtpe"
WB = "http://web.archive.org/web/2025id_/"
UA_WB = {"User-Agent": "tremor/1.0 (PUCP)"}  # Wayback responde 429 a UA de navegador (y al de requests), no a uno propio
VIEJO = "https://www.trabajo.gob.pe/archivos/file/estadisticas/anuario/Anuario{}.zip"
CDN = "https://cdn.www.gob.pe/uploads/document/file/"
ANUARIOS = {a: WB + VIEJO.format(a) for a in range(2010, 2015)} | {
    2015: WB + "https://www2.trabajo.gob.pe/archivos/estadisticas/anuario/Anuario_2015_280616.zip",
    2016: WB + "https://www2.trabajo.gob.pe/archivos/estadisticas/anuario/ANUARIO2016.zip",
    2017: WB + "https://www2.trabajo.gob.pe/archivos/estadisticas/anuario/Anuario-2017.zip",
    2018: CDN + "461127/Cuadros.zip",
    2019: CDN + "921500/Cuadros.zip",
    2020: CDN + "2034699/ANUARIO%202020.zip.zip",
    2021: CDN + "3668970/Anuario%202021.zip",
    2022: CDN + "4930318/anuario%202022.zip",
    2023: CDN + "6837546/5915177-anuarioestadisticosectorial2023archivosexcelypdf.zip",
    2024: CDN + "8796015/7267740-anuario-mtpe-2024.zip",
    2025: CDN + "10367729/8420738-anuario-estadistico-2025-v8.zip",
}  # ponytail: lista a mano; cada anuario nuevo (sale a mitad del año siguiente) se agrega aquí
DATOS_ABIERTOS = "https://www.datosabiertos.gob.pe/sites/default/files/Dataset_Huelgas_MTPE_0.csv"
BUSQUEDA = "https://www.gob.pe/busquedas?contenido[]=publicaciones&institucion[]=mtpe&term=huelgas&sort_by=recent&sheet={}"
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "setiembre", "octubre", "noviembre", "diciembre"]
OFICINAS = {"cerro de pasco": "19", "pucallpa": "25", "puerto maldonado": "17", "quillabamba": "08"}  # ciudades sede que no son nombre de distrito ni provincia
ABREVIADAS = {"no h": "huelgas", "no t c": "trabajadores", "no h hp": "horas_hombre"}  # fila TOTAL del anuario 2010
METRICAS = ("huelgas", "trabajadores", "horas_hombre")
ESQUEMA = """
CREATE TABLE IF NOT EXISTS huelga_mes (anio INTEGER, mes INTEGER, sector TEXT, huelgas INTEGER, trabajadores INTEGER,
    horas_hombre INTEGER, fuente TEXT, PRIMARY KEY (anio, mes, sector));
CREATE TABLE IF NOT EXISTS huelga_region_anio (anio INTEGER, region TEXT, sector TEXT, huelgas INTEGER,
    trabajadores INTEGER, horas_hombre INTEGER, PRIMARY KEY (anio, region, sector));"""


def bajar(url, nombre):
    """Descarga una vez a crudos/mtpe; un corte nunca deja un archivo a medias."""
    ruta = CRUDOS / nombre
    if not ruta.exists():
        CRUDOS.mkdir(parents=True, exist_ok=True)
        for espera in (1, 30, 90, 180):  # Wayback responde 429 o se cuelga si se le pide seguido
            time.sleep(espera)
            try:
                r = requests.get(url, headers=UA_WB if WB in url else UA, timeout=(30, 600))
            except requests.ConnectionError:
                if espera == 180:
                    raise
                continue
            if r.status_code != 429:
                break
        r.raise_for_status()
        ruta.with_suffix(".part").write_bytes(r.content)
        ruta.with_suffix(".part").replace(ruta)
    return ruta


def numero(v) -> int:
    """Celda → entero. Los anuarios ponen "*" (huelga que viene de otro periodo) o "-" donde no hay cifra."""
    if isinstance(v, (int, float)):
        return 0 if pd.isna(v) else int(round(v))
    s = re.sub(r"[\s*,\-]", "", str(v))
    return int(float(s)) if re.fullmatch(r"\d+(\.\d+)?", s) else 0  # "NO SE REGISTRÓ HUELGAS" y similares


def metrica(t):
    if t in ABREVIADAS:
        return ABREVIADAS[t]
    if t.startswith("huelga") and "trabajador" not in t:  # "HUELGAS, TRABAJADORES COMPRENDIDOS..." es el título
        return "huelgas"
    return "trabajadores" if t.startswith("trabajador") else "horas_hombre" if t.startswith("horas") else None


def filas(hoja: pd.DataFrame):
    """Recorre un cuadro sector × (mes | oficina). Rinde ("rotulo", texto) y ("dato", métrica, minería, total).
    Las columnas se leen del encabezado y se releen en cada página (cambian entre páginas)."""
    cmin = ctot = previa = None
    for fila in hoja.itertuples(index=False):
        textos = [(j, norm(v), v) for j, v in enumerate(fila) if isinstance(v, str) and norm(v)]
        if not textos:
            continue
        mina = [j for j, t, _ in textos if t.startswith("explotacion")]
        if mina:
            cmin = mina[0]
            ctot = next((j for j, t, _ in textos if t in ("total", "absoluto")), ctot)
            continue
        if any(t == "absoluto" for _, t, _ in textos):
            ctot = next(j for j, t, _ in textos if t == "absoluto")
            continue
        if cmin is None:
            continue
        _, t, original = textos[0]
        if t.startswith("fuente"):
            cmin = ctot = None  # fin de página; la siguiente trae su propio encabezado
            continue
        m = metrica(t)
        if not m and previa == "trabajadores" and numero(fila[ctot]):
            m = "horas_hombre"  # 2023 C-102: la fila de horas del Callao dice "ICA"; va siempre tras trabajadores
        previa = m
        yield ("dato", m, numero(fila[cmin]), numero(fila[ctot])) if m else ("rotulo", original.strip())


def por_mes(hoja) -> dict:
    """{mes: {métrica: (minería, total)}}; mes 0 = TOTAL del año."""
    out, mes = {}, None
    for f in filas(hoja):
        if f[0] == "rotulo":
            t = norm(f[1]).replace("septiembre", "setiembre")
            mes = 0 if t == "total" else next((i + 1 for i, n in enumerate(MESES) if t.startswith(n)), None)
        elif mes is not None:
            out.setdefault(mes, {})[f[1]] = f[2:]
    return out


def departamento(nombre, actual):
    """Oficina → código de departamento (2 dígitos) o el nombre tal cual. `actual`: último departamento visto."""
    if "nivel nacional" in norm(nombre):  # huelgas de alcance nacional que ve la sede central: no son de Lima
        return "nacional", actual
    partes = [re.sub(r"\(.*?\)|\*", "", p).strip() for p in nombre.split(" - ")]
    r = resolver(region=partes[0])[0]
    if r:
        return r, r
    for p in partes:
        c = OFICINAS.get(norm(p)) or resolver(provincia=p, pista=actual)[0] or resolver(localidad=p, pista=actual)[0]
        if c:
            return c[:2], actual
    return nombre, actual


def por_region(hoja) -> dict:
    """{región: {métrica: [minería, total]}} sumando oficinas del mismo departamento; "TOTAL" = fila nacional."""
    out, clave, actual = {}, None, None
    for f in filas(hoja):
        if f[0] == "rotulo":
            clave, actual = ("TOTAL", actual) if norm(f[1]) == "total" else departamento(f[1], actual)
        elif clave:
            v = out.setdefault(clave, {m: [0, 0] for m in METRICAS})[f[1]]
            v[0] += f[2]
            v[1] += f[3]
    return {k: v for k, v in out.items() if any(any(x) for x in v.values())}


def excel_huelgas(z: zipfile.ZipFile):
    """Busca el Excel de huelgas dentro del zip (y de zips anidados) sin extraer nada a disco."""
    for n in z.namelist():
        if n.lower().endswith(".zip"):
            hallado = excel_huelgas(zipfile.ZipFile(io.BytesIO(z.read(n))))
            if hallado:
                return hallado
        elif "huelga" in n.lower() and n.lower().endswith((".xls", ".xlsx")):
            return n, z.read(n)


def anuario(anio):
    """→ (meses, regiones, archivo). Elige el cuadro por contenido, no por número de hoja."""
    with zipfile.ZipFile(bajar(ANUARIOS[anio], f"anuario_{anio}.zip")) as z:
        nombre, datos = excel_huelgas(z)
    meses = regiones = None
    for hoja in pd.read_excel(io.BytesIO(datos), sheet_name=None, header=None).values():
        cab = {norm(v) for v in hoja.head(12).values.ravel() if isinstance(v, str)}
        if meses is None and cab & {"mes", "meses"}:
            meses = por_mes(hoja) or None
        elif regiones is None and any(t.startswith(("direccion", "gerencia")) for t in cab):
            regiones = por_region(hoja) or None
    return meses, regiones, nombre


def tres(lineas, i):
    """Las tres cifras (huelgas, trabajadores, horas) que siguen a la línea i del PDF."""
    return tuple(numero(x) for x in lineas[i + 1:i + 4])


def reporte_mensual(ruta) -> dict:
    """PDF mensual → {"mineria": (h, t, hh), "total": (h, t, hh)} del cuadro por actividad económica."""
    import pymupdf
    with pymupdf.open(ruta) as doc:
        for pagina in doc:
            lineas = [x.strip() for x in pagina.get_text().splitlines() if x.strip()]
            n = [norm(x) for x in lineas]
            if "actividad economica" in n and "total" in n:
                i = next((k for k, t in enumerate(n) if t.startswith("explotacion de minas")), None)
                return {"mineria": tres(lineas, i) if i is not None else (0, 0, 0), "total": tres(lineas, n.index("total"))}
    raise ValueError(f"{ruta.name}: sin cuadro por actividad económica")


def reportes(desde) -> dict:
    """{(año, mes): PDF en caché} de los reportes mensuales desde el año `desde`. Busca en gob.pe solo lo que falta;
    si gob.pe no responde, se queda con lo ya bajado."""
    cache = {(int(r.stem[8:12]), int(r.stem[13:15])): r for r in CRUDOS.glob("reporte_*.pdf")}
    try:
        for hoja in range(1, 9):
            time.sleep(1)
            html = requests.get(BUSQUEDA.format(hoja), headers=UA, timeout=60).text
            for ruta, mes, anio in re.findall(r"(/institucion/mtpe/informes-publicaciones/\d+-[a-z-]*huelgas-en-el-peru-([a-z]+)-(\d{4}))", html):
                clave = (int(anio), MESES.index(mes) + 1) if mes in MESES else None
                if clave and clave[0] >= desde and clave not in cache:
                    time.sleep(1)
                    pdf = re.search(r'https://cdn\.www\.gob\.pe/uploads/document/file/[^"?]+\.pdf',
                                    requests.get("https://www.gob.pe" + ruta, headers=UA, timeout=60).text)
                    if pdf:
                        cache[clave] = bajar(pdf.group(0), f"reporte_{clave[0]}_{clave[1]:02d}.pdf")
    except requests.RequestException as e:
        print(f"  gob.pe no respondió ({type(e).__name__}); uso los reportes ya bajados")
    return {k: v for k, v in sorted(cache.items()) if k[0] >= desde}


def main():
    t0 = time.time()
    abiertos = pd.read_csv(bajar(DATOS_ABIERTOS, "Dataset_Huelgas_MTPE_0.csv"), encoding="utf-8-sig")
    abiertos.columns = [re.sub(r"\s+", "", c) for c in abiertos.columns]
    abiertos = {int(r.ANIOS): (r.HUELGAS_PLIEGO_RECLAMOS + r.HUELGAS_OTRAS_CAUSAS,
                               r.TRABAJADORES_COMPRENDIDOS_PR + r.TRABAJADORES_COMPRENDIDOS_OC,
                               r.HORAS_HOMBRE_PERDIDAS_PR + r.HORAS_HOMBRE_PERDIDAS_OC) for r in abiertos.itertuples()}
    mes_filas, reg_filas, revision = [], [], []
    for anio in ANUARIOS:
        meses, regiones, archivo = anuario(anio)
        anual = meses.pop(0)
        for mes, v in sorted(meses.items()):
            for k, sector in enumerate(("mineria", "total")):
                mes_filas.append((anio, mes, sector, *(v[m][k] for m in METRICAS), f"anuario {anio}"))
        suma = {s: tuple(sum(v[m][k] for v in meses.values()) for m in METRICAS) for k, s in enumerate(("mineria", "total"))}
        anu = {s: tuple(anual[m][k] for m in METRICAS) for k, s in enumerate(("mineria", "total"))}
        reg = None
        if regiones:  # (fila TOTAL del cuadro regional, suma de las regiones)
            fila = {s: tuple(regiones["TOTAL"][m][k] for m in METRICAS) for k, s in enumerate(("mineria", "total"))}
            sreg = {s: tuple(sum(v[m][k] for r, v in regiones.items() if r != "TOTAL") for m in METRICAS)
                    for k, s in enumerate(("mineria", "total"))}
            reg = (fila, sreg)
        revision.append((anio, len(meses), suma, anu, abiertos.get(anio), reg))
        for region, v in (regiones or {}).items():
            if region != "TOTAL":
                reg_filas += [(anio, region, s, *(v[m][k] for m in METRICAS)) for k, s in enumerate(("mineria", "total"))]
        print(f"  {anio}: {archivo} · {len(meses)} meses · {len(regiones or {}) - 1} regiones", flush=True)
    for (anio, mes), ruta in reportes(max(ANUARIOS) + 1).items():
        v = reporte_mensual(ruta)
        mes_filas += [(anio, mes, s, *v[s], f"reporte mensual {anio}-{mes:02d}") for s in ("mineria", "total")]
    con = conectar()
    con.executescript(ESQUEMA)
    con.executemany("INSERT OR REPLACE INTO huelga_mes VALUES (?, ?, ?, ?, ?, ?, ?)", mes_filas)
    con.executemany("INSERT OR REPLACE INTO huelga_region_anio VALUES (?, ?, ?, ?, ?, ?)", reg_filas)
    con.commit()
    con.close()
    informe(revision, mes_filas, reg_filas)
    print(f"{len(mes_filas)} filas huelga_mes, {len(reg_filas)} huelga_region_anio · {time.time() - t0:.0f} s")


def informe(revision, mes_filas, reg_filas):
    print("\naño meses | Σmeses total (h,t,hh) | anuario total | datosabiertos | Σmeses minería | anuario minería | fila TOTAL y Σ regiones = anuario?")
    for anio, n, suma, anu, da, reg in revision:
        marca = lambda a, b: "=" if a == b else "≠"
        print(f"{anio} {n:2d} | {suma['total']} {marca(suma['total'], anu['total'])} {anu['total']} "
              f"{'' if da is None else marca(anu['total'], tuple(da)) + ' ' + str(tuple(int(x) for x in da))} | "
              f"{suma['mineria']} {marca(suma['mineria'], anu['mineria'])} {anu['mineria']} | "
              f"{'-' if reg is None else marca(reg[0], anu) + marca(reg[1], anu)}")
    print("\nMinería, huelgas por mes (ene..dic):")
    serie = {}
    for anio, mes, sector, h, *_ in mes_filas:
        if sector == "mineria":
            serie.setdefault(anio, {})[mes] = h
    for anio, v in serie.items():
        print(anio, " ".join(f"{v.get(m, '.'):>2}" for m in range(1, 13)), "=", sum(v.values()))
    sin_codigo = sorted({r[1] for r in reg_filas if not r[1].isdigit()})
    print("Oficinas sin código de departamento:", sin_codigo or "ninguna")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    warnings.filterwarnings("ignore", "Unknown extension", UserWarning)  # openpyxl, ruido de los xlsx del MTPE
    main()
