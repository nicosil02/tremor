"""Radios en vivo de las zonas de influencia extractiva (módulo 003): graba el stream, transcribe con faster-whisper
(local, sin cuota) y guarda cada fragmento como una `nota`. Después el codificador de prensa (manual EGPP) detecta las
protestas y `tremor.animo` mide menciones y tono hacia cada proyecto o empresa.

    python -m tremor.radio escuchar --minutos 30                        # todas las radios, directo a la base
    python -m tremor.radio escuchar --minutos 30 --grupo 2 --grupos 8 --salida notas_2.jsonl   # una máquina de 8
    python -m tremor.radio cargar notas_*.jsonl                         # junta lo de las máquinas en la base

En GitHub Actions: .github/workflows/radio.yml (matriz de máquinas, como tv-en-vivo.yml de Base_legislativa).
Catálogo: tremor/radios.csv. Whisper "small" en CPU int8, audio mono 16 kHz (como Base_legislativa).
shortcut: solo castellano; el quechua y el aimara necesitan otro modelo (Omnilingual ASR)."""
import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
import tempfile
import wave
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from tremor.db import RAIZ, ahora, conectar
from tremor.prensa.recolectar import LIMA, filtro, id_nota

CATALOGO = RAIZ / "tremor" / "radios.csv"
SR = 16_000
TROZO = 1200  # caracteres por nota: un noticiero trae muchas noticias y el codificador espera una por nota


def radios(grupo=None, grupos=1):
    with open(CATALOGO, encoding="utf-8") as f:
        filas = list(csv.DictReader(f))
    return filas if grupo is None else filas[grupo - 1::grupos]


def grabar(url, segundos, ruta):
    ffmpeg = os.environ.get("FFMPEG_BIN") or shutil.which("ffmpeg")
    if not ffmpeg:  # Windows sin ffmpeg instalado: el binario que trae imageio-ffmpeg
        import imageio_ffmpeg
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    try:
        subprocess.run([ffmpeg, "-loglevel", "error", "-y", "-reconnect", "1", "-reconnect_streamed", "1",
                        "-i", url, "-t", str(segundos), "-vn", "-ac", "1", "-ar", str(SR), ruta],
                       stdin=subprocess.DEVNULL, timeout=segundos + 120, check=False)
    except subprocess.TimeoutExpired:
        pass
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
    segmentos, _ = modelo.transcribe(audio, language="es", vad_filter=True, beam_size=1)  # sin av: choque de versiones
    return " ".join(s.text.strip() for s in segmentos)


def notas(radio, inicio, texto):
    if len(texto) < 100:  # música o silencio
        return []
    medio, salida = radio["medio"], []
    for i, x in enumerate(trozos(texto), 1):
        titular = f"{medio}, en vivo {inicio:%d/%m/%Y %H:%M} ({i})"
        salida.append({"id": id_nota(medio, titular), "medio": medio, "titular": titular, "resumen": x,
                       "publicado": inicio.isoformat(timespec="minutes"), "enlace": radio["stream"],
                       "departamento": radio["departamento"], "filtro": filtro(x)})
    return salida


def guardar(con, filas):
    n = sum(con.execute("INSERT OR IGNORE INTO nota VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (f["id"], f["medio"], f["titular"], f["resumen"], f["publicado"], f["enlace"], "radio",
                         f["departamento"], ahora(), f["filtro"])).rowcount for f in filas)
    con.commit()
    return n


def escuchar(minutos, grupo=None, grupos=1, salida=None):
    from faster_whisper import WhisperModel
    lista, inicio, filas = radios(grupo, grupos), datetime.now(LIMA), []
    print(f"Escuchando {len(lista)} radios {minutos} min", flush=True)
    with tempfile.TemporaryDirectory() as d:
        rutas = [os.path.join(d, f"{i}.wav") for i in range(len(lista))]
        with ThreadPoolExecutor(len(lista)) as ex:  # todas a la vez: solo es red
            ok = list(ex.map(lambda r: grabar(r[0]["stream"], int(minutos * 60), r[1]), zip(lista, rutas)))
        modelo = WhisperModel("small", device="cpu", compute_type="int8")
        for radio, ruta, bien in zip(lista, rutas, ok):
            nuevas = notas(radio, inicio, transcribir(modelo, ruta)) if bien else []
            filas += nuevas
            pasan = sum(f["filtro"] is None for f in nuevas)
            print(f"  {radio['medio']} ({radio['provincia']}): "
                  + (f"{len(nuevas)} fragmentos, {pasan} al codificador" if bien else "sin audio"), flush=True)
    if salida:
        with open(salida, "w", encoding="utf-8") as f:
            f.writelines(json.dumps(x, ensure_ascii=False) + "\n" for x in filas)
    else:
        print(f"{guardar(conectar(), filas)} notas nuevas")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m tremor.radio")
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("escuchar")
    e.add_argument("--minutos", type=float, default=30)
    e.add_argument("--grupo", type=int)
    e.add_argument("--grupos", type=int, default=1)
    e.add_argument("--salida")
    c = sub.add_parser("cargar")
    c.add_argument("archivos", nargs="*")
    a = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")
    if a.cmd == "escuchar":
        escuchar(a.minutos, a.grupo, a.grupos, a.salida)
    else:
        filas = [json.loads(x) for f in a.archivos for x in open(f, encoding="utf-8") if x.strip()]
        print(f"{guardar(conectar(), filas)} notas nuevas de {len(filas)} fragmentos de radio")
    return 0


if __name__ == "__main__":
    sys.exit(main())
