"""Línea de comandos del recolector. Contrato: specs/001-recolector-defensoria/contracts/cli.md"""
import argparse
import sys

from tremor.db import conectar
from tremor.defensoria import catalogo, validar as val


def descubrir(con, completo):
    nuevos = catalogo.descubrir(con, completo=completo)
    rescatados = catalogo.buscar_en_wayback(con)
    print(f"Listado: {nuevos} documentos nuevos. Wayback: {rescatados} rescatados.")
    return 0


def descargar(con):
    ok, errores = catalogo.descargar(con)
    print(f"Descargados: {ok}. Con error: {errores}.")
    return 1 if errores else 0


def identificar(con):
    r = catalogo.identificar(con)
    print(f"Portadas leídas: {r['leidos']}. Número distinto al del título: {len(r['discrepancias'])}.")
    for url, pista, real in r["discrepancias"]:
        print(f"  {url.rsplit('/', 1)[-1]}: título {pista}, portada {real}")
    return 0


def extraer(con, num=None):
    if num is not None:  # reprocesar un reporte: se borra lo suyo y se vuelve a leer
        for tabla, col in [("caso_mes", "reporte_num"), ("seccion", "reporte_num"), ("accion_protesta", "reporte_num"),
                           ("victimas", "reporte_num"), ("reporte", "num")]:
            con.execute(f"DELETE FROM {tabla} WHERE {col} = ?", (num,))
    cuenta = val.validar(con, desde=num or 1)
    print("Reportes extraídos: " + (", ".join(f"{k}: {v}" for k, v in cuenta.items()) or "0 nuevos"))
    return 0


def validar(con):
    print("Validación contra los totales de cada reporte:")
    for e, n in con.execute("SELECT estado, COUNT(*) FROM reporte GROUP BY estado ORDER BY estado"):
        print(f"  {e}: {n}")
    for r in con.execute("SELECT num, estado, detalle_validacion FROM reporte"
                         " WHERE estado NOT IN ('valido') ORDER BY num"):
        print(f"  n.° {r[0]} {r[1]}: {r[2]}")
    return 0


def exportar(con):
    val.exportar(con)
    print(f"CSV en {val.EXPORTES}")
    return 0


def estado(con):
    q = lambda sql: con.execute(sql).fetchone()[0]
    nums = catalogo.numeros_conocidos(con)
    falt = catalogo.faltantes(con)
    print(f"Reportes en catálogo: {len(nums)} de {max(nums, default=0)}"
          + (f"  (faltan {len(falt)}: {', '.join(map(str, falt))})" if falt else ""))
    print(f"Documentos: {q('SELECT COUNT(*) FROM documento')}"
          f"   Descargados: {q('SELECT COUNT(*) FROM documento WHERE huella IS NOT NULL')}"
          f"   Con error: {q('SELECT COUNT(*) FROM documento WHERE error IS NOT NULL')}")
    print("Por fuente: " + ", ".join(f"{f}: {n}" for f, n in
          con.execute("SELECT fuente, COUNT(*) FROM documento GROUP BY fuente")))
    return 0


def base_abierta(con):
    """Desde el n.° 271 (HTML) las acciones de protesta no vienen en el reporte sino en una hoja de Google enlazada
    ("Abrir detalle"). Se lee para los reportes HTML que aún no tienen acciones."""
    import io
    import re
    import pandas as pd
    from tremor.prensa.eventos import ubicar_defensoria
    pendientes = con.execute("SELECT r.num, d.url FROM reporte r JOIN documento d ON d.huella = r.huella "
                             "WHERE d.formato = 'html' AND NOT EXISTS (SELECT 1 FROM accion_protesta a "
                             "WHERE a.reporte_num = r.num)").fetchall()
    for num, url in pendientes:
        m = re.search(r"docs\.google\.com/spreadsheets/d/([\w-]+)", catalogo._get(url).text)
        if not m:
            print(f"  n.° {num}: sin enlace a la base abierta")
            continue
        x = pd.read_excel(io.BytesIO(catalogo._get(
            f"https://docs.google.com/spreadsheets/d/{m[1]}/export?format=xlsx").content), sheet_name=0)
        x = x.rename(columns=str.strip).dropna(subset=["Medida"])
        con.executemany("INSERT INTO accion_protesta (reporte_num, n, fecha, medida, actores, lugar, demanda) "
                        "VALUES (?,?,?,?,?,?,?)",
                        [(num, k, str(r.Fecha)[:10], r.Medida, r.Actores, r["Ubicación"], r.Demandas)
                         for k, (_, r) in enumerate(x.iterrows(), 1)])
        print(f"  n.° {num}: {len(x)} acciones de la base abierta")
    con.commit()
    if pendientes:
        ubicar_defensoria(con)
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m tremor.defensoria")
    sub = p.add_subparsers(dest="comando", required=True)
    d = sub.add_parser("descubrir", help="listado oficial y Wayback para los faltantes")
    d.add_argument("--completo", action="store_true", help="recorrer las 120 páginas")
    sub.add_parser("descargar", help="bajar lo que no tiene huella")
    sub.add_parser("identificar", help="leer número y mes de cada portada")
    e = sub.add_parser("extraer", help="secciones, totales y fichas de los reportes nuevos")
    e.add_argument("--num", type=int, help="reprocesar solo este reporte")
    sub.add_parser("validar", help="resultado de comparar cada reporte con sus totales")
    sub.add_parser("abierta", help="acciones de protesta de la hoja enlazada en los reportes HTML (n.° 271+)")
    sub.add_parser("exportar", help="CSV en datos/exportes/")
    sub.add_parser("estado", help="resumen del catálogo")
    t = sub.add_parser("todo", help="todos los pasos en orden")
    t.add_argument("--completo", action="store_true")
    a = p.parse_args(argv)

    con = conectar()
    if a.comando == "descubrir":
        return descubrir(con, a.completo)
    if a.comando == "descargar":
        return descargar(con)
    if a.comando == "identificar":
        return identificar(con)
    if a.comando == "extraer":
        return extraer(con, a.num)
    if a.comando == "validar":
        return validar(con)
    if a.comando == "abierta":
        return base_abierta(con)
    if a.comando == "exportar":
        return exportar(con)
    if a.comando == "estado":
        return estado(con)
    if a.comando == "todo":
        codigo = descubrir(con, a.completo) | descargar(con) | identificar(con) | extraer(con) | base_abierta(con)
        exportar(con)
        estado(con)
        return codigo


if __name__ == "__main__":
    sys.exit(main())
