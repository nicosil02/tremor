import React from "react";
import { AbsoluteFill, Audio, Easing, Sequence, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import type { GeoJSONSource, Map as Mapa } from "maplibre-gl";
import * as turf from "@turf/turf";
import { C, Punto, fontFamily, miles, mueve, sale, tramo } from "./comun";
import { Camara, LARGO, Mapa3D, punto } from "./Mapa3D";
import geo from "./geo.json";
import voz from "./voz.json";
import palabras from "./palabras.json";

/* Un solo vuelo de cámara sobre el relieve real del Perú. El locutor marca el tiempo: cada frase empieza en S[i]. */
const D = voz.map((d) => Math.ceil(d * 30));
export const S = D.reduce<number[]>((a, d, i) => [...a, i ? a[i - 1] + D[i - 1] + 14 : 24], []);
export const TOTAL = S[8] + D[8] + 60;
const PAL = palabras as [string, number, number][][];
// cuadro en que el locutor empieza a decir una palabra de la frase i
const en = (i: number, w: string) => S[i] + Math.round((PAL[i].find(([p]) => p.startsWith(w))?.[1] ?? 0) * 30);

const BLOQUEO = 190; // km de la ruta, en la Bajada a Arequipa
const TRAMOS: [string, number, number][] = [["Mina a Callalli", 9, 25], ["Bajada a Arequipa", 29, 189], ["Puerto de Matarani", 29, 262], ["Al Callao por la Panamericana", 25, LARGO]];
const MINA = geo.mina as [number, number];
const RIESGO = Math.round(geo.bateas.prob_zona_extractivo * 100);

// Rumbo suave a lo largo de la ruta: promedio de las direcciones de los próximos 30 km
const rumbo = (km: number) => {
  let x = 0, y = 0;
  for (let d = 4; d <= 30; d += 2) { const b = (turf.bearing(punto(km), punto(km + d)) * Math.PI) / 180; x += Math.sin(b); y += Math.cos(b); }
  return (Math.atan2(x, y) * 180) / Math.PI;
};
const sigue = (km: number, zoom: number, pitch: number, giro = 0): Camara => ({ centro: punto(km + 4), zoom, pitch, rumbo: rumbo(km) + giro });

// Momentos de la frase 6 (predicción): el país, la operación y la ruta tramo por tramo
const E6 = () => en(6, "estima"), Z6 = () => en(6, "zona"), T6 = () => en(6, "tramo");
type Clave = [number, Camara | ((f: number) => Camara)];
const CLAVES: Clave[] = [
  [0, { centro: [-75.2, -10.2], zoom: 4.9, pitch: 25, rumbo: 0 }],
  [S[0] + 30, { centro: [-72.6, -14.6], zoom: 6.6, pitch: 50, rumbo: -12 }],
  [S[1] - 6, (f) => sigue(BLOQUEO - 14 + (f - S[0]) * 0.04, 11.3, 68, 0)],
  [S[2] - 6, (f) => sigue(BLOQUEO - 14 + (f - S[0]) * 0.04, 11.5, 70, (f - S[1] + 6) * 0.25)],
  [S[2] + 60, { centro: [-73.4, -13.9], zoom: 5.9, pitch: 42, rumbo: -8 }],
  [S[5] - 10, { centro: [-72.6, -14.6], zoom: 6.4, pitch: 48, rumbo: 6 }],
  [E6() + 10, { centro: [-75.0, -10.6], zoom: 5.0, pitch: 38, rumbo: 0 }],
  [Z6() - 4, { centro: [-74.6, -11.2], zoom: 5.15, pitch: 40, rumbo: 4 }],
  [T6() - 6, { centro: punto(185), zoom: 8.3, pitch: 46, rumbo: 205 }],
  [S[7] + 6, { centro: punto(200), zoom: 8.5, pitch: 50, rumbo: 218 }],
  [S[7] + 50, { centro: [-75.0, -10.6], zoom: 5.2, pitch: 35, rumbo: 0 }],
  [S[8] - 6, { centro: [-75.0, -10.4], zoom: 5.0, pitch: 30, rumbo: 0 }],
  [TOTAL, { centro: [-75.0, -10.0], zoom: 4.8, pitch: 20, rumbo: 0 }],
];
const giro = (a: number, b: number) => ((((b - a) % 360) + 540) % 360) - 180;
const camara = (f: number): Camara => {
  const i = Math.max(0, CLAVES.findIndex(([k], j) => f >= k && (j === CLAVES.length - 1 || f < CLAVES[j + 1][0])));
  const [ka, a0] = CLAVES[i], [kb, b0] = CLAVES[Math.min(i + 1, CLAVES.length - 1)];
  const a = typeof a0 === "function" ? a0(f) : a0, b = typeof b0 === "function" ? b0(f) : b0;
  const t = kb === ka ? 0 : mueve(Math.min(1, (f - ka) / (kb - ka)));
  const l = (x: number, y: number) => x + (y - x) * t;
  return { centro: [l(a.centro[0], b.centro[0]), l(a.centro[1], b.centro[1])], zoom: l(a.zoom, b.zoom), pitch: l(a.pitch, b.pitch), rumbo: a.rumbo + giro(a.rumbo, b.rumbo) * t };
};

// Capas: zonas con operación pintadas por su riesgo real, radios que palpitan, la ruta y el bloqueo
const fc = turf.featureCollection;
const pt = (p: number[], props: object) => turf.point(p as [number, number], props);
const ZONAS = fc(geo.zonas.map(([x, y, r]) => pt([x, y], { r })));
const preparar = (m: Mapa) => {
  m.addSource("zonas", { type: "geojson", data: ZONAS });
  m.addLayer({ id: "zonas", type: "circle", source: "zonas", paint: {
    "circle-color": ["interpolate", ["linear"], ["get", "r"], 0, "#e8ecec", 0.08, "#e3a67c", 0.18, "#b4542a", 0.3, "#8a3213"],
    "circle-radius": ["interpolate", ["linear"], ["zoom"], 5, ["+", 2.5, ["*", 22, ["get", "r"]]], 10, ["+", 8, ["*", 60, ["get", "r"]]]],
    "circle-stroke-color": "#ffffff", "circle-stroke-width": 1.2, "circle-opacity": 0, "circle-stroke-opacity": 0, "circle-pitch-alignment": "map" } });
  m.addSource("radios", { type: "geojson", data: fc([]) });
  m.addLayer({ id: "radios", type: "circle", source: "radios", paint: { "circle-color": "rgba(0,0,0,0)", "circle-radius": ["get", "radio"],
    "circle-stroke-color": "#b4542a", "circle-stroke-width": 2.5, "circle-stroke-opacity": ["get", "op"], "circle-pitch-alignment": "map" } });
  m.addLayer({ id: "radios-centro", type: "circle", source: "radios", paint: { "circle-color": "#2a1a12", "circle-radius": 3.5, "circle-opacity": ["get", "base"], "circle-pitch-alignment": "map" } });
  m.addSource("ruta", { type: "geojson", data: fc([]) });
  m.addLayer({ id: "ruta-halo", type: "line", source: "ruta", layout: { "line-cap": "round", "line-join": "round" }, paint: { "line-color": "#ffffff", "line-width": 13 } });
  m.addLayer({ id: "ruta", type: "line", source: "ruta", layout: { "line-cap": "round", "line-join": "round" }, paint: { "line-color": "#b4542a", "line-width": 7 } });
  m.addSource("pulso", { type: "geojson", data: fc([]) });
  m.addLayer({ id: "pulso", type: "circle", source: "pulso", paint: { "circle-color": ["get", "color"], "circle-radius": ["get", "radio"], "circle-opacity": ["get", "op"], "circle-pitch-alignment": "map" } });
};
const cuadro = (m: Mapa, f: number) => {
  const T = T6();
  const z = tramo(f, E6() - 10, E6() + 30) * (1 - 0.55 * tramo(f, T - 20, T + 10) * (1 - tramo(f, S[7] + 10, S[7] + 40)));
  m.setPaintProperty("zonas", "circle-opacity", 0.9 * z);
  m.setPaintProperty("zonas", "circle-stroke-opacity", z);
  const r = tramo(f, S[2], S[2] + 50) * (1 - tramo(f, S[5] - 10, S[5] + 20));
  (m.getSource("radios") as GeoJSONSource).setData(fc(r ? geo.radios.map(([x, y], i) => {
    const k = ((f + i * 11) % 50) / 50;
    return pt([x, y], { radio: 4 + 22 * k, op: r * (1 - k), base: r });
  }) : []));
  // la ruta: primero el tramo del bloqueo; en la predicción se dibuja entera desde la mina
  const a = tramo(f, S[0] + 20, S[0] + 70);
  const tramoVisto: [number, number] = f < T - 20 ? [BLOQUEO - 40 * a, BLOQUEO + 40 * a] : [0, Math.max(0.2, Math.min(LARGO, 6 + (f - T + 20) * 5))];
  const ver = f < S[3] || (f > T - 20 && f < S[7] + 40);
  (m.getSource("ruta") as GeoJSONSource).setData(ver && tramoVisto[1] - tramoVisto[0] > 0.2 ? turf.lineSliceAlong(turf.lineString(geo.camino), tramoVisto[0], tramoVisto[1]) : fc([]));
  const k = (f % 40) / 40;
  const pulsos = [];
  if (f > S[0] + 20 && f < S[3]) pulsos.push(pt(punto(BLOQUEO), { color: C.rojo, radio: 10 + 40 * k, op: 0.5 * (1 - k) }), pt(punto(BLOQUEO), { color: C.rojo, radio: 11, op: 1 }));
  if (f > Z6() - 10 && f < S[7] + 40) pulsos.push(pt(MINA, { color: C.cobre4, radio: 12 + 46 * k, op: 0.45 * (1 - k) }), pt(MINA, { color: C.cobre4, radio: 13, op: 1 }));
  (m.getSource("pulso") as GeoJSONSource).setData(fc(pulsos));
};

/* Piezas que flotan sobre el mapa */
const sombra = "0 30px 60px -24px rgba(42,26,18,.45), 0 2px 6px rgba(42,26,18,.08)";
// Estilo Apple: la tarjeta entra desenfocada y crece; cada palabra sube desde una máscara y se enfoca, en cascada
const Inicio = React.createContext(0);
const suave = Easing.bezier(0.16, 1, 0.3, 1);
const Tarjeta: React.FC<{ desde: number; hasta: number; style?: React.CSSProperties; children: React.ReactNode }> = ({ desde, hasta, style, children }) => {
  const f = useCurrentFrame();
  const e = interpolate(f, [desde, desde + 22], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: suave });
  const x = interpolate(f, [hasta, hasta + 14], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.in(Easing.cubic) });
  if (f < desde || f > hasta + 14) return null;
  return (
    <Inicio.Provider value={desde}>
      <div style={{ position: "absolute", background: "rgba(255,255,255,.94)", backdropFilter: "blur(18px)", borderRadius: 34, boxShadow: sombra, padding: "32px 38px",
        opacity: e * (1 - x), filter: `blur(${(1 - e) * 14 + x * 10}px)`, transform: `translateY(${(1 - e) * 50 - x * 30}px) scale(${0.9 + 0.1 * e - 0.04 * x})`, ...style }}>{children}</div>
    </Inicio.Provider>
  );
};
export const Txt: React.FC<{ children: string; d?: number; style?: React.CSSProperties }> = ({ children, d = 6, style }) => {
  const f = useCurrentFrame() - React.useContext(Inicio) - d;
  return (
    <div style={style}>
      {children.split(" ").map((w, i) => {
        const p = interpolate(f - i * 1.6, [0, 18], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: suave });
        return (
          <span key={i} style={{ display: "inline-block", overflow: "hidden", verticalAlign: "top", paddingBottom: "0.12em", marginBottom: "-0.12em", marginRight: "0.26em" }}>
            <span style={{ display: "inline-block", transform: `translateY(${(1 - p) * 105}%)`, filter: `blur(${(1 - p) * 6}px)`, opacity: 0.2 + 0.8 * p }}>{w}</span>
          </span>
        );
      })}
    </div>
  );
};
const Etq: React.FC<{ children: string; d?: number; color?: string }> = ({ children, d = 4, color = C.tinta2 }) => <Txt d={d} style={{ fontSize: 27, fontWeight: 600, color }}>{children}</Txt>;
const Num: React.FC<{ children: string; d?: number; style?: React.CSSProperties }> = ({ children, d = 8, style }) => (
  <Txt d={d} style={{ fontWeight: 800, letterSpacing: "-0.035em", fontVariantNumeric: "tabular-nums", lineHeight: 1.02, whiteSpace: "nowrap", ...style }}>{children}</Txt>
);

const Bloqueo: React.FC = () => {
  const f = useCurrentFrame();
  return (
    <Tarjeta desde={en(0, "bloqueo") - 4} hasta={S[1] + 4} style={{ left: 60, right: 60, top: 200, borderRadius: 60, padding: "30px 40px", display: "flex", alignItems: "center", gap: 26 }}>
      <div style={{ width: 26, height: 26, borderRadius: 13, background: C.rojo, boxShadow: `0 0 0 ${8 + 6 * Math.sin(f / 5)}px rgba(192,57,43,.2)`, flex: "none" }} />
      <div><Txt d={4} style={{ fontSize: 44, fontWeight: 800 }}>Bloqueo en la ruta</Txt><Etq d={8}>Bajada a Arequipa · vía cerrada</Etq></div>
    </Tarjeta>
  );
};

const Costo: React.FC = () => {
  const f = useCurrentFrame();
  const h = interpolate(f, [S[1] + 20, S[2] - 16], [0, 24], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: sale });
  return (
    <Tarjeta desde={S[1] + 10} hasta={S[2] + 6} style={{ left: 60, right: 60, top: 200 }}>
      <Etq>Una mina mediana detenida</Etq>
      <div style={{ display: "grid", gridTemplateColumns: "0.7fr 2fr", gap: 24, marginTop: 8 }}>
        <div><Num style={{ fontSize: 84 }}>{`${Math.round(h)} h`}</Num><Etq d={10}>detenida</Etq></div>
        <div><Num style={{ fontSize: 84, color: C.cobre4 }}>{`US$${miles((h / 24) * 374000)}`}</Num><Etq d={12}>en ventas que no salen</Etq></div>
      </div>
    </Tarjeta>
  );
};

const Aviso: React.FC = () => (
  <Tarjeta desde={en(2, "Se") - 4} hasta={S[3] - 8} style={{ left: 60, right: 60, top: 200 }}>
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}><Etq>Pachamama Radio · 20 oct</Etq>
      <span style={{ background: C.cobre, color: "#fff", borderRadius: 30, padding: "6px 18px", fontSize: 24, fontWeight: 700 }}>Protesta anunciada</span></div>
    <Txt d={10} style={{ fontSize: 44, fontWeight: 800, lineHeight: 1.15, marginTop: 14 }}>Pobladores de Putina radicalizarán su protesta en la carretera el 6 de noviembre</Txt>
  </Tarjeta>
);

const QueEs: React.FC = () => {
  const f = useCurrentFrame();
  return (
    <Tarjeta desde={S[3] - 6} hasta={S[4] - 8} style={{ left: 60, right: 60, top: 200, padding: "40px 44px" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 22 }}><Punto r={20} f={f} /><Num d={4} style={{ fontSize: 96 }}>Tremor</Num></div>
      <Txt d={12} style={{ fontSize: 40, fontWeight: 700, lineHeight: 1.2, marginTop: 14 }}>Alerta temprana para los equipos de gestión social de la minería</Txt>
    </Tarjeta>
  );
};

const Monitorea: React.FC = () => {
  const f = useCurrentFrame();
  const c = (a: number, n: number) => miles(interpolate(f, [a, a + 30], [0, n], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: sale }));
  const chip = (t: string, a: number, fondo = C.cobre1, color = C.cobre4) => {
    const p = tramo(f, a, a + 16, suave);
    return <span key={t} style={{ padding: "10px 22px", borderRadius: 40, background: fondo, color, fontSize: 30, fontWeight: 700,
      opacity: p, filter: `blur(${(1 - p) * 6}px)`, transform: `scale(${0.8 + 0.2 * p})`, display: "inline-block" }}>{t}</span>;
  };
  return (
    <Tarjeta desde={S[4] - 6} hasta={S[5] - 14} style={{ left: 60, right: 60, top: 200 }}>
      <div style={{ display: "flex", gap: 60 }}>
        <div><Num style={{ fontSize: 100, color: C.cobre }}>{c(en(4, "286") - 6, 286)}</Num><Etq d={10}>radios locales</Etq></div>
        <div style={{ opacity: tramo(f, en(4, "lee") - 4, en(4, "lee") + 8) }}><Num style={{ fontSize: 100 }}>{`${c(en(4, "lee"), 400)}+`}</Num><Etq d={10}>medios de prensa</Etq></div>
      </div>
      <div style={{ display: "flex", gap: 14, marginTop: 26, flexWrap: "wrap" }}>
        {["Castellano", "Quechua", "Aimara"].map((t, i) => chip(t, en(4, "castellano") + i * 9))}
        {["Defensoría del Pueblo", "SUTRAN"].map((t, i) => chip(t, en(4, "Defensoría") + i * 9, C.piedra, C.tinta))}
      </div>
    </Tarjeta>
  );
};

const Riesgo: React.FC = () => {
  const f = useCurrentFrame(), E = E6(), Z = Z6();
  return (
    <>
      <Tarjeta desde={E - 6} hasta={Z - 6} style={{ left: 60, right: 60, top: 200 }}>
        <Etq>Riesgo de un paro o bloqueo contra cada operación, próximos 3 meses</Etq>
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 18 }}>
          {["#e8ecec", "#e3a67c", "#b4542a", "#8a3213"].map((c, i) => <div key={c} style={{ flex: 1, height: 18, borderRadius: 9, background: c, transformOrigin: "0 50%", transform: `scaleX(${tramo(f, E + 4 + i * 5, E + 24 + i * 5, suave)})` }} />)}
        </div>
        <div style={{ display: "flex", justifyContent: "space-between", marginTop: 10 }}><Etq>Bajo</Etq><Etq>Alto</Etq></div>
      </Tarjeta>
      <Tarjeta desde={Z - 2} hasta={T6() + 26} style={{ left: 60, right: 60, top: 200 }}>
        <Etq>Bateas, Caylloma · próximos 3 meses</Etq>
        <div style={{ display: "flex", alignItems: "center", gap: 22 }}>
          <Num style={{ fontSize: 130, color: C.cobre4 }}>{`${Math.round(RIESGO * tramo(f, Z + 4, Z + 40))}%`}</Num>
          <span style={{ background: C.cobre2, color: C.cobre4, borderRadius: 30, padding: "8px 22px", fontSize: 30, fontWeight: 700 }}>Medio · casi el doble del promedio</span>
        </div>
        <Etq d={12}>de un paro o bloqueo contra la operación</Etq>
      </Tarjeta>
    </>
  );
};

// Los porcentajes de cada tramo, pegados al mapa
const Tramos: React.FC<{ xy: ({ x: number; y: number } | null)[] }> = ({ xy }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const fin = 1 - tramo(f, S[7] + 24, S[7] + 40);
  return (
    <>
      {TRAMOS.map(([nombre, p, km], i) => {
        const llega = T6() - 20 + (km - 6) / 5;
        const s = spring({ frame: f - llega, fps, config: { damping: 14 } }) * fin;
        const q = xy[i];
        if (!q || f < llega) return null;
        return (
          <div key={nombre} style={{ position: "absolute", left: q.x, top: q.y, transform: `translate(${i === 3 ? "-115%" : i === 2 ? "15%" : "-50%"}, calc(-100% - 26px)) scale(${s})`, transformOrigin: "50% 100%",
            background: "#fff", borderRadius: 22, boxShadow: sombra, padding: "14px 22px", textAlign: "center", whiteSpace: "nowrap" }}>
            <div style={{ fontSize: 46, fontWeight: 800, color: p >= 29 ? C.cobre4 : C.tinta }}>{p}%</div>
            <div style={{ fontSize: 22, fontWeight: 600, color: C.tinta2 }}>{nombre}</div>
          </div>
        );
      })}
    </>
  );
};
const Salida: React.FC = () => (
  <Tarjeta desde={T6() + 30} hasta={S[7] + 30} style={{ left: 60, right: 60, top: 200, background: C.verde, color: "#fff" }}>
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
      <div><Txt d={4} style={{ fontSize: 26, fontWeight: 600, opacity: 0.85 }}>Riesgo de corte en su ruta de salida</Txt>
        <Txt d={8} style={{ fontSize: 40, fontWeight: 800 }}>Mina → Matarani → Callao</Txt></div>
      <Num style={{ fontSize: 96 }}>66%</Num>
    </div>
  </Tarjeta>
);

const Notificacion: React.FC<{ titulo: string; texto: string; desde: number; urgente?: boolean }> = ({ titulo, texto, desde, urgente }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({ frame: f - desde, fps, config: { damping: 13 } });
  return (
    <div style={{ background: "rgba(255,255,255,.96)", borderRadius: 34, padding: "26px 28px", boxShadow: "0 20px 40px -16px rgba(0,0,0,.35)", display: "flex", gap: 22,
      transform: `translateY(${(1 - s) * 90}px) scale(${0.92 + s * 0.08})`, opacity: s, filter: `blur(${(1 - s) * 8}px)`, marginBottom: 18 }}>
      <div style={{ width: 64, height: 64, borderRadius: 16, background: urgente ? C.cobre : C.pardo, display: "grid", placeItems: "center", flex: "none" }}>
        <div style={{ width: 22, height: 22, borderRadius: "50%", background: urgente ? "#fff" : C.cobre }} /></div>
      <div><div style={{ fontSize: 26, color: C.tinta2, fontWeight: 600 }}>TREMOR · ahora</div>
        <div style={{ fontSize: 34, fontWeight: 800, marginTop: 2 }}>{titulo}</div>
        <div style={{ fontSize: 28, color: C.tinta2, lineHeight: 1.3, marginTop: 4 }}>{texto}</div></div>
    </div>
  );
};
const Telefono: React.FC = () => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const a = spring({ frame: f - (S[5] - 16), fps, config: { damping: 18 } }), b = tramo(f, S[6] - 8, S[6] + 16, mueve);
  if (f < S[5] - 16 || f > S[6] + 16) return null;
  return (
    <div style={{ position: "absolute", left: 230, top: 330, width: 620, height: 1260, borderRadius: 84, background: C.tinta, padding: 20,
      transform: `translateY(${(1 - a) * 1500 - b * 1600}px) rotate(${(1 - a) * 8}deg)`, boxShadow: "0 60px 120px -40px rgba(42,26,18,.6)" }}>
      <div style={{ position: "relative", width: "100%", height: "100%", borderRadius: 66, overflow: "hidden", background: "linear-gradient(170deg, #f1e5dc, #e3a67c 60%, #8a3213)" }}>
        <div style={{ textAlign: "center", color: "#fff", marginTop: 110, fontSize: 120, fontWeight: 300, letterSpacing: -4 }}>6:52</div>
        <div style={{ textAlign: "center", color: "#fff", fontSize: 30, opacity: 0.9 }}>lunes</div>
        <div style={{ position: "absolute", left: 20, right: 20, top: 400 }}>
          <Notificacion desde={en(5, "envía") - 4} urgente titulo="Paro de transportistas en Arequipa" texto="16 de noviembre, por el alza de los combustibles. Fuente: El Búho." />
        </div>
      </div>
    </div>
  );
};

const Prueba: React.FC = () => (
  <Tarjeta desde={S[7] + 30} hasta={S[8] - 6} style={{ left: 60, right: 60, top: 200 }}>
    <Etq>Zonas que Tremor marca en alerta, 2024-2026</Etq>
    <div style={{ display: "flex", alignItems: "baseline", gap: 18, marginTop: 6 }}>
      <Num d={8} style={{ fontSize: 130, color: C.cobre4 }}>9,6×</Num><Etq d={14}>más conflictos</Etq>
    </div>
    <Txt d={18} style={{ fontSize: 30, fontWeight: 600, lineHeight: 1.3, color: C.tinta2 }}>El 48% de los paros y bloqueos contra operaciones ocurrió en el 5% de zonas en alerta</Txt>
  </Tarjeta>
);

const Cierre: React.FC = () => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({ frame: f - S[8], fps, config: { damping: 15 } });
  if (f < S[8]) return null;
  return (
    <AbsoluteFill style={{ background: `radial-gradient(ellipse at 50% 70%, rgba(248,250,249,${0.92 * s}) 30%, rgba(248,250,249,${0.4 * s}) 70%)` }}>
      <div style={{ position: "absolute", left: 80, right: 80, top: 1180, textAlign: "center", opacity: s, transform: `translateY(${(1 - s) * 50}px)` }}>
        <div style={{ display: "inline-flex", alignItems: "center", gap: 30 }}><Punto r={34} f={f} /><span style={{ fontSize: 150, fontWeight: 800, letterSpacing: -5 }}>Tremor</span></div>
        <div style={{ fontSize: 48, fontWeight: 600, color: C.tinta2, lineHeight: 1.2, marginTop: 24, opacity: tramo(f, S[8] + 25, S[8] + 45) }}>Inteligencia de riesgo social para operaciones en territorio</div>
        <div style={{ fontSize: 34, color: C.cobre4, marginTop: 40, fontWeight: 600, opacity: tramo(f, S[8] + 45, S[8] + 65) }}>nicosil02.github.io/tremor</div>
      </div>
    </AbsoluteFill>
  );
};

// Subtítulos: trozos de 2 a 4 palabras con el tiempo real de cada una; la palabra que se dice, en cobre y con un pop
const TROZOS = PAL.map((frase) => {
  const t: [string, number, number][][] = [[]];
  frase.forEach((w) => {
    const u = t[t.length - 1];
    if (u.length >= 3 || (u.length >= 2 && /[.,?…]$/.test(u[u.length - 1][0]))) t.push([w]); else u.push(w);
  });
  return t;
});
const Subtitulo: React.FC = () => {
  const f = useCurrentFrame();
  const i = S.findIndex((s, j) => f >= s - 2 && f < s + D[j] + 4);
  if (i < 0 || i === 8) return null;
  const seg = (f - S[i]) / 30;
  let k = 0;
  TROZOS[i].forEach((t, j) => { if (seg >= t[0][1] - 0.05) k = j; });
  const trozo = TROZOS[i][k], desde = S[i] + Math.round(trozo[0][1] * 30);
  return (
    <div style={{ position: "absolute", left: 50, right: 50, bottom: 170, textAlign: "center", fontSize: 62, fontWeight: 800, letterSpacing: "-0.02em", lineHeight: 1.1,
      textShadow: "0 0 26px rgba(248,250,249,.95), 0 0 8px rgba(248,250,249,.95)" }}>
      {trozo.map(([w, a], j) => {
        const p = interpolate(f, [desde + j * 2, desde + j * 2 + 10], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: suave });
        const dicha = seg >= a - 0.03;
        const pop = interpolate(seg - a, [0, 0.08, 0.22], [1, 1.06, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
        return <span key={w + j} style={{ display: "inline-block", marginRight: "0.3em", color: dicha ? C.cobre4 : C.tinta, opacity: p,
          filter: `blur(${(1 - p) * 8}px)`, transform: `translateY(${(1 - p) * 24}px) scale(${pop})`, transformOrigin: "50% 100%" }}>{w}</span>;
      })}
    </div>
  );
};

const LUGARES = TRAMOS.map(([, , km]) => punto(km));
export const Vuelo: React.FC = () => (
  <AbsoluteFill style={{ background: C.papel, fontFamily, color: C.tinta }}>
    <Mapa3D camara={camara} preparar={preparar} cuadro={cuadro} lugares={LUGARES}>{(xy) => <Tramos xy={xy} />}</Mapa3D>
    <Bloqueo /><Costo /><Aviso /><QueEs /><Monitorea /><Telefono /><Riesgo /><Salida /><Prueba /><Cierre /><Subtitulo />
    {S.map((s, i) => <Sequence key={i} from={s}><Audio src={staticFile(`voz/${String(i).padStart(2, "0")}.wav`)} /></Sequence>)}
  </AbsoluteFill>
);
