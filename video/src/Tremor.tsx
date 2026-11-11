import React from "react";
import { AbsoluteFill, Audio, Sequence, Series, staticFile } from "remotion";
import { Alertas, Aviso, Bloqueo, Cierre, Plataforma, Prediccion, Pregunta, Ruta, Seguimiento } from "./escenas";
import voz from "./voz.json";

// Cada escena dura lo que su frase más un respiro, sin bajar del mínimo que necesita su animación
const ESCENAS = [Pregunta, Bloqueo, Alertas, Seguimiento, Prediccion, Ruta, Aviso, Plataforma, Cierre];
const MINIMO = [150, 210, 300, 180, 300, 230, 200, 170, 150];
const ENTRA = [40, 10, 10, 10, 10, 10, 20, 10, 20]; // cuándo empieza a hablar el locutor en cada escena
export const DURACIONES = voz.map((d, i) => Math.max(MINIMO[i], Math.ceil(d * 30) + ENTRA[i] + 24));
export const TOTAL = DURACIONES.reduce((a, b) => a + b, 0);

export const Tremor: React.FC = () => (
  <AbsoluteFill style={{ background: "#f8faf9" }}>
    <Series>
      {ESCENAS.map((Escena, i) => (
        <Series.Sequence key={i} durationInFrames={DURACIONES[i]}>
          <Escena />
          <Sequence from={ENTRA[i]}><Audio src={staticFile(`voz/${String(i).padStart(2, "0")}.wav`)} /></Sequence>
        </Series.Sequence>
      ))}
    </Series>
  </AbsoluteFill>
);
