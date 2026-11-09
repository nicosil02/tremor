"""Radios en vivo de las zonas de influencia extractiva (módulo 003): graba el stream, transcribe con faster-whisper
(local, sin cuota) y guarda cada fragmento como una `nota`. Después el codificador de prensa (manual EGPP) detecta las
protestas y `tremor.animo` mide menciones y tono hacia cada proyecto o empresa.

    python -m tremor.radio escuchar --minutos 30                        # todas las radios, directo a la base
    python -m tremor.radio escuchar --minutos 30 --grupo 2 --grupos 8 --salida notas_2.jsonl   # una máquina de 8
    python -m tremor.radio cargar notas_*.jsonl                         # junta lo de las máquinas en la base

En GitHub Actions: .github/workflows/radio.yml (matriz de máquinas, como tv-en-vivo.yml de Base_legislativa).
Catálogo: tremor/radios.csv. Whisper "small" en CPU int8, audio mono 16 kHz (como Base_legislativa).
Quechua y aimara (`--indigena`): Whisper no los conoce y con VAD casi no devuelve texto. Los minutos con voz pero
sin castellano (`no_castellano`) van a MMS (facebook/mms-1b-all, adaptador quz/quy/ayr, int8: ~3x tiempo real en 4
hilos); los fragmentos que pasan `filtro_radio` se traducen al castellano con NLLB-200 600M para el codificador.
Requiere `pip install transformers sentencepiece torch` (CPU); sin eso se queda en castellano."""
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
import re

from tremor.prensa.recolectar import LIMA, NO_ES, id_nota

CATALOGO = RAIZ / "tremor" / "radios.csv"
SR = 16_000
TROZO = 1200  # caracteres por nota: un noticiero trae muchas noticias y el codificador espera una por nota
VENTANA = 60  # segundos: unidad de la detección de lengua
MAX_INDIGENA = 15 * 60  # segundos de quechua/aimara por radio y franja: tope de CPU (MMS ~3x tiempo real en 4 hilos)
# ponytail: la variante sale de la provincia de la radio, no del audio; mms-lid-512 (quz/quy/ayr) si mezcla mucho
AIMARA = {"CHUCUITO", "EL COLLAO", "YUNGUYO", "CANDARAVE", "TARATA"}
QUECHUA_SUR = {"CUSCO", "PUNO", "AREQUIPA", "MOQUEGUA", "TACNA"}  # quechua Cusco-Collao (quz); el resto, chanka (quy)


def radios(grupo=None, grupos=1):
    with open(CATALOGO, encoding="utf-8") as f:
        filas = list(csv.DictReader(f))
    return filas if grupo is None else filas[grupo - 1::grupos]


def directo(url):
    """La TV en vivo (canal de YouTube /live): el manifiesto HLS de menor calidad, solo se usa el audio. En Actions
    YouTube bloquea las IP de datacenter: yt-dlp sale por WARP (YT_DLP_PROXY), como tv-en-vivo de Base_legislativa."""
    if "youtube.com" not in url:
        return url
    import yt_dlp
    opciones = {"quiet": True, "no_warnings": True, **({"proxy": p} if (p := os.environ.get("YT_DLP_PROXY")) else {})}
    try:
        with yt_dlp.YoutubeDL(opciones) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as e:
        print(f"  {url}: sin directo ({str(e)[:80]})", flush=True)
        return None
    hls = sorted((f for f in info.get("formats") or [] if "m3u8" in (f.get("protocol") or "")), key=lambda f: f.get("tbr") or 0)
    return hls[0]["url"] if hls else info.get("url")


def grabar(url, segundos, ruta):
    ffmpeg = os.environ.get("FFMPEG_BIN") or shutil.which("ffmpeg")
    if not ffmpeg:  # Windows sin ffmpeg instalado: el binario que trae imageio-ffmpeg
        import imageio_ffmpeg
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    tv = "youtube.com" in url
    if not (url := directo(url)):
        return False
    proxy = ["-http_proxy", os.environ["FFMPEG_HTTP_PROXY"]] if tv and os.environ.get("FFMPEG_HTTP_PROXY") else []
    try:
        subprocess.run([ffmpeg, "-loglevel", "error", "-y", *proxy, "-reconnect", "1", "-reconnect_streamed", "1",
                        "-i", url, "-t", str(segundos), "-vn", "-ac", "1", "-ar", str(SR), ruta],
                       stdin=subprocess.DEVNULL, timeout=segundos + 120, check=False)
    except subprocess.TimeoutExpired:
        pass
    return os.path.exists(ruta) and os.path.getsize(ruta) > SR * 2 * 10  # al menos 10 s de audio


def trozos(texto, n=TROZO):
    """Corta en frases hasta ~n caracteres."""
    salida, actual = [], ""
    frases = texto.replace("? ", "?. ").replace("! ", "!. ").split(". ")
    w = [f.split() for f in frases]  # MMS no puntúa: las frases larguísimas se parten cada n/12 palabras
    frases = [" ".join(p[i:i + n // 12]) for p in w for i in range(0, max(len(p), 1), n // 12)]
    for frase in frases:
        if len(actual) + len(frase) > n and actual:
            salida.append(actual.strip()); actual = ""
        actual += frase + ". "
    return salida + ([actual.strip()] if actual.strip() else [])


def _ascii(x):
    import unicodedata
    return unicodedata.normalize("NFKD", x).encode("ascii", "ignore").decode().upper().strip()


def lengua(radio) -> str:
    """Adaptador MMS de la radio: aimara, quechua del sur (Cusco-Collao) o chanka."""
    if _ascii(radio["provincia"]) in AIMARA:
        return "ayr"
    return "quz" if _ascii(radio["departamento"]) in QUECHUA_SUR else "quy"


def no_castellano(segs, voz, duracion, ventana=VENTANA, min_voz=20, cps=4):
    """Tramos (ini, fin) en segundos con voz pero casi sin texto de Whisper en castellano. Ante el quechua Whisper
    calla (3 frases en 5 min de Ñuqanchik); el castellano hablado da ~14 caracteres por segundo de voz.
    segs: [(ini, fin, texto)] de Whisper; voz: [(ini, fin)] del VAD."""
    tramos = []
    for a in range(0, int(duracion), ventana):
        b = min(a + ventana, duracion)
        v = sum(max(0, min(f, b) - max(i, a)) for i, f in voz)
        c = sum(len(t) for i, f, t in segs if a <= i < b)
        if v >= min_voz and c / v < cps:
            if tramos and tramos[-1][1] == a:
                tramos[-1] = (tramos[-1][0], b)
            else:
                tramos.append((a, b))
    return tramos


_MMS, _NLLB = {}, {}


def mms(audio, lang):
    """Transcribe con MMS-1b-all + adaptador (int8 dinámico, trozos de 20 s)."""
    import torch
    from transformers import AutoProcessor, Wav2Vec2ForCTC
    if "m" not in _MMS:
        _MMS["p"] = AutoProcessor.from_pretrained("facebook/mms-1b-all")
        m = Wav2Vec2ForCTC.from_pretrained("facebook/mms-1b-all")
        _MMS["m"], _MMS["lang"] = m, None
    p, m = _MMS["p"], _MMS["m"]
    if _MMS["lang"] != lang:  # el adaptador se carga en float y después se cuantiza todo
        p.tokenizer.set_target_lang(lang); m.load_adapter(lang)
        _MMS["q"] = torch.quantization.quantize_dynamic(m, {torch.nn.Linear}, dtype=torch.qint8)
        _MMS["lang"] = lang
    salida = []
    with torch.inference_mode():
        for i in range(0, len(audio), SR * 20):
            x = p(audio[i:i + SR * 20], sampling_rate=SR, return_tensors="pt")
            salida.append(p.decode(_MMS["q"](**x).logits[0].argmax(-1)))
    return " ".join(salida)


def traducir(texto, lang):
    """Al castellano con NLLB-200 600M (quy_Latn sirve también para quz; ayr_Latn para el aimara)."""
    import torch
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
    M = "facebook/nllb-200-distilled-600M"
    if not _NLLB:
        _NLLB["t"], _NLLB["m"] = AutoTokenizer.from_pretrained(M), AutoModelForSeq2SeqLM.from_pretrained(M)
    t, m = _NLLB["t"], _NLLB["m"]
    t.src_lang = "ayr_Latn" if lang == "ayr" else "quy_Latn"
    with torch.inference_mode():
        e = t(texto, return_tensors="pt", truncation=True, max_length=400)
        y = m.generate(**e, forced_bos_token_id=t.convert_tokens_to_ids("spa_Latn"), max_new_tokens=400, num_beams=1,
                       no_repeat_ngram_size=3)  # sin esto repite "de la ciudad" sin fin
    return t.decode(y[0], skip_special_tokens=True)


def transcribir(modelo, ruta, lang=None):
    """Texto en castellano y, con `lang`, el de los tramos en quechua/aimara (MMS)."""
    import numpy as np
    with wave.open(ruta) as w:
        audio = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
    segmentos, _ = modelo.transcribe(audio, language="es", vad_filter=True, beam_size=1)  # sin av: choque de versiones
    segs = [(s.start, s.end, s.text.strip()) for s in segmentos]
    texto, indigena = " ".join(t for _, _, t in segs), ""
    if lang:
        try:
            from faster_whisper.vad import get_speech_timestamps
            voz = [(x["start"] / SR, x["end"] / SR) for x in get_speech_timestamps(audio)]
            resto, partes = MAX_INDIGENA, []
            for a, b in no_castellano(segs, voz, len(audio) / SR):
                b = min(b, a + resto); resto -= b - a
                if b > a:
                    partes.append(mms(audio[int(a * SR):int(b * SR)], lang))
            indigena = " ".join(partes)
        except ImportError:  # sin transformers/torch: solo castellano
            print("  [aviso] sin transformers: no se escucha quechua ni aimara", flush=True)
    return texto, indigena


# Filtro de la radio, más estricto que el de la prensa: un noticiero mezcla música, avisos y prédicas, y cada
# fragmento que pasa gasta cupo del LLM. Pasa solo si nombra una medida de lucha y su contexto (o dos medidas).
FUERTE = re.compile(r"\bparo|sayari|hatari|maqanaku|huelga|bloque[oa]|movilizaci|\bmarcha\b|plant[oó]n|toma (?:de|del|las|los)|"
                    r"enfrentamiento|protesta|piquete|frente de defensa|comuner|ronder|rondas? campesin|"
                    r"medida de lucha|acatamiento|acatan|lucha indefinida|vigilia|cacerolazo|desalojo", re.I)
CONTEXTO = re.compile(r"miner|\bmina\b|empresa|petr[oó]le|\blote\b|oleoducto|derrame|contamina|relave|canon|"
                      r"municipalidad|alcalde|gobierno|ministerio|congreso|prefect|polic|carretera|\bv[ií]a\b|puente|"
                      r"comunidad|agricultor|transportista|docente|trabajadores|sindicato|agua|proyecto|dirigente", re.I)
RELIGIOSO = re.compile(r"\bdios\b|hermanos|biblia|jes[uú]s|iglesia|pastor|am[eé]n|aleluya|esp[ií]ritu santo|"
                       r"cap[ií]tulo \d+|vers[ií]culo|se[nñ]or nuestro", re.I)
AVISO = re.compile(r"ll[aá]m(?:a|enos)|whatsapp|promoci[oó]n|oferta|descuento|precio|cont[aá]ctenos|"
                   r"cel(?:ular)?\b|\b9\d{2}[ .]?\d{3}[ .]?\d{3}|s[ií]guenos|auspicia", re.I)


def filtro_radio(x: str) -> str | None:
    """None si el fragmento va al LLM; si no, el motivo."""
    palabras = re.findall(r"\w+", x.lower())
    if len(palabras) < 40 or len(set(palabras)) / len(palabras) < 0.35:
        return "musica_o_ruido"  # canciones: pocas palabras distintas que se repiten
    if NO_ES.search(x):
        return "no_es_protesta"
    if len(RELIGIOSO.findall(x)) >= 3:
        return "religioso"
    if len(AVISO.findall(x)) >= 3:
        return "aviso"
    fuertes = len(FUERTE.findall(x))
    if fuertes >= 2 or (fuertes and CONTEXTO.search(x)):
        return None
    return "sin_medida_de_lucha"


NOMBRE = {"quz": "quechua", "quy": "quechua", "ayr": "aimara"}


def notas(radio, inicio, texto, indigena="", lang=None):
    """Un fragmento por nota. Los de quechua/aimara pasan el filtro en la lengua original (préstamos: paro, huelga,
    mina, municipalidad) y solo esos se traducen; la nota lleva la traducción y el original."""
    medio, salida, vistos = radio["medio"], [], set()
    for sufijo, txt in (("", texto), (f", {NOMBRE.get(lang, '')}", indigena)):
        if len(txt) < 100:  # música o silencio
            continue
        for i, x in enumerate(trozos(txt), 1):
            huella = " ".join(re.findall(r"\w+", x.lower()))[:300]
            if huella in vistos:  # el mismo aviso o la misma cortina repetida en la franja
                continue
            vistos.add(huella)
            titular = f"{medio}, en vivo {inicio:%d/%m/%Y %H:%M}{sufijo} ({i})"
            filtro = filtro_radio(x)
            if sufijo and filtro is None:
                x = f"{traducir(x, lang)} [original en {NOMBRE[lang]}: {x}]"
            salida.append({"id": id_nota(medio, titular), "medio": medio, "titular": titular, "resumen": x,
                           "publicado": inicio.isoformat(timespec="minutes"), "enlace": radio["stream"],
                           "departamento": radio["departamento"], "filtro": filtro})
    return salida


def guardar(con, filas):
    n = sum(con.execute("INSERT OR IGNORE INTO nota VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (f["id"], f["medio"], f["titular"], f["resumen"], f["publicado"], f["enlace"], "radio",
                         f["departamento"], ahora(), f["filtro"])).rowcount for f in filas)
    con.commit()
    return n


def escuchar(minutos, grupo=None, grupos=1, salida=None, indigena=False):
    from faster_whisper import WhisperModel
    lista, inicio, filas = radios(grupo, grupos), datetime.now(LIMA), []
    print(f"Escuchando {len(lista)} radios {minutos} min", flush=True)
    with tempfile.TemporaryDirectory() as d:
        rutas = [os.path.join(d, f"{i}.wav") for i in range(len(lista))]
        with ThreadPoolExecutor(len(lista)) as ex:  # todas a la vez: solo es red
            ok = list(ex.map(lambda r: grabar(r[0]["stream"], int(minutos * 60), r[1]), zip(lista, rutas)))
        modelo = WhisperModel("small", device="cpu", compute_type="int8")
        for radio, ruta, bien in zip(lista, rutas, ok):
            lang = lengua(radio) if indigena else None
            nuevas = notas(radio, inicio, *transcribir(modelo, ruta, lang), lang) if bien else []
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
    e.add_argument("--indigena", action="store_true", help="quechua y aimara con MMS (necesita transformers)")
    c = sub.add_parser("cargar")
    c.add_argument("archivos", nargs="*")
    a = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")
    if a.cmd == "escuchar":
        escuchar(a.minutos, a.grupo, a.grupos, a.salida, a.indigena)
    else:
        filas = [json.loads(x) for f in a.archivos for x in open(f, encoding="utf-8") if x.strip()]
        print(f"{guardar(conectar(), filas)} notas nuevas de {len(filas)} fragmentos de radio")
    return 0


if __name__ == "__main__":
    sys.exit(main())
