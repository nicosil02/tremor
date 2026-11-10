"""Fiscalización ambiental del OEFA (datos abiertos) por empresa, unidad y distrito: medidas administrativas,
multas firmes, supervisiones y denuncias SINADA, solo de minería, hidrocarburos y electricidad.

El portal se actualizó por última vez el 29 abr 2025 (datos hasta marzo de 2025): es historia y contexto de cada
unidad, no una señal en vivo. Se baja una vez; si las tablas ya tienen filas, no se vuelve a bajar.
No se guarda texto que nombre a personas: el sector de la supervisión sale del número del informe, no de la
columna de coordinación (que en algunas filas trae el nombre del supervisor).

    python -m tremor.oefa          # carga (o nada, si ya está)
    python -m tremor.oefa --forzar # vuelve a bajar
"""
import io
import re
import sys
from datetime import date

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
    # el sector sale del número del informe (…/DSEM-CMIN); la columna de coordinación trae a veces el nombre del
    # supervisor, así que no se guarda: la fila se conserva y la persona no queda en la base
    v = v.assign(sector=v.NRO_INFORME.str.extract(r"-C(MIN|HID|ELE)(?![A-Z])")[0].map(
        {"MIN": "Minería", "HID": "Hidrocarburos", "ELE": "Electricidad"})).dropna(subset=["sector"])
    supervision = pd.DataFrame({"administrado": v.ADMINISTRADO, "unidad": v.UNIDAD_FISCALIZABLE, "sector": v.sector,
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


# Resoluciones de primera instancia (DFAI) publicadas en gob.pe: siguen al día (~3 meses de rezago) cuando el portal
# de datos abiertos ya no. Cada entrada trae número, fecha, administrado y qué se decidió; la unidad está en el PDF.
DFAI = "https://www.gob.pe/institucion/oefa/colecciones/1758-resoluciones-de-dfai?sheet={}"
MESES = dict(zip("enero febrero marzo abril mayo junio julio agosto septiembre setiembre octubre noviembre diciembre".split(),
                 [1, 2, 3, 4, 5, 6, 7, 8, 9, 9, 10, 11, 12]))
# en gob.pe la fecha va ANTES del número; hasta nov 2017 la oficina era la DFSAI (numeración propia: sufijo "-S")
_ITEM = re.compile(r"(\d{1,2}) de (\w+) de (\d{4})\s*\n\s*Resoluci\S+ N\S*?\s*(\d{1,4})-(\d{4})-OEFA[/-]DF(S?)AI[^\n]*\n\s*([^\n]+)")
TIPO = [("multa", r"multa"), ("responsabilidad", r"responsabilidad"), ("archivo", r"archiv"),
        ("reconsideracion", r"reconsideraci"), ("otro", r"")]
# el administrado va después de "administrado", "interpuesto por", "presentada por" o "correctiva a", antes de la coma
_ADM = re.compile(r"(?:administrad[oa]|seguid[oa] a|coercitiva a|interpuest[oa] por|presentad[oa] por|correctivas? a|responsabilidad administrativa (?:a|de))"
                  r"\s+(.+?)(?:,| por los| al haber|\s*\.\.\.|$)")


# solo personas jurídicas y entidades públicas: de una persona natural no se guarda el nombre ni el resumen
L = "A-ZÁÉÍÓÚÑ"  # siglas como palabra entera: "SA" no debe calzar con la de "SANCHEZ"
JURIDICA = (rf"(?<![{L}])(?:S\.?\s?A\.?(?:\s?[CA]\.?)?|S\.?\s?R\.?\s?L\.?|E\.?\s?I\.?\s?R\.?\s?L\.?|S\.?\s?C\.?\s?R\.?\s?L\.?"
            rf"|INC|LTD|EPS)(?![{L}])|(?<![{L}])(?:SOCIEDAD|EMPRESA|COMPA|CORPORACI|MUNICIPALIDAD|GOBIERNO|MINISTERIO"
            r"|ASOCIACI|COOPERATIVA|CONSORCIO|UNIVERSIDAD|INSTITUTO|PETR[OÓ]LEO|LIMITED|COMUNIDAD|PROYECTO|PROGRAMA"
            r"|SERVICIO|HOSPITAL|ELECTRO|MINERA|GRUPO|GRIFO|ESTACI[OÓ]N|INVERSIONES|INDUSTRIA|NEGOCIACI)")


def leer_dfai(html_):
    out = []
    for d, mes_, a, n, anio, s, res in _ITEM.findall(_texto(html_)):
        res, anio = res.strip(" |\xa0"), anio + ("-S" if s else "")
        adm = _ADM.search(res)
        adm = adm[1].strip(" .").upper() if adm else None
        natural = adm is not None and not re.search(JURIDICA, adm)
        out.append({"num": f"{int(n):04d}-{anio}", "fecha": f"{a}-{MESES.get(mes_.lower(), 0):02d}-{int(d):02d}",
                    "administrado": "PERSONA NATURAL" if natural else adm,
                    "tipo": next(k for k, p in TIPO if re.search(p, res, re.I)), "resumen": None if natural or adm is None else res[:200]})
    return out


# Segunda instancia: la Sala del Tribunal de Fiscalización Ambiental (TFA-SE), ~3 semanas de rezago. Cada resolución
# cita la de la DFAI que revisa; la empresa sale de ahí (no se guarda texto: puede nombrar a personas).
TFA = ("https://www.gob.pe/institucion/oefa/colecciones/1716-sala-especializada-en-mineria-energia-actividades-"
       "productivas-e-infraestructura-y-servicios-tfa-se?sheet={}")
# Hasta 2019 la redacción era otra: "RESOLUCIÓN N° 339-2018-OEFA/TFA-SMEPIM" y otras salas (SMEPIM, SEPIM, SEE).
_TFA = re.compile(r"(\d{1,2}) de (\w+) de (\d{4})\s*\n\s*Resoluci\S+ N\S*?\s*(\d{1,4})-(\d{4})-OEFA[/-]TFA-(S\w*)[^\n]*\n\s*([^\n]+)",
                  re.I)
DECISION = [("confirma", r"\bconfirma"), ("revoca", r"\brevoca"), ("nulidad", r"nulidad"), ("improcedente", r"improcedente"),
            ("otro", r"")]


def _texto(html_):
    import html as h
    t = re.sub(r"<[^>]+>", "\n", re.sub(r"<script.*?</script>|<style.*?</style>", " ", html_, flags=re.S))
    return h.unescape(h.unescape(t))  # gob.pe escapa dos veces ("&amp;amp;")


def leer_tfa(html_):
    out = []
    for d, mes_, a, n, anio, sala, res in _TFA.findall(_texto(html_)):
        ref = re.search(r"(\d{1,5})-(\d{4})-OEFA[/-]DF(S?)AI", res)
        sala = sala.upper()  # cada sala numera aparte: la SE (desde 2019) sin sufijo, las antiguas con el suyo
        out.append({"num": f"{int(n):04d}-{anio}" + ("" if sala == "SE" else f"-{sala}"), "fecha": f"{a}-{MESES.get(mes_.lower(), 0):02d}-{int(d):02d}",
                    "dfai": f"{int(ref[1]):04d}-{ref[2]}" + ("-S" if ref[3] else "") if ref else None,
                    "decision": next(k for k, p in DECISION if re.search(p, res, re.I))})
    return out


def razon_social(s):
    """'MINERA BATEAS S.A.C.' y 'Minera Bateas SAC' → 'minera bateas': para cruzar la DFAI con las operaciones."""
    s = norm(str(s or ""))
    s = re.sub(r"\b(s\s?a\s?[ca]?|s\s?r\s?l|e\s?i\s?r\s?l|s\s?c\s?r\s?l|sociedad anonima( cerrada| abierta)?|"
               r"sucursal( del)? peru|en liquidacion|inc|ltd|limited)\b", " ", re.sub(r"[^a-z0-9 ]", " ", s))
    return " ".join(s.split())


COLECCIONES = {"oefa_dfai": (DFAI, leer_dfai, "num TEXT PRIMARY KEY, fecha TEXT, administrado TEXT, tipo TEXT, resumen TEXT"),
               "oefa_tfa": (TFA, leer_tfa, "num TEXT PRIMARY KEY, fecha TEXT, dfai TEXT, decision TEXT")}


def coleccion(con, tabla, hasta_pagina=2000, pausa=0.5, anio=None):
    """Baja una colección de gob.pe, de lo más nuevo hacia atrás, hasta una página ya guardada o el final. gob.pe no
    pagina más allá de ~10 000 resultados: lo anterior se baja año por año (`anio`), con su filtro de fechas."""
    import time
    url, leer, columnas = COLECCIONES[tabla]
    con.execute(f"CREATE TABLE IF NOT EXISTS {tabla} ({columnas})")
    nuevas, habia = 0, con.execute(f"SELECT COUNT(*) FROM {tabla}").fetchone()[0]
    for p in range(1, hasta_pagina + 1):
        for i in range(4):
            try:
                r = requests.get(url.format(p), timeout=60, headers={"User-Agent": "Tremor/1.0 (github.com/nicosil02/tremor)"},
                                 params={"filter[start_date]": f"{anio}-01-01", "filter[end_date]": f"{anio}-12-31"} if anio else None)
                r.encoding = "utf-8"
                filas = leer(r.text)
                if filas or i >= 1:  # gob.pe a veces devuelve una página vacía al azar: un reintento antes de darla por final
                    break
                time.sleep(20)
            except requests.RequestException:
                time.sleep(15 * (i + 1))
        else:
            raise RuntimeError(f"gob.pe no responde en la página {p}")
        if not filas:
            if re.search(r"Resoluci\S+ N\S*?\s*\d", _texto(r.text), re.I):  # hay resoluciones que no se leen: no es el final
                print(f"  {tabla}: la página {p} trae resoluciones en un formato que no se lee")
                continue
            break
        antes = con.total_changes
        con.executemany(f"INSERT OR IGNORE INTO {tabla} VALUES ({', '.join(':' + k for k in filas[0])})", filas)
        con.commit()
        nuevas += con.total_changes - antes
        if habia and not anio and con.total_changes == antes and p > 3:  # página entera ya conocida: lo que sigue también
            break
        time.sleep(pausa)
    print(tabla, nuevas, "nuevas;", tuple(con.execute(f"SELECT COUNT(*), MIN(fecha), MAX(fecha) FROM {tabla}").fetchone()))


RUIAS = "https://sistemas.oefa.gob.pe/ruias/mfe/"


def leer_ruias(js):
    """Reincidentes del RUIAS: vienen como objetos dentro del JavaScript de la página. Es una foto (los registros
    vencen y salen), así que va a la ficha de la app y no al modelo. Sin RUC/DNI ni personas naturales."""
    import json
    s = lambda k, o: json.loads('"' + re.sub(r"\\x([0-9A-Fa-f]{2})", r"\\u00\1", (re.search(k + r':"((?:[^"\\]|\\.)*)"', o) or [0, ""])[1]) + '"')
    f = lambda k, o: "-".join(reversed(s(k, o).split("/"))) if re.match(r"\d", s(k, o)) else None  # 11/07/2022 → 2022-07-11; "No aplica" → None
    out = []
    for o in re.findall(r"\{numero:\d+,.*?\}", js):
        adm = s("nombreRazonSocial", o)
        if not re.search(JURIDICA, adm.upper()):
            continue
        out.append({"expediente": s("nroExpediente", o), "administrado": adm.upper(), "sector": s("sectorEconomico", o),
                    "unidad": s("unidadAmbiental", o), "ubigeo": _ubigeo(s("departamento", o), s("provincia", o), s("distrito", o)),
                    "reincidente_desde": f("fechaResolucionReincidente", o), "confirmada": f("fechaResolucionConfirma", o)})
    actualizado = re.search(r'fechaActualizacion:"([^"]+)"', js)
    return out, actualizado[1] if actualizado else None


def ruias(con):
    h = {"User-Agent": "Tremor/1.0 (github.com/nicosil02/tremor)"}
    main = re.search(r'src="(main-[^"]+\.js)"', requests.get(RUIAS, timeout=60, headers=h).text)[1]
    filas, actualizado = leer_ruias(requests.get(RUIAS + main, timeout=60, headers=h).text)
    pd.DataFrame(filas).assign(actualizado=actualizado).to_sql("oefa_ruias", con, if_exists="replace", index=False)
    con.commit()
    print("oefa_ruias", len(filas), "reincidentes; actualizado", actualizado)


def dfai(con):
    if not con.execute("SELECT name FROM sqlite_master WHERE name = 'oefa_dfai'").fetchone():
        for a in range(2016, date.today().year + 1):  # la primera vez, año por año: gob.pe no pagina más allá de ~10 000
            coleccion(con, "oefa_dfai", anio=a)
    coleccion(con, "oefa_dfai")
    if not con.execute("SELECT name FROM sqlite_master WHERE name = 'oefa_tfa'").fetchone() or \
            con.execute("SELECT MIN(fecha) FROM oefa_tfa").fetchone()[0] > "2017":  # sin la historia: año por año
        for a in range(2016, date.today().year + 1):
            coleccion(con, "oefa_tfa", anio=a)
    coleccion(con, "oefa_tfa")
    ruias(con)


if __name__ == "__main__":
    if "dfai" in sys.argv:
        dfai(conectar())
    else:
        cargar(conectar(), forzar="--forzar" in sys.argv)
