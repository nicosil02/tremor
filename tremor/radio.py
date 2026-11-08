"""Radios regionales en vivo: graba el stream, transcribe con faster-whisper (local, sin cuota) y guarda cada
fragmento como una `nota`, para que el codificador de prensa (manual EGPP) detecte las protestas.

`python -m tremor.radio --minutos 20` (en GitHub Actions: .github/workflows/radio.yml, franjas de noticieros).
Como en Base_legislativa (congreso_live/live_transcribe.py): Whisper "small" en CPU int8, audio mono 16 kHz.
shortcut: solo castellano; el quechua y el aimara necesitan otro modelo (Omnilingual ASR), queda para el módulo 003."""
import argparse
import os
import subprocess
import sys
import tempfile
import wave
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from tremor.db import ahora, conectar
from tremor.prensa.recolectar import LIMA, filtro, id_nota

# (medio, departamento, stream): de la web de cada radio o de radio-browser.info; probados el 7 nov 2026.
RADIOS = [
    ("Pachamama Radio", "Puno", "https://servidor14.brlogic.com:8744/live"),
    ("Radio Sol de los Andes", "Puno", "https://cloudstream2036.conectarhosting.com/8036/stream"),
    ("Radio Onda Popular", "Puno", "https://dattavolt.com/8278/stream"),
    ("Radio Titanka", "Apurímac", "http://servistream.info:8482/stream"),
    ("Radio Cusco Legal", "Cusco", "https://stream-144.zeno.fm/ryrhxgus0wzuv"),
    ("Radio Intiraymi", "Cusco", "https://streamhotsperu.purosurfm.com:8150/intiraymi"),
    ("Radio Salkantay", "Cusco", "https://stream.radiosalkantaycusco.com/7662/stream"),
    ("Radio Yaraví", "Arequipa", "https://tupanel.info/stream/radioyaravi/stream"),
    ("Radio Metropolitana", "Arequipa", "https://maximacenterdata.com/8120/stream"),
    ("Radio Onda Popular Cajamarca", "Cajamarca", "https://envivo.top:8443/am"),
    ("Radio Bambamarca", "Cajamarca", "https://envivo.top:8443/lider"),
    ("Radio Nor Andina", "Cajamarca", "https://mediastreamm.com/8012/stream/1/"),
    ("Radio Loreto", "Loreto", "https://sp.oyotunstream.com/8006/stream"),
    ("Radio Milenium", "Amazonas", "https://sp.onliveperu.com/8102/stream"),
    ("RPT Radio", "Moquegua", "https://stream.zeno.fm/m2x1vzybpapvv"),
    ("Radio Andina Tarata", "Tacna", "http://sp.oyotunstream.com:8064/"),
]
SR = 16_000
TROZO = 1200  # caracteres por nota: un noticiero trae muchas noticias y el codificador espera una por nota


def grabar(url, segundos, ruta):
    ffmpeg = os.environ.get("FFMPEG_BIN", "ffmpeg")
    subprocess.run([ffmpeg, "-loglevel", "error", "-y", "-i", url, "-t", str(segundos), "-vn", "-ac", "1",
                    "-ar", str(SR), ruta], stdin=subprocess.DEVNULL, timeout=segundos + 120, check=False)
    return os.path.exists(ruta) and os.path.getsize(ruta) > SR * 2 * 10  # al menos 10 s de audio


def trozos(texto, n=TROZO):
    """Corta en frases hasta ~n caracteres."""
    salida, actual = [], ""
    for frase in texto.replace("? ", "?. ").replace("! ", "!. ").split(". "):
        if len(actual) + len(frase) > n and actual:
            salida.append(actual.strip()); actual = ""
        actual += frase + ". "
    return salida + ([actual.strip()] if actual.strip() else [])


def transcribir(modelo, ruta):
    import numpy as np
    with wave.open(ruta) as w:
        audio = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
    segmentos, _ = modelo.transcribe(audio, language="es", vad_filter=True)  # sin av: evita el choque de versiones
    return " ".join(s.text.strip() for s in segmentos)


def guardar(con, medio, dep, url, inicio, texto):
    nuevas = 0
    if len(texto) < 100:  # música o silencio
        return 0
    for i, t in enumerate(trozos(texto), 1):
        titular = f"{medio}, en vivo {inicio:%d/%m/%Y %H:%M} ({i})"
        cur = con.execute("INSERT OR IGNORE INTO nota VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                          (id_nota(medio, titular), medio, titular, t, inicio.isoformat(timespec="minutes"), url,
                           "radio", dep, ahora(), filtro(t)))
        nuevas += cur.rowcount
    con.commit()
    return nuevas


def main(argv=None):
    from faster_whisper import WhisperModel
    ap = argparse.ArgumentParser(prog="python -m tremor.radio")
    ap.add_argument("--minutos", type=float, default=20)
    a = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")
    inicio = datetime.now(LIMA)
    with tempfile.TemporaryDirectory() as d, ThreadPoolExecutor(len(RADIOS)) as ex:
        rutas = [os.path.join(d, f"{i}.wav") for i in range(len(RADIOS))]
        ok = list(ex.map(lambda r: grabar(r[0][2], int(a.minutos * 60), r[1]), zip(RADIOS, rutas)))  # en paralelo
        modelo, con = WhisperModel("small", device="cpu", compute_type="int8"), conectar()
        for (medio, dep, url), ruta, bien in zip(RADIOS, rutas, ok):
            if not bien:
                print(f"  {medio}: sin audio"); continue
            texto = transcribir(modelo, ruta)
            n = guardar(con, medio, dep, url, inicio, texto)
            pasan = con.execute("SELECT COUNT(*) FROM nota WHERE consulta = 'radio' AND medio = ? AND publicado = ? "
                                "AND filtro IS NULL", (medio, inicio.isoformat(timespec="minutes"))).fetchone()[0]
            print(f"  {medio}: {len(texto)} caracteres, {n} fragmentos, {pasan} pasan al codificador")
    return 0


if __name__ == "__main__":
    sys.exit(main())
