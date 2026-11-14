"""Vigilante: el carril rápido. Una vuelta cada 2 minutos con lo que cambia en minutos (SUTRAN y prensa), lee solo las
notas nuevas, reagrupa y manda los avisos de Telegram. Es el único que avisa: defensoria.yml y radio.yml (carril lento)
publican la base en la rama `datos` y él la vuelve a bajar cuando cambia.

Su memoria es la rama `vivo`: `vivo.db.gz` (notas y lecturas de los últimos días y todos los avisos enviados) y el
`web.json` que lee la página. Con eso, si muere, el siguiente retoma sin repetir avisos, y el carril lento no vuelve a
gastar cupo del LLM en lo que él ya leyó. Corre igual en GitHub (vigia.yml) que en cualquier Linux con git y las claves.

    python -m tremor.vigia --minutos 320     # el bucle
    python -m tremor.vigia traer             # el carril lento: sumar a la base lo que vio el vigilante
"""
import gzip
import json
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone

from tremor.db import DATOS, conectar

DIAS = "date('now', '-2 days')"
ESTADO = {"nota": f"descargado >= {DIAS}", "codificacion": f"nota_id IN (SELECT id FROM nota WHERE descargado >= {DIAS})",
          "llm_cache": f"creado >= {DIAS}", "aviso_enviado": "1"}
VIVO = DATOS / "vivo.db"


def guardar(con, ruta=VIVO):
    ruta.unlink(missing_ok=True)
    con.execute("ATTACH ? AS v", (str(ruta),))
    for t, donde in ESTADO.items():
        con.execute(f"CREATE TABLE v.{t} AS SELECT * FROM {t} WHERE {donde}")
    con.commit(); con.execute("DETACH v")


def traer(con, ruta=VIVO):
    """Suma a la base lo guardado; lo que ya está, se queda como está. Devuelve las filas nuevas."""
    con.execute("CREATE TABLE IF NOT EXISTS aviso_enviado (clave TEXT, empresa TEXT, enviado TEXT, PRIMARY KEY (clave, empresa))")
    con.execute("ATTACH ? AS v", (str(ruta),))
    # ponytail: SELECT * supone las mismas columnas en las dos bases; si una tabla gana una columna, falla hasta el
    # siguiente relevo del vigilante (5,5 h como mucho)
    # la nota que el otro carril amplió (más texto) o dio por vieja gana: se lleva su texto y sus lecturas. Sin esto,
    # lo que el vigilante bajaba del medio se perdía al recargar la base de `datos`, que traía la nota solo con titular
    mejores = """SELECT v.id FROM v.nota v JOIN nota n ON n.id = v.id WHERE length(coalesce(v.resumen, '')) >
                 length(coalesce(n.resumen, '')) OR (v.filtro = 'vieja' AND n.filtro IS NOT 'vieja')"""
    con.execute(f"DELETE FROM codificacion WHERE nota_id IN ({mejores})")
    m = con.execute(f"""UPDATE nota SET (resumen, enlace, publicado, filtro) =
        (SELECT resumen, enlace, publicado, filtro FROM v.nota v WHERE v.id = nota.id) WHERE id IN ({mejores})""").rowcount
    n = m + sum(con.execute(f"INSERT OR IGNORE INTO {t} SELECT * FROM v.{t}").rowcount for t in ESTADO)
    con.commit(); con.execute("DETACH v")
    return n


def git(*a, entrada=None):
    return subprocess.run(["git", *a], input=entrada, capture_output=True, check=True).stdout


def bajar_vivo():
    """vivo.db de la rama `vivo`; False si la rama todavía no existe."""
    if subprocess.run(["git", "fetch", "-q", "--depth", "1", "origin", "vivo"], capture_output=True).returncode:
        return False
    VIVO.write_bytes(gzip.decompress(git("show", "FETCH_HEAD:vivo.db.gz")))
    return True


def base():
    """La base publicada por el carril lento más la memoria del vigilante. Devuelve el commit de `datos` que bajó."""
    git("fetch", "-q", "--depth", "1", "origin", "datos")
    commit = git("rev-parse", "FETCH_HEAD").decode().strip()
    (DATOS / "exportes").mkdir(parents=True, exist_ok=True)
    for f in git("ls-tree", "--name-only", commit).decode().split():
        if f.endswith((".csv", ".geojson")):  # la alerta del modelo y los límites, que piden web y avisos
            (DATOS / ("exportes" if f.endswith(".csv") else "") / f).write_bytes(git("show", f"{commit}:{f}"))
    (DATOS / "tremor.db").write_bytes(gzip.decompress(git("show", f"{commit}:tremor.db.gz")))
    if bajar_vivo():
        con = conectar(); print(f"  base {commit[:7]}; del vigilante anterior: {traer(con)} filas", flush=True); con.close()
    return commit


def publicar(ultimo):
    """Un solo commit sin historia en la rama `vivo`, y solo si algo cambió. Devuelve el árbol publicado."""
    web = DATOS / "exportes" / "web.json"
    d = json.loads(web.read_text(encoding="utf-8"))
    d["vivo"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M")[:15] + "0:00"  # sello cada 10 min: la página sabe que sigue vivo
    web.write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    con = conectar(); guardar(con); con.close()
    gz = DATOS / "vivo.db.gz"
    gz.write_bytes(gzip.compress(VIVO.read_bytes(), mtime=0))
    arbol = git("mktree", entrada=b"".join(b"100644 blob " + git("hash-object", "-w", str(p)).strip() + b"\t" + p.name.encode() + b"\n"
                                           for p in (gz, web))).strip()
    if arbol != ultimo:
        git("push", "-qf", "origin", git("commit-tree", arbol, "-m", "Vivo").strip().decode() + ":refs/heads/vivo")
    return arbol


def latido(con, enviar, ahora_=None):
    """Una vez al día, desde las 8:00 de Lima: un mensaje de que sigue vigilando, con lo hecho en 24 horas. Si un día no
    llega, el vigilante está caído. Queda en aviso_enviado (clave latido:fecha) para que el relevo no lo repita."""
    from tremor.avisos import CLIENTE
    from tremor.prensa.codificar import VERSION
    lima = (ahora_ or datetime.now(timezone.utc)) - timedelta(hours=5)
    clave = f"latido:{lima:%Y-%m-%d}"
    if lima.hour < 8 or con.execute("SELECT 1 FROM aviso_enviado WHERE clave = ?", (clave,)).fetchone():
        return False
    ayer = (datetime.now() - timedelta(days=1)).isoformat(timespec="seconds")  # como db.ahora(): hora de la máquina
    uno = lambda q, *a: con.execute(q, a).fetchone()[0]
    notas = uno("SELECT count(*) FROM nota WHERE descargado >= ?", ayer)
    cola = uno("""SELECT count(*) FROM nota n WHERE n.filtro IS NULL AND n.descargado >= ?
        AND NOT EXISTS (SELECT 1 FROM codificacion c WHERE c.nota_id = n.id AND c.version = ?)""", ayer, VERSION)
    avisos = uno("SELECT count(*) FROM aviso_enviado WHERE enviado >= ? AND clave NOT LIKE 'latido:%'", ayer)
    texto = (f"🟢 *Tremor sigue vigilando* · {CLIENTE}\n\nÚltimas 24 horas: {notas} notas recogidas, {cola} en cola de lectura, "
             f"{avisos} avisos enviados.")
    if enviar(texto):
        con.execute("INSERT OR IGNORE INTO aviso_enviado VALUES (?, ?, ?)", (clave, CLIENTE, datetime.now().isoformat(timespec="seconds")))
        con.commit()
        return True
    return False


def paso(*args):
    """Un paso que falla (un medio caído, el LLM sin cupo) no tumba al vigilante: se anota y la vuelta sigue."""
    r = subprocess.run([sys.executable, "-m", *args], capture_output=True, text=True, encoding="utf-8", errors="replace")
    enviados = [x for x in r.stdout.splitlines() if "aviso enviado" in x]  # avisos imprime la clave de cada envío
    ult = [x for x in (r.stdout if r.returncode == 0 else r.stderr).strip().splitlines() if x not in enviados][-1:]
    print(f"  {' '.join(args)}: {'ERROR ' if r.returncode else ''}{ult[0][:150] if ult else ''}", *enviados, sep="\n", flush=True)


def vigilar(minutos, cada=120, reenviar=False):
    fin, n, datos, arbol = time.time() + minutos * 60, 0, None, None
    while time.time() < fin:
        t0 = time.time()
        try:
            if git("ls-remote", "origin", "refs/heads/datos").decode().split()[:1] != [datos]:
                datos = base()
            print(f"vuelta {n} {datetime.now(timezone.utc):%H:%M:%S}", flush=True)
            paso("tremor.sutran")
            paso("tremor.prensa", "recolectar", *([] if n % 8 == 0 else ["--rapido"]))  # Google News entero cada 8 vueltas
            # el texto del medio para las protestas que llegaron solo con titular (sin él no se avisa ni se sabe si la
            # nota es vieja); lo que se amplía se vuelve a leer en esta misma vuelta
            paso("tremor.prensa", "ampliar", "--limite", "6")
            # ponytail: 3 lotes por vuelta (~45 notas). Con 40, una tanda de 500 notas nuevas dejó la vuelta en 8 min y
            # los avisos esperando detrás; si el atraso crece, leer primero las notas de la zona del cliente
            paso("tremor.prensa", "codificar", "--max-solicitudes", "3")
            paso("tremor.prensa", "agrupar")
            paso("tremor.web")
            paso("tremor.avisos", *(["--reenviar"] if reenviar and n == 0 else []))
            from tremor.avisos import enviar
            con = conectar(); latido(con, enviar); con.close()
            arbol = publicar(arbol)
        except (subprocess.CalledProcessError, OSError) as e:  # GitHub no responde: la siguiente vuelta lo reintenta
            print(f"  vuelta fallida: {e}", flush=True)
            datos = None
        n += 1
        time.sleep(max(0, cada - (time.time() - t0)))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if "traer" in sys.argv:
        print(f"Del vigilante: {traer(conectar()) if bajar_vivo() else 0} filas nuevas.")
    else:
        vigilar(int(sys.argv[sys.argv.index("--minutos") + 1]) if "--minutos" in sys.argv else 320, reenviar="--reenviar" in sys.argv)
