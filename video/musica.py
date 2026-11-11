"""Colchón musical de fondo para el video, sintetizado (sin descargas ni licencias): python video/musica.py

Acordes lentos en La menor con senoidales y pocos armónicos, ataque y caída largos, un pulso grave muy sutil cada 2 s.
Sube un poco en la escena del teléfono (~40 s) y baja en el cierre. Pico a -8 dBFS; el volumen final lo pone Vuelo.tsx (0.15 bajo la voz, 0.25 en silencios).
Escribe public/musica.wav (24 kHz, mono, 75 s)."""
import wave
from pathlib import Path

import numpy as np

SR, DUR = 24000, 75
t = np.arange(SR * DUR) / SR
f = lambda n: 440 * 2 ** ((n - 69) / 12)  # nota MIDI → Hz
# Am, F, C, G (notas MIDI), 8 s cada uno, en bucle; ponytail: una sola progresión basta para 75 s
ACORDES = [[57, 60, 64, 69], [53, 57, 60, 65], [48, 55, 60, 64], [55, 59, 62, 67]]
CADA = 8


def voz(nota, ini, dur):
    """Una nota con ataque y caída de 2 s y tres armónicos suaves, dentro de su ventana."""
    tt = np.clip(t - ini, 0, dur)
    env = np.minimum(tt / 2, 1) * np.minimum((dur - tt) / 2, 1) * (t >= ini) * (t < ini + dur)
    h = f(nota)
    return env * (np.sin(2 * np.pi * h * t) + 0.3 * np.sin(2 * np.pi * 2 * h * t) + 0.1 * np.sin(2 * np.pi * 3 * h * t))


y = np.zeros_like(t)
for k, ini in enumerate(np.arange(0, DUR, CADA)):
    for n in ACORDES[k % 4]:
        y += voz(n, ini, CADA + 2)  # se solapan 2 s: el cambio de acorde es un fundido
y += 0.35 * np.sin(2 * np.pi * 55 * t) * np.exp(-((t % 2) * 4)) * (t < DUR - 8)  # pulso grave, decae en 0.25 s
# dinámica: 1.0 de base, sube a 1.3 entre 38 y 48 s (teléfono y alerta), baja a 0.3 en los últimos 8 s
din = np.interp(t, [0, 36, 40, 47, 52, DUR - 8, DUR], [1.0, 1.0, 1.3, 1.3, 1.0, 1.0, 0.3])
y *= din * np.minimum(t / 3, 1)  # entra en 3 s
y *= 0.4 / np.abs(y).max()  # pico -8 dBFS
with wave.open(str(Path(__file__).parent / "public" / "musica.wav"), "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((y * 32767).astype(np.int16).tobytes())
assert abs(np.abs(y).max() - 0.4) < 1e-6 and len(y) == SR * DUR
print("public/musica.wav", DUR, "s")
