"""Qué dicen los medios de un conflicto que la Defensoría registra sin descripción: quién reclama, por qué y a quién.

La Defensoría a veces publica solo el nombre del caso ("Comunidad Campesina de Maure – Penal de Challapalca / INPE").
Aquí se busca en Google News el nombre y el lugar del último año, se guardan las notas (tabla `nota`, consulta
`caso:<id>`) y el LLM resume en una oración, con las notas que usó como fuente. Queda en `caso_contexto`, que lee
la página y puede leer el modelo. `python -m tremor.contexto`
"""
import json
import re
import sys
import time
from datetime import date, timedelta
from urllib.parse import quote

import requests

from tremor.db import conectar
from tremor.lugares import norm

RESUMEN = ("Te doy el nombre de un conflicto social del Perú registrado por la Defensoría del Pueblo, su lugar y notas "
           "de prensa numeradas. Usa solo las notas que hablan de ESTE conflicto. Di en UNA oración formal de máximo 30 "
           "palabras quién reclama (por rol o comunidad, nunca nombres de personas), qué pide y a quién. Si ninguna nota "
           'sirve, resumen = null. Responde JSON {"resumen": "<oración>" o null, "notas": [<números usados>]}.')
VACIAS = {"de", "del", "la", "las", "los", "el", "y", "en", "por", "con", "para", "contra", "sobre", "antes", "ex",
          "comunidad", "campesina", "nativa", "empresa", "pobladores", "frente", "defensa", "conflicto", "servicio"}


def claves(nombre: str) -> list[str]:
    """Las palabras que identifican el caso: sin siglas de una letra, artículos ni años."""
    ws = re.findall(r"[A-Za-zÁÉÍÓÚÑáéíóúñ]{3,}", nombre or "")
    return [w for w in ws if norm(w) not in VACIAS][:5]


def casos(con, pausa=1.5) -> int:
    from tremor.llm import chat_json, SinCuota, RespuestaInvalida
    from tremor.prensa.recolectar import GNEWS, UA, parsear, _guardar
    con.execute("""CREATE TABLE IF NOT EXISTS caso_contexto (caso_id INTEGER PRIMARY KEY, resumen TEXT, fuentes TEXT,
                   actualizado TEXT NOT NULL)""")
    filas = con.execute("""SELECT c.id, c.nombre, c.ubigeo FROM caso c JOIN caso_mes cm ON cm.caso_id = c.id
                           WHERE cm.reporte_num = (SELECT MAX(num) FROM reporte) AND cm.estado IN ('activo', 'latente')
                             AND trim(coalesce(cm.descripcion, c.descripcion, '')) IN ('', c.nombre)
                             AND c.id NOT IN (SELECT caso_id FROM caso_contexto WHERE resumen IS NOT NULL
                                              AND actualizado >= date('now', '-30 day'))""").fetchall()
    desde, hechos = date.today() - timedelta(365), 0
    for id_, nombre, ubigeo in filas:
        ks = claves(nombre)
        if not ks:
            continue
        q = " ".join(ks) + f" after:{desde}"
        try:
            r = requests.get(GNEWS.format(q=quote(q)), timeout=30, headers=UA); r.raise_for_status()
            notas = [n for n in parsear(r.text) if sum(norm(k) in norm(n["titular"] + " " + n["resumen"]) for k in ks) >= 2][:10]
            _guardar(con, notas, f"caso:{id_}", None)
        except requests.RequestException as e:
            print(f"  {nombre[:40]}: {e.__class__.__name__}")
            continue
        finally:
            time.sleep(pausa)
        if not notas:
            con.execute("INSERT OR REPLACE INTO caso_contexto VALUES (?, NULL, '[]', datetime('now'))", (id_,))
            continue
        texto = f"Conflicto: {nombre}. Ubigeo {ubigeo}.\n\n" + "\n".join(
            f"[{i}] {n['medio']} ({(n['publicado'] or '')[:10]}): {n['titular']}. {n['resumen'][:300]}" for i, n in enumerate(notas))
        try:
            out = chat_json(con, RESUMEN, texto, "caso-contexto-1")
        except SinCuota:
            break
        except RespuestaInvalida:
            continue
        usadas = [notas[i] for i in out.get("notas") or [] if isinstance(i, int) and 0 <= i < len(notas)]
        fuentes = [{"medio": n["medio"], "titular": n["titular"], "enlace": n["enlace"]} for n in usadas[:3]]
        con.execute("INSERT OR REPLACE INTO caso_contexto VALUES (?, ?, ?, datetime('now'))",
                    (id_, out.get("resumen"), json.dumps(fuentes, ensure_ascii=False)))
        hechos += bool(out.get("resumen"))
        con.commit()
    con.commit()
    return hechos


VINCULO = ("Para cada conflicto social del Perú (ficha de la Defensoría del Pueblo) extrae: quien_reclama (tipo de "
           "actor: comunidad campesina, comunidad nativa, pobladores, trabajadores, agricultores, frente de defensa, "
           "gobierno local u otro; nunca nombres de personas), contra_empresa (razón social o nombre de la empresa "
           "privada o estatal a la que se reclama, o null), unidad (mina, proyecto, lote, planta o central nombrada, o "
           "null), estado (entidades públicas involucradas, máximo 3), tema (una de: agua, contaminacion, empleo, "
           "canon, tierras, acuerdos, vias, mineria_ilegal, consulta_previa, servicios, laboral, otro). "
           'Responde JSON {"r": [{"i": <id>, "quien_reclama": ..., "contra_empresa": ..., "unidad": ..., '
           '"estado": [...], "tema": ...}]}.')


GENERICAS = {"compania", "cia", "sociedad", "minera", "minero", "mineros", "empresa", "sac", "saa", "srl", "eirl", "del",
             "peru", "sucursal", "mining", "resources", "gold", "corporation", "holding", "the", "los", "las", "san",
             "unidad", "proyecto", "mina", "petrolera", "energia", "anonima", "cerrada", "abierta", "limitada",
             "regional", "hospital", "central", "planta", "norte", "sur", "nacional", "municipal"}


def emparejar(ops, empresa, unidad):
    """La operación de la base que corresponde a la empresa y unidad nombradas en el conflicto (por nombre).
    Sin empresa no hay operación: un hospital o un municipio "regional" no es la unidad Regional - Atico."""
    if not empresa:
        return None, None, None
    ne, nu = norm(empresa or ""), norm(unidad or "")
    raiz = lambda s: [w for w in s.replace(".", " ").split() if len(w) > 2 and w not in GENERICAS]
    re_, ru = set(raiz(ne)), set(raiz(nu))
    mejor = None
    for e, u, ub in ops:
        pe = len(re_ & set(raiz(norm(e)))) if re_ else 0
        pu = len(ru & set(raiz(norm(u or "")))) if ru else 0
        p = pe + 2 * pu
        if (pu or pe >= 1) and (not mejor or p > mejor[0]):
            mejor = (p, e, u, ub)
    return mejor[1:] if mejor else (None, None, None)


def vinculos(con) -> int:
    """Con quién es cada conflicto vigente: empresa y unidad (enlazadas a la tabla operacion), quién reclama, qué
    entidades del Estado intervienen y el tema. Tabla caso_vinculo; la usan la página y el modelo."""
    from tremor.llm import chat_json, SinCuota, RespuestaInvalida
    con.execute("""CREATE TABLE IF NOT EXISTS caso_vinculo (caso_id INTEGER PRIMARY KEY, quien_reclama TEXT,
                   contra_empresa TEXT, unidad TEXT, estado TEXT, tema TEXT, empresa_op TEXT, unidad_op TEXT,
                   ubigeo_op TEXT, actualizado TEXT NOT NULL)""")
    ops = con.execute("SELECT empresa, unidad, ubigeo FROM operacion").fetchall()
    filas = con.execute("""SELECT c.id, c.nombre, coalesce(cm.descripcion, c.descripcion, ''), coalesce(cm.actores_primarios, ''),
                                  coalesce(x.resumen, '')
                           FROM caso c JOIN caso_mes cm ON cm.caso_id = c.id LEFT JOIN caso_contexto x ON x.caso_id = c.id
                           WHERE cm.reporte_num = (SELECT MAX(num) FROM reporte) AND cm.estado IN ('activo', 'latente')""").fetchall()
    hechos = 0
    for k in range(0, len(filas), 4):
        lote = "\n".join(f"[{i}] {n}. {d[:700]} Actores: {a[:300]}. {x}" for i, n, d, a, x in filas[k:k + 4])
        try:
            out = chat_json(con, VINCULO, lote, "caso-vinculo-1").get("r", [])
        except SinCuota:
            break
        except (RespuestaInvalida, ValueError):
            continue
        for v in out:
            try:
                i = int(v["i"])
            except (KeyError, TypeError, ValueError):
                continue
            e, u, ub = emparejar(ops, v.get("contra_empresa"), v.get("unidad"))
            con.execute("INSERT OR REPLACE INTO caso_vinculo VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))",
                        (i, v.get("quien_reclama"), v.get("contra_empresa"), v.get("unidad"),
                         json.dumps(v.get("estado") or [], ensure_ascii=False), v.get("tema"), e, u, ub))
            hechos += 1
        con.commit()
    return hechos


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    assert claves("Comunidad Campesina de Maure – Penal de Challapalca / INPE")[:3] == ["Maure", "Penal", "Challapalca"]
    assert emparejar([("SOUTHERN PERU", "Regional - Atico", "x")], None, "Hospital Regional II-2 JAMO") == (None, None, None)
    assert emparejar([("ARUNTANI S.A.C.", "Florencia - Tucari", "x")], "Aruntani", "Tucari")[0] == "ARUNTANI S.A.C."
    print(f"Contexto de prensa para {casos(conectar())} casos sin descripción.")
    print(f"Vínculos de {vinculos(conectar())} conflictos vigentes.")
