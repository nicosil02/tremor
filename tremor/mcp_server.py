"""Servidor MCP de Tremor: un asistente (Claude, por ejemplo) consulta la base y la Consulta Amigable del MEF.

`python -m tremor.mcp_server` (stdio). Registrado en `.mcp.json` del repo.
"""
import sqlite3

from mcp.server.mcpserver import MCPServer

from tremor import territorio
from tremor.db import RUTA_DB
from tremor.lugares import catalogo, nombre, norm

mcp = MCPServer("tremor", instructions=(
    "Conflictos sociales en el Perú por distrito (ubigeo INEI): historia de protestas de la EGPP PUCP (1980-2025), "
    "acciones de protesta de la Defensoría, protestas en la prensa (incluidas las anunciadas), bloqueos de la SUTRAN, "
    "presupuesto municipal del MEF, pobreza departamental de la ENAHO, y precios y producción minera del BCRP. "
    "Primero ubica el lugar con buscar_lugar y usa su ubigeo. Cita la fuente de cada cifra; para el MEF, la URL que "
    "devuelve consulta_amigable."))


def _sql(q, args=()):
    con = sqlite3.connect(f"file:{RUTA_DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in con.execute(q, args)]
    finally:
        con.close()


@mcp.tool()
def buscar_lugar(texto: str, limite: int = 10) -> list[dict]:
    """Distritos, provincias o departamentos cuyo nombre contiene el texto, con su ubigeo (sin tildes ni mayúsculas)."""
    t, nombres = norm(texto), catalogo()[3]
    salida = [{"ubigeo": u, "nombre": n, "nivel": {2: "departamento", 4: "provincia", 6: "distrito"}[len(u)],
               "en": " / ".join(x for x in (nombres.get(u[:2]), nombres.get(u[:4])) if x and len(u) > 2)}
              for u, n in nombres.items() if t in norm(n)]
    return sorted(salida, key=lambda x: (norm(x["nombre"]) != t, len(x["ubigeo"])))[:limite]


@mcp.tool()
def perfil_distrito(ubigeo: str) -> dict:
    """Todo lo que Tremor sabe de un distrito: perfil histórico de la EGPP, últimas acciones de protesta de la
    Defensoría y eventos de prensa en su provincia, alertas viales de la SUTRAN y canon municipal por año."""
    prov = ubigeo[:4]
    return {
        "lugar": " / ".join(x for x in (nombre(ubigeo[:2]), nombre(prov), nombre(ubigeo)) if x),
        "egpp": _sql("SELECT * FROM perfil_distrito WHERE ubigeo = ?", (ubigeo,)),
        "defensoria_ultimas_acciones": _sql(
            "SELECT reporte_num, fecha, medida, actores, lugar, demanda, ubigeo FROM accion_protesta "
            "WHERE ubigeo LIKE ? ORDER BY reporte_num DESC, n LIMIT 15", (prov + "%",)),
        "prensa_eventos": _sql("SELECT * FROM evento_prensa WHERE ubigeo LIKE ? ORDER BY fecha_evento DESC LIMIT 15",
                               (prov + "%",)),
        "sutran_alertas": _sql("SELECT codigo, motivo, submotivo, estado_via, titulo, descripcion, fecha_evento, "
                               "visto_ultimo FROM sutran_alerta WHERE ubigeo LIKE ? ORDER BY fecha_evento DESC LIMIT 15",
                               (prov + "%",)),
        "mef_canon": _sql("SELECT anio, municipalidad, devengado_total, devengado_canon FROM mef_municipal "
                          "WHERE ubigeo = ? ORDER BY anio", (ubigeo,)),
        "enaho_pobreza_departamento": _sql("SELECT anio, pobreza, pobreza_extrema FROM enaho_departamento "
                                           "WHERE ccdd = ? ORDER BY anio", (ubigeo[:2],)),
        "bcrp_produccion_minera_departamento": _mineria(ubigeo[:2]),
        "fuentes": "EGPP PUCP (Arce 2024; actualización dic. 2025); Defensoría del Pueblo, reportes mensuales; "
                   "prensa (enlaces en eventos_prensa.csv); SUTRAN alertasviales.sutran.gob.pe; MEF Consulta Amigable; "
                   "INEI ENAHO módulo 34 (pobreza monetaria, % de personas); BCRP series RD129xx (producción minera "
                   "por departamento).",
    }


def _mineria(ccdd):
    """Producción minera anual del departamento por metal: las series del BCRP se llaman 'Cobre - Apurimac (tm.f)'."""
    depto = norm(nombre(ccdd))
    filas = _sql("SELECT nombre, substr(periodo, 1, 4) AS anio, SUM(valor) AS produccion, COUNT(*) AS meses "
                 "FROM bcrp_mensual WHERE serie LIKE 'RD%' GROUP BY serie, anio ORDER BY nombre, anio")
    return [f for f in filas if norm(f["nombre"].split(" - ")[1].split(" (")[0]) == depto]


@mcp.tool()
def serie_bcrp(texto: str, desde: str = "2020-01", hasta: str = "2100-12") -> list[dict]:
    """Series mensuales del BCRP guardadas en Tremor cuyo nombre contiene el texto: precios del cobre, el oro y el
    petróleo ("Cobre - LME", "Oro - LME", "WTI") y producción minera por departamento ("Oro - Cajamarca").
    Periodos "AAAA-MM". Cita el código de la serie."""
    t = norm(texto)
    codigos = {r["serie"]: r["nombre"] for r in _sql("SELECT DISTINCT serie, nombre FROM bcrp_mensual")
               if t in norm(r["nombre"])}
    return [{"serie": c, "nombre": n, "datos": _sql("SELECT periodo, valor FROM bcrp_mensual WHERE serie = ? AND "
                                                     "periodo BETWEEN ? AND ? ORDER BY periodo", (c, desde, hasta)),
             "fuente": f"https://estadisticas.bcrp.gob.pe/estadisticas/series/mensuales/resultados/{c}/html"}
            for c, n in list(codigos.items())[:5]]


@mcp.tool()
def ranking(tipo: str = "socioambiental", n: int = 15, sin_capitales: bool = True) -> list[dict]:
    """Distritos con más protestas en la EGPP. tipo: "socioambiental", "laboral_minero" o "todos". Sin capitales
    por defecto: cuando la EGPP no sabe el distrito codifica la capital, que entonces queda inflada."""
    col = {"socioambiental": "socioambiental", "laboral_minero": "laboral_minero", "todos": "eventos"}[tipo]
    filtro = "WHERE capital_por_defecto = 0" if sin_capitales else ""
    return _sql(f"SELECT ubigeo, region, provincia, distrito, {col} AS protestas, operaciones, top_subreclamos "
                f"FROM perfil_distrito {filtro} ORDER BY {col} DESC LIMIT ?", (n,))


@mcp.tool()
def consulta_amigable(desglose: str, anio: int, filtros: dict[str, str] | None = None, buscar: str | None = None,
                      limite: int = 30) -> dict:
    """Presupuesto público del Perú (Consulta Amigable del MEF, desde 2012, en soles): PIA, PIM, devengado y avance %.
    desglose y llaves de filtros: nivel (E nacional, R regional, M local), sector, pliego, ejecutora, municipalidad,
    funcion, fuente, rubro (18 = canon, sobrecanon y regalías), departamento, mes, generica, categoria_presupuestal,
    producto_proyecto, division_funcional. El valor de un filtro es el «codigo» de una fila anterior; para una
    municipalidad también vale su ubigeo de 6 dígitos. Ejemplo: desglose="rubro", filtros={"nivel": "M",
    "municipalidad": "030506"} = el gasto de Challhuahuacho por fuente."""
    filtros = dict(filtros or {})
    if len(filtros.get("municipalidad", "")) == 6:  # ubigeo → código de la ejecutora
        _, munis = territorio.consulta("municipalidad", {"nivel": "M"}, anio)
        filtros["municipalidad"] = next(m["codigo"] for m in munis if m["nombre"].startswith(filtros["municipalidad"]))
    url, filas = territorio.consulta(desglose, filtros, anio)
    if buscar:
        filas = [f for f in filas if norm(buscar) in norm(f["nombre"])]
    filas = sorted(filas, key=lambda f: f["pim"], reverse=True)
    return {"anio": anio, "filas_total": len(filas), "filas": filas[:limite], "fuente": url}


if __name__ == "__main__":
    mcp.run()
