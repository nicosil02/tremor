"""CLI de prensa. Contrato: specs/002-prensa-egpp/contracts/cli.md"""
import argparse
import csv
import sys
from datetime import date

from tremor.db import DATOS, conectar
from tremor.prensa import codificar as cod, eventos, recolectar as rec


def exportar(con):
    d = DATOS / "exportes"; d.mkdir(parents=True, exist_ok=True)
    consultas = {
        "eventos_prensa.csv": """SELECT e.*, group_concat(n.enlace, ' ') AS enlaces, group_concat(n.medio, '; ') AS medios
            FROM evento_prensa e JOIN evento_nota en ON en.evento_id = e.id JOIN nota n ON n.id = en.nota_id GROUP BY e.id""",
        "notas.csv": """SELECT n.id, n.medio, n.titular, n.publicado, n.enlace, n.filtro, c.es_protesta, c.estado,
            c.fecha_evento, c.ubigeo, c.accion, c.actor, c.reclamo, c.empresa, c.operacion
            FROM nota n LEFT JOIN codificacion c ON c.nota_id = n.id AND c.version = '%s'""" % cod.VERSION,
    }
    for nombre, q in consultas.items():
        cur = con.execute(q)
        with open(d / nombre, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f); w.writerow([c[0] for c in cur.description]); w.writerows(cur)
    print(f"Exportado: {', '.join(consultas)} en datos/exportes/")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m tremor.prensa")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("recolectar"); r.add_argument("--desde", type=date.fromisoformat); r.add_argument("--hasta", type=date.fromisoformat)
    c = sub.add_parser("codificar"); c.add_argument("--max-solicitudes", type=int, default=200)
    sub.add_parser("ampliar")
    sub.add_parser("agrupar")
    v = sub.add_parser("validar"); v.add_argument("--mes", required=True)
    sub.add_parser("exportar")
    sub.add_parser("todo")
    a = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")
    con = conectar()
    if a.cmd in ("recolectar", "todo"):
        nuevas, vistas = rec.recolectar(con, getattr(a, "desde", None), getattr(a, "hasta", None))
        print(f"Prensa: {vistas} notas vistas, {nuevas} nuevas.")
    if a.cmd in ("ampliar", "todo"):
        from tremor.prensa.ampliar import ampliar
        vistas, hechas = ampliar(con, cod.VERSION)
        print(f"Ampliadas {hechas} de {vistas} protestas sin lugar (lead del medio).")
    if a.cmd in ("codificar", "todo"):
        s, n, falta = cod.codificar(con, getattr(a, "max_solicitudes", 200))
        print(f"Codificadas {n} notas en {s} solicitudes." + (" Quedan pendientes." if falta else ""))
    if a.cmd in ("agrupar", "todo"):
        print(f"Eventos: {eventos.agrupar(con)}.")
    if a.cmd in ("exportar", "todo"):
        exportar(con)
    if a.cmd == "validar":
        print(f"Acciones de la Defensoría ubicadas: {eventos.ubicar_defensoria(con)} nuevas.")
        print(eventos.validar(con, a.mes))
    return 0


if __name__ == "__main__":
    sys.exit(main())
