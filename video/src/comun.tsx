import React from "react";
import { Easing, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { loadFont } from "@remotion/google-fonts/Archivo";

export const { fontFamily } = loadFont("normal", { weights: ["400", "500", "600", "700", "800"], subsets: ["latin", "latin-ext"] });

// La paleta de la página de inicio
export const C = {
  papel: "#f8faf9", piedra: "#e8ecec", linea: "#d3dad9", tinta: "#1c2629", tinta2: "#4f5d61", gris: "#8d9a99",
  cobre: "#b4542a", cobre1: "#f3e1d3", cobre2: "#e3a67c", cobre4: "#8a3213", pardo: "#2a1a12", verde: "#2f6b4f",
  rojo: "#c0392b", via: "#c9d1d0",
};

export const sale = Easing.bezier(0.23, 1, 0.32, 1);
export const mueve = Easing.bezier(0.77, 0, 0.175, 1);

/** 0→1 entre dos cuadros, con la curva de salida fuerte. */
export const tramo = (f: number, a: number, b: number, ease = sale) =>
  interpolate(f, [a, b], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease });

export const miles = (n: number) => Math.round(n).toLocaleString("es-PE").replace(/,/g, " ");

/** Texto grande en mayúsculas, palabra por palabra, como en los videos de referencia. Cada línea entra en su cuadro. */
export const Rotulo: React.FC<{ lineas: [number, string][]; claro?: boolean; abajo?: number }> = ({ lineas, claro, abajo = 250 }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const actual = [...lineas].reverse().find(([d]) => f >= d);
  if (!actual) return null;
  const [desde, texto] = actual;
  const palabras = texto.split(" ");
  return (
    <div style={{ position: "absolute", left: 80, right: 80, bottom: abajo, textAlign: "center", fontFamily, fontWeight: 800,
      fontSize: 84, lineHeight: 1.02, letterSpacing: -1.5, color: claro ? "#fff" : C.tinta, textTransform: "uppercase" }}>
      {palabras.map((p, i) => {
        const s = spring({ frame: f - desde - i * 3, fps, config: { damping: 16, stiffness: 180 } });
        return (
          <span key={i} style={{ display: "inline-block", marginRight: 22, opacity: s, transform: `translateY(${(1 - s) * 40}px) scale(${0.9 + s * 0.1})` }}>{p}</span>
        );
      })}
    </div>
  );
};

/** El punto de Tremor, con el halo que palpita. */
export const Punto: React.FC<{ r?: number; f: number }> = ({ r = 18, f }) => {
  const k = (f % 45) / 45;
  return (
    <div style={{ position: "relative", width: r * 2, height: r * 2 }}>
      <div style={{ position: "absolute", inset: 0, borderRadius: "50%", background: C.cobre, opacity: 0.35 * (1 - k), transform: `scale(${1 + k * 1.6})` }} />
      <div style={{ position: "absolute", inset: 0, borderRadius: "50%", background: C.cobre, boxShadow: `0 0 0 ${r * 0.45}px ${C.cobre1}` }} />
    </div>
  );
};

/** Una línea poligonal como path de SVG. */
export const trazo = (p: number[][]) => p.map(([x, y], i) => `${i ? "L" : "M"}${x} ${y}`).join(" ");

/** Punto a una fracción t de una poligonal, y su largo. */
export function sobre(p: number[][], t: number) {
  const seg = p.slice(1).map((q, i) => Math.hypot(q[0] - p[i][0], q[1] - p[i][1]));
  const total = seg.reduce((a, b) => a + b, 0);
  let d = Math.max(0, Math.min(1, t)) * total;
  for (let i = 0; i < seg.length; i++) {
    if (d <= seg[i] || i === seg.length - 1) {
      const k = seg[i] ? Math.min(1, d / seg[i]) : 0;
      const [a, b] = [p[i], p[i + 1]];
      return { x: a[0] + (b[0] - a[0]) * k, y: a[1] + (b[1] - a[1]) * k, ang: Math.atan2(b[1] - a[1], b[0] - a[0]) * 180 / Math.PI, total };
    }
    d -= seg[i];
  }
  return { x: p[0][0], y: p[0][1], ang: 0, total };
}
