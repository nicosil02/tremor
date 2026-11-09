"""Producción minera metálica por unidad y mes (MINEM, declaraciones ESTAMIN), 2001 a hoy.

gob.pe publica un archivo por año (7z o zip): hasta 2019 un Excel por metal, desde 2020 uno con todos. Cada fila es
titular × unidad × distrito × metal con los doce meses. Queda en `produccion_unidad` (ubigeo INEI) y de ahí salen
las variables por distrito-mes para el modelo. `python -m tremor.produccion` (baja lo que falte y recarga).
"""
import io
import re
import sys
import zipfile
from functools import lru_cache
from pathlib import Path

import pandas as pd
import requests

from tremor.db import RAIZ, conectar
from tremor.lugares import norm

PAGINA = "https://www.gob.pe/institucion/minem/informes-publicaciones/5472883-produccion-minera"
CARPETA = RAIZ / "datos" / "crudos" / "minem_produccion"
NAVEGADOR = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "setiembre", "octubre", "noviembre",
         "diciembre"]
METALES = {"cobre", "oro", "plata", "zinc", "plomo", "hierro", "molibdeno", "estano", "cadmio", "tungsteno",
           "arsenico", "bismuto", "manganeso", "indio", "selenio", "antimonio", "teluro", "mercurio"}


def bajar():
    html = requests.get(PAGINA, headers=NAVEGADOR, timeout=60).text
    CARPETA.mkdir(parents=True, exist_ok=True)
    for url in sorted(set(re.findall(r'https://cdn\.www\.gob\.pe/uploads/document/file/[^"\s?]+\.(?:zip|7z)', html))):
        destino = CARPETA / url.rsplit("/", 1)[1]
        if not destino.exists() or "2026" in destino.name:  # el del año en curso se actualiza cada mes
            destino.write_bytes(requests.get(url, headers=NAVEGADOR, timeout=300).content)


def excels():
    """(nombre, bytes) de cada Excel metálico, abriendo zips dentro de 7z dentro de zips."""
    import py7zr

    def abrir(nombre, datos):
        if nombre.lower().endswith(".7z"):
            import tempfile
            with tempfile.TemporaryDirectory() as d:  # py7zr nuevo ya no lee a memoria: se extrae y se lee
                with py7zr.SevenZipFile(io.BytesIO(datos)) as z:
                    z.extractall(d)
                for p in sorted(Path(d).rglob("*")):
                    if p.is_file():
                        yield from abrir(p.name, p.read_bytes())
        elif nombre.lower().endswith(".zip"):
            with zipfile.ZipFile(io.BytesIO(datos)) as z:
                for n in z.namelist():
                    yield from abrir(n, z.read(n))
        elif nombre.lower().endswith((".xls", ".xlsx")):
            base = norm(Path(nombre).stem)
            if re.search(r"no metal|carbon|concentrado|metales$|otros", base):  # METALES.XLS repite los otros
                return
            yield nombre, datos

    for f in sorted(CARPETA.glob("*")):
        if f.suffix in (".zip", ".7z"):
            yield from abrir(f.name, f.read_bytes())


def leer(nombre, datos) -> pd.DataFrame:
    """Una hoja → filas largas (anio, mes, mineral, unidad_medida, titular, unidad, departamento, provincia, distrito,
    valor). Los formatos cambian por año: se busca la fila de títulos (la que dice TITULAR)."""
    salida = []
    for hoja, d in pd.read_excel(io.BytesIO(datos), header=None, sheet_name=None).items():
        fila = next((i for i in range(min(len(d), 30)) if any(norm(x) == "titular" for x in d.iloc[i])), None)
        if fila is None:
            antiguo = leer_antiguo(nombre, d)
            if len(antiguo):
                salida.append((False, antiguo))
            continue
        titulo = " ".join(str(x) for x in d.iloc[:fila].stack())
        anio = int(re.findall(r"(20\d\d)", titulo + " " + nombre)[-1])
        mes = {m[:3]: m for m in MESES} | {"sep": "setiembre"}  # 2020-2023 abrevian: ENE, FEB, SET
        cols = [MESES[x.month - 1] if hasattr(x, "month") else mes.get(norm(x), norm(x)) for x in d.iloc[fila]]
        d = d.iloc[fila + 1:].set_axis(cols, axis=1)
        col = lambda *ks: next((c for c in cols if c in ks), None)
        meses = [c for c in cols if c in MESES]
        mineral = col("mineral", "producto", "metal")
        medida = col("unidad de medida", "unidad medida")
        fijo = norm(Path(nombre).stem)
        if not mineral:  # un archivo por metal (hasta 2019): el metal y la unidad están en el título
            metal = next((m for m in METALES if m in norm(titulo) or m in fijo), fijo)
            d = d.assign(mineral=metal, medida=re.search(r"\(([^)]+)\)", titulo)[1] if "(" in titulo else "")
            mineral, medida = "mineral", "medida"
        if not col("etapa"):
            d = d.assign(etapa="")
        ids = [mineral, medida, "etapa", col("titular"), col("unidad", "unidad minera"), col("region", "departamento"),
               col("provincia"), col("distrito")]
        if None in ids or not meses:
            print(f"  {nombre} / {hoja}: formato no reconocido, se salta")
            continue
        d = d[d[col("titular")].notna() & ~d[col("titular")].astype(str).str.contains("TOTAL", case=False)]
        largo = d.melt(id_vars=ids, value_vars=meses, var_name="mes", value_name="valor")
        largo.columns = ["mineral", "unidad_medida", "etapa", "titular", "unidad", "departamento", "provincia",
                         "distrito", "mes", "valor"]
        largo["valor"] = pd.to_numeric(largo.valor, errors="coerce")
        salida.append((bool(medida != "medida"), largo[largo.valor > 0].assign(anio=anio, mes=largo.mes.map(MESES.index) + 1)))
    # 2020 trae una hoja con todos los metales y además una por metal: si hay hoja completa, solo esa
    completas = [x for c, x in salida if c]
    salida = completas or [x for _, x in salida]
    return pd.concat(salida) if salida else pd.DataFrame()


def leer_antiguo(nombre, d) -> pd.DataFrame:
    """2001-2010: una hoja por metal, la empresa en una fila y sus unidades debajo. 2006-2010 traen tres columnas por
    mes (principal, subproducto, total: se toma el total); 2002-2005, una, con UNIDAD MINERA una fila más abajo."""
    u = next((i for i in range(min(len(d), 30)) if any(norm(x) == "unidad minera" for x in d.iloc[i])), None)
    if not u:
        return pd.DataFrame()
    titulo = " ".join(str(x) for x in d.iloc[:u].stack())
    anio = int(re.findall(r"(20\d\d)", titulo)[-1])
    metal = next((m for m in METALES if m in norm(titulo)), norm(Path(nombre).stem))
    medida = re.search(r"\(([^)]+)\)", titulo)[1] if "(" in titulo else ""
    sub = [norm(x) for x in d.iloc[u]]
    pos = lambda *ks: next((i for i, x in enumerate(sub) if x in ks), None)
    c = {"unidad": pos("unidad minera"), "distrito": pos("distrito"), "provincia": pos("provincia"),
         "departamento": pos("departamento", "region")}
    if None in c.values():
        return pd.DataFrame()
    meses = {}  # mes -> columna con el total de ese mes
    for fila in (d.iloc[u - 1], d.iloc[u]):
        for j, x in enumerate(norm(v) for v in fila):
            x = ({m[:3]: m for m in MESES} | {"sep": "setiembre"}).get(x, x)  # 2003-2005 abrevian: ENE, SEP
            if x in MESES:
                meses[MESES.index(x) + 1] = next((k for k in range(j, min(j + 4, len(sub))) if sub[k] == "total"), j)
    filas, empresa, seccion = [], None, ""
    for _, r in d.iloc[u + 1:].iterrows():
        if re.match(r"\s*\d\.-", str(r.iloc[0])):
            seccion = norm(r.iloc[0])  # "2.- REFINACIÓN": el mismo metal ya contado en la concentración
        if "refin" in seccion or "fundic" in seccion:
            continue
        uni, dist = r.iloc[c["unidad"]], r.iloc[c["distrito"]]
        nombres = [str(x).strip() for x in r.iloc[1:c["unidad"]] if pd.notna(x) and str(x).strip()]
        if nombres:  # la empresa (o un subtotal como GRAN MINERÍA, que pisa la siguiente empresa)
            empresa = nombres[0]
        if pd.isna(uni) or pd.isna(dist) or not empresa:
            continue
        for m, k in meses.items():
            v = pd.to_numeric(r.iloc[k], errors="coerce")
            if v and v > 0:
                filas.append({"mineral": metal, "unidad_medida": medida, "etapa": "", "titular": empresa,
                              "unidad": str(uni).strip(), "departamento": r.iloc[c["departamento"]],
                              "provincia": r.iloc[c["provincia"]], "distrito": dist, "mes": m, "valor": v, "anio": anio})
    return pd.DataFrame(filas)


@lru_cache(maxsize=None)
def ubigeo(dep, prov, dist):
    from tremor.distritos import ubigeo_inei
    return ubigeo_inei(dep, prov, dist)


def cargar(con):
    t = pd.concat([leer(n, b) for n, b in excels()], ignore_index=True)
    t["mineral"] = t.mineral.map(norm)
    m = t.unidad_medida.map(norm).str.replace(".", "", regex=False)
    t["unidad_medida"] = m.str[:2].map({"kg": "kg finos", "gr": "g finos", "g ": "g finos", "tm": "TMF"}).fillna(m)
    t["ubigeo"] = [ubigeo(*x) for x in zip(t.departamento.astype(str), t.provincia.astype(str), t.distrito.astype(str))]
    t["etapa"] = t.etapa.map(norm)  # concentración, beneficio, fundición, refinación: no sumar las dos últimas (doble conteo)
    t = t.groupby(["anio", "mes", "mineral", "unidad_medida", "etapa", "titular", "unidad", "ubigeo"], dropna=False,
                  as_index=False).valor.sum()
    t.to_sql("produccion_unidad", con, if_exists="replace", index=False)
    con.commit()
    sin = t.ubigeo.isna().mean()
    print(f"{len(t)} unidad-metal-mes, {t.anio.min()}-{t.anio.max()}, {t.unidad.nunique()} unidades; "
          f"{sin:.1%} sin distrito")
    return t


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    bajar()
    cargar(conectar())
