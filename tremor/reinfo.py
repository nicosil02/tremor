"""Minería informal por distrito: inscripciones vigentes en el REINFO (Registro Integral de Formalización Minera, MINEM).

El registro es público (pad.minem.gob.pe/REINFO_WEB) y se consulta por páginas de 25. De cada fila solo se guarda el
lugar del derecho minero: nunca el nombre ni el RUC del declarante. Sale a distrito_variable como `reinfo_vigentes`
(foto, anio 0). Una inscripción en el REINFO es minería informal en vías de formalización; la ilegal no se registra.

    python -m tremor.reinfo            # ~950 páginas, cerca de una hora; si se corta, al repetir sigue donde quedó
"""
import json
import sys
import time
from collections import Counter

import requests
from bs4 import BeautifulSoup

from tremor.db import DATOS, conectar
from tremor.lugares import resolver

URL = "https://pad.minem.gob.pe/REINFO_WEB/Index.aspx"
UA = {"User-Agent": "Mozilla/5.0 (tremor; investigacion PUCP)"}


def lugares(html):
    """(página, total de páginas, [(departamento, provincia, distrito)]) de una página del listado."""
    b = BeautifulSoup(html, "html.parser")
    filas = []
    for tr in b.find(id="stdregistro").find_all("tr"):
        # la fila es una celda que envuelve a las nueve: nº, RUC, declarante, código, derecho, departamento, provincia,
        # distrito y estado
        c = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
        if len(c) == 10 and c[1].isdigit():
            filas.append(tuple(c[6:9]))
    return int(b.find(id="txtpagina")["value"]), int(b.find(id="txttotal")["value"]), filas, b


def _campos(b, pagina):
    d = {i["name"]: i.get("value", "") for i in b.find_all("input") if i.get("name") and i.get("type") in ("hidden", "text")}
    for s in b.find_all("select"):
        o = s.find("option", selected=True) or s.find("option")
        d[s["name"]] = o["value"] if o else ""
    return d | {"txtpagina": str(pagina), "ImgBtnSiguiente.x": "5", "ImgBtnSiguiente.y": "5"}  # "siguiente" desde esa página


def bajar(pausa=1.0):
    """Counter {(departamento, provincia, distrito): inscripciones vigentes}. Guarda el avance en datos/cache."""
    avance = DATOS / "cache" / "reinfo.json"
    avance.parent.mkdir(parents=True, exist_ok=True)
    hecho = json.loads(avance.read_text(encoding="utf-8")) if avance.exists() else {"pagina": 0, "n": {}}
    n = Counter(hecho["n"])
    s = requests.Session()
    pag, total, filas, b = lugares(s.get(URL, headers=UA, timeout=90).text)
    if hecho["pagina"] == 0:
        n.update("|".join(f) for f in filas)
        hecho["pagina"] = 1
    while hecho["pagina"] < total:
        for intento in range(5):
            try:
                pag, total, filas, b2 = lugares(s.post(URL, data=_campos(b, hecho["pagina"]), headers=UA, timeout=90).text)
                break
            except (requests.RequestException, AttributeError, TypeError, ValueError):
                time.sleep(10 * (intento + 1))
        else:
            raise SystemExit(f"REINFO no responde en la página {hecho['pagina'] + 1}; al repetir sigue desde ahí")
        if not filas:  # cambió el formato de la tabla: mejor parar que contar cero
            raise SystemExit(f"REINFO: la página {pag} llegó sin filas")
        if pag != hecho["pagina"] + 1:
            raise SystemExit(f"REINFO devolvió la página {pag} en vez de la {hecho['pagina'] + 1}")
        b = b2
        n.update("|".join(f) for f in filas)
        hecho = {"pagina": pag, "n": dict(n)}
        if pag % 20 == 0 or pag == total:
            avance.write_text(json.dumps(hecho, ensure_ascii=False), encoding="utf-8")
            print(f"  página {pag} de {total}", flush=True)
        time.sleep(pausa)
    return Counter({tuple(k.split("|")): v for k, v in n.items()})


# Distritos que el REINFO escribe distinto que el catálogo del INEI
OTRO_NOMBRE = {("ICA", "NASCA", "NASCA"): "110301", ("ANCASH", "HUARAZ", "PAMPAS GRANDE"): "020109",
               ("TACNA", "TACNA", "CORONEL GREGORIO ALBARRACIN LANCHIPA"): "230110",
               ("HUANUCO", "HUANUCO", "QUISQUI (KICHKI)"): "100106", ("APURIMAC", "AYMARAES", "IHUAYLLO"): "030407"}


def por_ubigeo(conteo):
    """{ubigeo: inscripciones} y cuántas quedaron sin distrito reconocido."""
    out, fuera = Counter(), 0
    for (dep, prov, dist), v in conteo.items():
        u = OTRO_NOMBRE.get((dep, prov, dist)) or resolver(region=dep, provincia=prov, distrito=dist)[0]
        if u and len(u) == 6:
            out[u] += v
        else:
            fuera += v
    return out, fuera


def main():
    from tremor.distritos import guardar
    sys.stdout.reconfigure(encoding="utf-8")
    conteo = bajar()
    out, fuera = por_ubigeo(conteo)
    guardar(conectar(), [(u, 0, "reinfo_vigentes", v) for u, v in out.items()], "MINEM, REINFO")
    print(f"{sum(out.values())} inscripciones vigentes en {len(out)} distritos; sin distrito reconocido: {fuera}")


if __name__ == "__main__":
    main()
