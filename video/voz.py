"""Narración con Chatterbox Multilingual (Resemble AI, licencia MIT): voz en castellano con control de emoción, local
y gratis. El timbre sale de una referencia corta (`--ref`, un locutor genérico, nunca la voz de una persona real sin
permiso); la entonación la pone el modelo, más expresiva con `exaggeration` alto.

    C:/cb/Scripts/python video/voz.py --ref video/public/voz/ref.wav            # escribe public/voz/NN.wav y src/voz.json
    C:/cb/Scripts/python video/voz.py --ref ... --probar 2                       # tres tomas de la frase 2, para elegir

Necesita `pip install chatterbox-tts` (torch con CUDA; en una RTX de 6 GB tarda segundos por frase)."""
import argparse, json
from pathlib import Path
import torchaudio
from chatterbox.mtl_tts import ChatterboxMultilingualTTS

AQUI = Path(__file__).parent
FRASES = json.load(open(AQUI / "src" / "frases.json", encoding="utf-8"))
# la emoción de cada frase: el gancho y el cierre más intensos, los datos más firmes
EMOCION = [0.75, 0.7, 0.6, 0.6, 0.6, 0.6, 0.7, 0.55, 0.5]

p = argparse.ArgumentParser()
p.add_argument("--ref", required=True)
p.add_argument("--probar", type=int)
a = p.parse_args()
tts = ChatterboxMultilingualTTS.from_pretrained(device="cuda")
out = AQUI / "public" / "voz"
habla = lambda i: tts.generate(FRASES[i], language_id="es", audio_prompt_path=a.ref, exaggeration=EMOCION[i], cfg_weight=0.35, temperature=0.8)

if a.probar is not None:
    for k in range(3):
        torchaudio.save(str(out / f"prueba{k}.wav"), habla(a.probar), tts.sr)
else:
    dur = []
    for i in range(len(FRASES)):
        w = habla(i)
        torchaudio.save(str(out / f"{i:02d}.wav"), w, tts.sr)
        dur.append(round(w.shape[-1] / tts.sr, 2))
    json.dump(dur, open(AQUI / "src" / "voz.json", "w"))
    print(dur, round(sum(dur), 1), "s")
