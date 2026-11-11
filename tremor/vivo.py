"""Radio en tiempo real: escucha en continuo las radios de la zona y la ruta de una empresa, transcribe cada minuto apenas
termina de grabarse y, si al aire se anuncia o se informa una medida concreta (paro, bloqueo, toma, marcha), avisa al chat
ese mismo minuto con la frase literal. Cada minuto con voz queda guardado como nota de radio, igual que la grabación por
franjas, para que la corrida normal lo codifique y agrupe.

    python -m tremor.radio vivo --empresa Bateas                 # hasta Ctrl+C
    python -m tremor.radio vivo --empresa Bateas --minutos 10 --hilos 4
    python -m tremor.radio vivo --provincias 0405 0401 0407      # provincias a mano

Whisper small en GPU si hay CUDA (int8_float16), si no en CPU. Sin TELEGRAM_* en el entorno los avisos solo se imprimen."""
import json
import os
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

from tremor.db import DATOS, RAIZ, ahora, conectar
from tremor.prensa.codificar import MEDIDA, VERIFICAR_RADIO
from tremor.prensa.recolectar import LIMA
from tremor.radio import grabar, guardar, notas, radios, transcribir

NOMBRE = [("paro", "Paro"), ("bloque", "Bloqueo"), ("huelga", "Huelga"), ("toma", "Toma"), ("moviliza", "Movilización"),
          ("marcha", "Marcha"), ("plant", "Plantón"), ("enfrenta", "Enfrentamiento"), ("protest", "Protesta")]
REPETIR = timedelta(minutes=30)  # la misma medida en la misma radio no se avisa dos veces en media hora


def provincias_de(con, empresa):
    """Provincias de la zona de la empresa (unidades y vecinos) y de su ruta de salida (docs/cadena.json)."""
    from tremor.avisos import CADENA, EMPRESAS, zona
    ruta = DATOS / "exportes" / "web.json"
    web = json.load(open(ruta if ruta.exists() else RAIZ / "docs" / "web.json", encoding="utf-8"))
    ubs = set(zona(con, EMPRESAS[empresa][0], web["vecinos"]))
    ubs |= {u for t in CADENA.get(empresa, {}).get("tramos", []) for u in t["ubigeos"]}
    return sorted({u[:4] for u in ubs})


def emisoras(provincias):
    return [r for r in radios() if r["ubigeo_provincia"] in set(provincias) and "youtube.com" not in r["stream"]]


def medida(texto):
    m = MEDIDA.search(texto or "")
    return (next((n for k, n in NOMBRE if m.group(0).lower().startswith(k)), "Protesta"), m) if m else (None, None)


def procesar(con, radio, inicio, texto, empresa, memoria, enviar):
    """Guarda el minuto como notas de radio; si nombra una medida, el LLM la verifica y, si es concreta, avisa.
    memoria: {(medio, medida): hora del último aviso}. Devuelve los avisos enviados."""
    from tremor.llm import RespuestaInvalida, SinCuota, chat_json
    filas = notas(radio, inicio, texto)
    guardar(con, filas)
    avisos = []
    for f in filas:
        nombre, m = medida(f["resumen"])
        if f["filtro"] is not None or not m:  # sin medida con contexto, no gasta LLM
            continue
        if inicio - memoria.get((radio["medio"], nombre), inicio - REPETIR * 2) < REPETIR:
            continue
        txt = f["resumen"]
        cita = txt[max(0, m.start() - 150):m.end() + 150].strip()
        try:
            r = chat_json(con, VERIFICAR_RADIO, cita, "radio1")
        except (SinCuota, RespuestaInvalida) as e:
            print(f"  [LLM] {str(e)[:80]}", flush=True)
            continue
        if r.get("concreta") is not True:
            continue
        s = lambda k: r.get(k) if isinstance(r.get(k), str) and r.get(k) else None
        texto_aviso = (f"📻 *EN VIVO · {radio['medio']}, {inicio:%H:%M}*\n_{nombre}{' de ' + s('quienes') if s('quienes') else ''}_\n\n"
                       + (f"🗓 *Cuándo:* {s('cuando')}\n" if s("cuando") else "") + (f"📍 *Dónde:* {s('lugar')}\n" if s("lugar") else "")
                       + (f"⏱ *Duración:* {s('duracion')}\n" if s("duracion") else "")
                       + f"\n🎙 «{cita}»\n_Transcripción automática del minuto; puede tener errores._\n\n📡 Escuchar: {radio['stream']}")
        clave = f"vivo:{radio['medio']}:{inicio:%Y-%m-%dT%H:%M}"
        con.execute("CREATE TABLE IF NOT EXISTS aviso_enviado (clave TEXT, empresa TEXT, enviado TEXT, PRIMARY KEY (clave, empresa))")
        if con.execute("SELECT 1 FROM aviso_enviado WHERE clave = ? AND empresa = ?", (clave, empresa)).fetchone():
            continue
        enviar(texto_aviso)
        con.execute("INSERT OR IGNORE INTO aviso_enviado VALUES (?, ?, ?)", (clave, empresa, ahora()))
        con.commit()
        memoria[(radio["medio"], nombre)] = inicio
        avisos.append(texto_aviso)
    return avisos


def modelo_whisper():
    from faster_whisper import WhisperModel
    try:
        m = WhisperModel("small", device="cuda", compute_type="int8_float16")
        return m, "GPU"
    except Exception as e:  # sin CUDA utilizable: CPU
        print(f"  sin GPU ({str(e)[:60]}): Whisper en CPU", flush=True)
        return WhisperModel("small", device="cpu", compute_type="int8"), "CPU"


def vivo(empresa=None, provincias=None, minutos=None, hilos=4, segundos=60):
    from tremor.avisos import enviar
    con = conectar(hilos=True)  # los hilos escriben bajo el candado `bd`
    provincias = provincias or provincias_de(con, empresa)
    lista = emisoras(provincias)
    modelo, disp = modelo_whisper()
    print(f"En vivo: {len(lista)} radios en {len(provincias)} provincias, trozos de {segundos} s, {hilos} hilos, Whisper en {disp}"
          + (f"; rotando entre las radios ({hilos} a la vez)" if len(lista) > hilos else ""), flush=True)
    # ponytail: un solo modelo con candado; si la GPU aguanta, varios modelos a la vez
    candado, bd, memoria, fin = threading.Lock(), threading.Lock(), {}, time.time() + (minutos or 10**9) * 60
    cola, stats = list(lista), {"trozos": 0, "latencia": 0.0, "avisos": 0}

    def turno(i):
        with tempfile.TemporaryDirectory() as d:
            while time.time() < fin:
                with bd:
                    radio = cola.pop(0); cola.append(radio)  # rota: cada hilo toma la siguiente radio libre
                ruta, inicio = os.path.join(d, f"{i}.wav"), datetime.now(LIMA)
                if not grabar(radio["stream"], segundos, ruta):
                    print(f"  {radio['medio']}: sin audio", flush=True); continue
                t0 = time.time()
                with candado:
                    texto, _ = transcribir(modelo, ruta)
                with bd:
                    avisos = procesar(con, radio, inicio, texto, empresa or "-", memoria, enviar)
                    stats["trozos"] += 1; stats["latencia"] += time.time() - t0; stats["avisos"] += len(avisos)
                print(f"  {inicio:%H:%M} {radio['medio']}: {len(texto)} letras en {time.time() - t0:.1f} s"
                      + (f", {len(avisos)} AVISO" if avisos else ""), flush=True)

    try:
        with ThreadPoolExecutor(min(hilos, len(lista)) or 1) as ex:
            list(ex.map(turno, range(min(hilos, len(lista)))))
    except KeyboardInterrupt:
        fin = 0
    n = stats["trozos"] or 1
    print(f"Fin: {stats['trozos']} trozos, latencia media {stats['latencia'] / n:.1f} s del fin de la grabación al texto, "
          f"{stats['avisos']} avisos", flush=True)
    return stats
