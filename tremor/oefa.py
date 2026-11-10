"""Fiscalización ambiental del OEFA (datos abiertos) por empresa, unidad y distrito: medidas administrativas,
multas firmes, supervisiones y denuncias SINADA, solo de minería, hidrocarburos y electricidad.

El portal se actualizó por última vez el 29 abr 2025 (datos hasta marzo de 2025): es historia y contexto de cada
unidad, no una señal en vivo. Se baja una vez; si las tablas ya tienen filas, no se vuelve a bajar.
No se guarda texto que nombre a personas (la columna de coordinación trae nombres de supervisores en algunas filas).

    python -m tremor.oefa          # carga (o nada, si ya está)
    python -m tremor.oefa --forzar # vuelve a bajar
"""
import io
import re
import sys

import pandas as pd
import requests

from tremor.db import conectar
from tremor.lugares import norm, resolver

PORTAL = "https://datosabiertos.oefa.gob.pe/datasets/"
FUENTES = {
    "medida": "197768-medidas-administrativas-de-las-direcciones-de-supervision-2016-2025",
    "multa": "197772-resolucion-con-multa-firmes-2019-2025",
    "sinada": "197779-denuncias-sinada-2019-2025",
    "supervision": "197769-informes-de-la-direccion-de-supervision-2019-2025",
}
SECTOR = r"miner|hidrocarb|electric|^min$|^hid$|^ele$"  # el OEFA escribe el sector de cuatro formas distintas


def _bajar(clave):
    r = requests.get(f"{PORTAL}{FUENTES[clave]}.download/", timeout=300,
                     headers={"User-Agent": "Tremor/1.0 (alertas de conflicto social; github.com/nicosil02/tremor)"})
    r.raise_for_status()
    return pd.read_excel(io.BytesIO(r.content))


def _ubigeo(d, p, x):
    return resolver(region=d, provincia=p, distrito=x)[0]


def soles(s):
    """'S/.24.866,80' y 'S/.23,000,000.00' (el OEFA mezcla los dos formatos) → float."""
    s = re.sub(r"[^\d.,]", "", re.sub(r"^\s*S/\.?", "", str(s or "")))
    if not s:
        return None
    if re.search(r",\d{1,2}$", s):  # coma decimal
        s = s.replace(".", "").replace(",", ".")
    return float(s.replace(",", ""))


def _sector(serie):
    return serie.map(norm).str.contains(SECTOR)


def tablas():
    m = _bajar("medida")
    m = m[_sector(m.SECTOR)]
    medida = pd.DataFrame({"administrado": m.ADMIN, "unidad": m.UF, "sector": m.SECTOR,
                           "fecha": pd.to_datetime(m.FECHA_RESOLUCION, errors="coerce").dt.strftime("%Y-%m-%d"),
                           "ubigeo": [_ubigeo(*t) for t in zip(m.REGION, m.PROVINCIA, m.DISTRITO)],
                           "tipo": m.DESCRIPCION_TIPO, "estado": m.ESTADO_DE_LA_MEDIDA_ADMINISTRATIVA,
                           "mandato": m.DESCRIPCION_DEL_MANDATO.str.slice(0, 300)})
    f = _bajar("multa")
    f = f[_sector(f.SECTOR)]
    multa = pd.DataFrame({"administrado": f.ADMINISTRADO, "unidad": f["UNIDAD AMBIENTAL"], "sector": f.SECTOR,
                          "fecha": pd.to_datetime(f["FECHA DE EMISION DE LA RESOLUCION DE PRIMERA INSTANCIA"],
                                                  errors="coerce").dt.strftime("%Y-%m-%d"),
                          "ubigeo": [_ubigeo(*t) for t in zip(f.DEPARTAMENTO, f.PROVINCIA, f.DISTRITO)],
                          "infraccion": f["TIPO DE INFRACCION"], "soles": f["MULTA (SOLES)"].map(soles)})
    s = _bajar("sinada")
    s = s[_sector(s["ACTIVIDAD ECONOMICA"])]
    componentes = ["AGUA", "AIRE", "SUELO", "FAUNA", "FLORA", "POBLACION"]
    sinada = pd.DataFrame({"codigo": s["CODIGO SINADA"],
                           "fecha": pd.to_datetime(s["FECHA DE REGISTRO"], errors="coerce").dt.strftime("%Y-%m-%d"),
                           "ubigeo": [_ubigeo(*t) for t in zip(s.DEPARTAMENTO, s.PROVINCIA, s.DISTRITO)],
                           "actividad": s["ACTIVIDAD ECONOMICA"].str.capitalize(),
                           "afecta": s[componentes].apply(lambda r: ", ".join(c.lower() for c in componentes if r[c] == 1), axis=1),
                           "estado": s.ESTADO})
    v = _bajar("supervision")
    v = v[v.COORDINACION.map(norm).str.contains(SECTOR)]  # descarta también las filas corridas con nombres de personas
    supervision = pd.DataFrame({"administrado": v.ADMINISTRADO, "unidad": v.UNIDAD_FISCALIZABLE,
                                "sector": v.COORDINACION.str.replace("COORDINACIÓN DE SUPERVISIÓN AMBIENTAL EN ", "").str.capitalize(),
                                "fecha": pd.to_datetime(v.FECHA_INFORME, errors="coerce").dt.strftime("%Y-%m-%d"),
                                "tipo": v.TIPO_DE_SUPERVISION, "obligaciones": pd.to_numeric(v.CANTIDAD_OBLIGACIONES, errors="coerce")})
    return {"oefa_medida": medida, "oefa_multa": multa, "oefa_sinada": sinada, "oefa_supervision": supervision}


def cargar(con, forzar=False):
    if not forzar and con.execute("SELECT 1 FROM sqlite_master WHERE name = 'oefa_supervision'").fetchone():
        print("OEFA ya cargado (el portal no publica desde abril de 2025).")
        return
    for nombre, df in tablas().items():
        df.to_sql(nombre, con, if_exists="replace", index=False)
        print(nombre, len(df), "filas;", f"{df.ubigeo.notna().mean():.0%} con ubigeo" if "ubigeo" in df else "")
    con.commit()


def fiscalizacion(con, empresa=None, ubigeo=None):
    """Lo del OEFA de una empresa (razón social o parte de ella) o de un lugar (ubigeo de 2, 4 o 6 dígitos)."""
    def q(tabla, extra=""):
        if empresa:
            w, a = "administrado LIKE ?", [f"%{empresa.upper()}%"]
        else:
            w, a = "ubigeo LIKE ?", [f"{ubigeo}%"]
        if tabla == "oefa_supervision" and not empresa:  # la supervisión no trae lugar: se toma de las unidades conocidas
            w = "unidad IN (SELECT unidad FROM oefa_medida WHERE ubigeo LIKE ? UNION SELECT unidad FROM oefa_multa WHERE ubigeo LIKE ?)"
            a = a * 2
        return pd.read_sql(f"SELECT * FROM {tabla} WHERE {w} {extra}", con, params=a)
    med, mul, sup = q("oefa_medida", "ORDER BY fecha DESC"), q("oefa_multa", "ORDER BY fecha DESC"), q("oefa_supervision")
    sin = q("oefa_sinada", "ORDER BY fecha DESC") if ubigeo else pd.DataFrame()
    return {
        "medidas_administrativas": {"total": len(med), "incumplidas": int((med.estado == "INCUMPLIDA").sum()),
                                    "ultimas": med.head(5).to_dict("records")},
        "multas_firmes": {"total": len(mul), "soles": round(float(mul.soles.sum()), 2) if len(mul) else 0,
                          "ultimas": mul.head(5).to_dict("records")},
        "supervisiones": {"total": len(sup), "por_anio": sup.fecha.str[:4].value_counts().sort_index().to_dict()},
        **({"denuncias_sinada": {"total": len(sin), "por_anio": sin.fecha.str[:4].value_counts().sort_index().to_dict(),
                                 "ultimas": sin.head(5).to_dict("records")}} if ubigeo else {}),
        "cubre": "2016-2025 (medidas), 2019-2025 (multas, supervisiones y SINADA); el OEFA no publica desde abril de 2025",
        "fuente": "https://datosabiertos.oefa.gob.pe",
    }


if __name__ == "__main__":
    cargar(conectar(), forzar="--forzar" in sys.argv)
