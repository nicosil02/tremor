"""Línea de comandos del recolector. Contrato: specs/001-recolector-defensoria/contracts/cli.md"""
import argparse
import sys

from tremor.db import ahora, conectar
from tremor.defensoria import catalogo


def _registrar(con, paso, inicio, nuevos=0, errores=0, detalle=""):
    con.execute(
        "INSERT INTO corrida (paso, inicio, fin, nuevos, errores, detalle) VALUES (?, ?, ?, ?, ?, ?)",
        (paso, inicio, ahora(), nuevos, errores, detalle),
    )
    con.commit()


def descubrir(con, completo):
    inicio = ahora()
    nuevos = catalogo.descubrir(con, completo=completo)
    rescatados = catalogo.buscar_en_wayback(con)
    print(f"Listado: {nuevos} documentos nuevos. Wayback: {rescatados} rescatados.")
    _registrar(con, "descubrir", inicio, nuevos + rescatados)
    return 0


def descargar(con):
    inicio = ahora()
    ok, errores = catalogo.descargar(con)
    print(f"Descargados: {ok}. Con error: {errores}.")
    _registrar(con, "descargar", inicio, ok, errores)
    return 1 if errores else 0


def identificar(con):
    inicio = ahora()
    r = catalogo.identificar(con)
    print(f"Portadas leídas: {r['leidos']}. Número distinto al del título: {len(r['discrepancias'])}.")
    for url, pista, real in r["discrepancias"]:
        print(f"  {url.rsplit('/', 1)[-1]}: título {pista}, portada {real}")
    _registrar(con, "identificar", inicio, r["leidos"], 0, repr(r["discrepancias"]))
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


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m tremor.defensoria")
    sub = p.add_subparsers(dest="comando", required=True)
    d = sub.add_parser("descubrir", help="listado oficial y Wayback para los faltantes")
    d.add_argument("--completo", action="store_true", help="recorrer las 120 páginas")
    sub.add_parser("descargar", help="bajar lo que no tiene huella")
    sub.add_parser("identificar", help="leer número y mes de cada portada")
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
    if a.comando == "estado":
        return estado(con)
    if a.comando == "todo":
        codigo = descubrir(con, a.completo) | descargar(con) | identificar(con)
        estado(con)
        return codigo


if __name__ == "__main__":
    sys.exit(main())
