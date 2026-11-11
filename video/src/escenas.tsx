import React from "react";
import { AbsoluteFill, OffthreadVideo, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { C, Punto, Rotulo, fontFamily, miles, mueve, sobre, tramo, trazo } from "./comun";
import datos from "./datos.json";

const base: React.CSSProperties = { background: C.papel, fontFamily, color: C.tinta, overflow: "hidden" };
const Entra: React.FC<{ children: React.ReactNode; fondo?: string }> = ({ children, fondo }) => {
  const f = useCurrentFrame();
  return <AbsoluteFill style={{ ...base, background: fondo ?? C.papel, opacity: tramo(f, 0, 8) }}>{children}</AbsoluteFill>;
};

// Calles de fondo, muy suaves, para que el papel parezca un mapa
const Calles: React.FC<{ op?: number }> = ({ op = 1 }) => (
  <svg width={1080} height={1920} style={{ position: "absolute", inset: 0, opacity: op }}>
    {[...Array(14)].map((_, i) => <path key={i} d={`M-50 ${120 + i * 140} C 300 ${80 + i * 140}, 700 ${200 + i * 140}, 1150 ${130 + i * 140}`} stroke={C.piedra} strokeWidth={i % 3 ? 6 : 14} fill="none" />)}
    {[...Array(8)].map((_, i) => <path key={"v" + i} d={`M${60 + i * 150} -50 C ${20 + i * 150} 600, ${120 + i * 150} 1300, ${70 + i * 150} 1980`} stroke={C.piedra} strokeWidth={i % 2 ? 5 : 10} fill="none" />)}
  </svg>
);

/* 1. La pregunta en la barra de búsqueda */
export const Pregunta: React.FC = () => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const texto = "¿Habrá un bloqueo en mi ruta esta semana?";
  const n = Math.floor(interpolate(f, [24, 96], [0, texto.length], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }));
  const s = spring({ frame: f - 4, fps, config: { damping: 14 } });
  const zoom = 1 + tramo(f, 118, 150, mueve) * 0.9;
  return (
    <Entra>
      <AbsoluteFill style={{ transform: `scale(${zoom})`, opacity: 1 - tramo(f, 135, 150) }}>
        <Calles />
        <div style={{ position: "absolute", left: 0, right: 0, top: 560, display: "flex", justifyContent: "center", transform: `scale(${s})` }}><Punto r={30} f={f} /></div>
        <div style={{ position: "absolute", left: 70, right: 70, top: 820, height: 150, borderRadius: 75, background: "#fff",
          boxShadow: "0 30px 60px -20px rgba(42,26,18,.25), 0 0 0 2px #e6eaea", display: "flex", alignItems: "center", gap: 28, padding: "0 36px",
          transform: `translateY(${(1 - s) * 60}px)`, opacity: s }}>
          <div style={{ width: 30, height: 30, borderRadius: "50%", background: C.cobre, flex: "none" }} />
          <div style={{ fontSize: 37, fontWeight: 500, whiteSpace: "nowrap", overflow: "hidden" }}>
            {texto.slice(0, n)}<span style={{ opacity: f % 30 < 15 ? 1 : 0, color: C.cobre }}>|</span>
          </div>
        </div>
      </AbsoluteFill>
    </Entra>
  );
};

/* 2. La carretera en 3D: los camiones se detienen y suben el tiempo y la pérdida */
const CARRETERA = [[700, 2600], [640, 2250], [830, 1950], [590, 1620], [770, 1300], [560, 980], [740, 680], [610, 330], [700, 0]];
const Camion: React.FC<{ x: number; y: number; ang: number; color: string }> = ({ x, y, ang, color }) => (
  <div style={{ position: "absolute", left: x - 22, top: y - 46, width: 44, height: 92, transform: `rotateZ(${ang - 90}deg)`, transformStyle: "preserve-3d" }}>
    <div style={{ position: "absolute", inset: 0, background: "rgba(42,26,18,.18)", borderRadius: 6, transform: "translate(10px, 8px)" }} />
    <div style={{ position: "absolute", inset: 0, borderRadius: 6, background: "#fff", transform: "translateZ(30px)", boxShadow: "0 0 0 2px #d9dfde" }}>
      <div style={{ position: "absolute", left: 4, right: 4, top: 4, height: 24, borderRadius: 4, background: color }} />
    </div>
  </div>
);
export const Bloqueo: React.FC = () => {
  const f = useCurrentFrame();
  const parada = 0.52, desde = 40;
  const camY = interpolate(f, [0, 210], [-200, 200]);
  const horas = 72 * tramo(f, 50, 195, (t) => t);
  const camiones = [0, 1, 2, 3, 4, 5].map((i) => {
    const t = Math.min(0.08 + i * -0.07 + f * 0.0032, parada - 0.045 * i);
    return { ...sobre(CARRETERA, t), i };
  });
  const corte = sobre(CARRETERA, parada + 0.03);
  const aviso = tramo(f, desde, desde + 18);
  return (
    <Entra fondo="#eef1ef">
      <AbsoluteFill style={{ perspective: 1800 }}>
        <div style={{ position: "absolute", left: -160, top: -420, width: 1400, height: 2600, transformStyle: "preserve-3d",
          transform: `rotateX(56deg) rotateZ(${-28 + f * 0.02}deg) translateY(${camY}px)` }}>
          <svg width={1400} height={2600} style={{ position: "absolute", inset: 0 }}>
            {[...Array(16)].map((_, i) => <path key={i} d={`M0 ${i * 170} C 400 ${i * 170 - 120}, 900 ${i * 170 + 140}, 1400 ${i * 170 - 40}`} stroke="#dfe5e3" strokeWidth={3} fill="none" />)}
            <path d={trazo(CARRETERA)} stroke="#cfd6d5" strokeWidth={120} fill="none" strokeLinejoin="round" />
            <path d={trazo(CARRETERA)} stroke="#fff" strokeWidth={6} strokeDasharray="30 30" fill="none" />
          </svg>
          {camiones.map((c) => <Camion key={c.i} x={c.x} y={c.y} ang={c.ang} color={c.i % 2 ? C.gris : C.cobre} />)}
          <div style={{ position: "absolute", left: corte.x - 80, top: corte.y - 20, width: 160, height: 40, transform: `translateZ(${20 * aviso}px) rotateZ(${corte.ang + 90}deg)`,
            background: `repeating-linear-gradient(45deg, ${C.rojo} 0 18px, #fff 18px 36px)`, borderRadius: 6, opacity: aviso }} />
          <div style={{ position: "absolute", left: corte.x - 120, top: corte.y - 120, width: 240, height: 240, borderRadius: "50%", border: `6px solid ${C.rojo}`,
            opacity: aviso * (1 - ((f % 40) / 40)), transform: `scale(${0.5 + ((f % 40) / 40)})` }} />
        </div>
      </AbsoluteFill>
      <div style={{ position: "absolute", left: 70, right: 70, top: 150, display: "grid", gridTemplateColumns: "1fr 1.35fr", gap: 24, opacity: tramo(f, 50, 70) }}>
        {[["Tiempo detenido", `${Math.floor(horas)} h`], ["Ventas que no entran", `US$${miles(horas * 15583)}`]].map(([k, v]) => (
          <div key={k} style={{ background: "rgba(255,255,255,.92)", borderRadius: 28, padding: "26px 30px", boxShadow: "0 20px 50px -20px rgba(42,26,18,.3)" }}>
            <div style={{ fontSize: 30, fontWeight: 600, color: C.tinta2 }}>{k}</div>
            <div style={{ fontSize: 64, fontWeight: 800, color: C.cobre4, letterSpacing: -2, fontVariantNumeric: "tabular-nums" }}>{v}</div>
          </div>
        ))}
      </div>
      <Rotulo lineas={[[30, "Bloqueo en la ruta"], [150, "Cada hora cuenta"]]} />
    </Entra>
  );
};

/* 3. Alertas: radios y diarios emiten, Tremor escucha y se vuelve un aviso */
const FUENTES = [...Array(6)].map((_, i) => { const a = -Math.PI / 2 + i * Math.PI / 3; return { x: 540 + 330 * Math.cos(a), y: 610 + 300 * Math.sin(a), radio: i % 2 === 0 }; });
const Radio: React.FC = () => (
  <svg width={70} height={70} viewBox="0 0 70 70"><path d="M35 30 L20 66 M35 30 L50 66 M25 54 H45" stroke={C.tinta} strokeWidth={5} fill="none" strokeLinecap="round" /><circle cx={35} cy={24} r={8} fill={C.cobre} /></svg>
);
const Diario: React.FC = () => (
  <svg width={70} height={70} viewBox="0 0 70 70"><rect x={10} y={12} width={50} height={46} rx={6} fill="#fff" stroke={C.tinta} strokeWidth={5} /><path d="M20 26 H50 M20 36 H50 M20 46 H38" stroke={C.cobre} strokeWidth={5} strokeLinecap="round" /></svg>
);
export const Alertas: React.FC = () => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const lenguas = ["Castellano", "Quechua", "Aimara"];
  const tarjeta = spring({ frame: f - 190, fps, config: { damping: 15 } });
  return (
    <Entra>
      <Calles op={0.6} />
      <svg width={1080} height={1920} style={{ position: "absolute", inset: 0 }}>
        {FUENTES.map((p, i) => {
          const a = tramo(f, 10 + i * 6, 30 + i * 6);
          const viaje = ((f - 60 - i * 9) % 50) / 50;
          return (
            <g key={i}>
              <line x1={p.x} y1={p.y} x2={540} y2={610} stroke={C.cobre2} strokeWidth={4} strokeDasharray="10 12" opacity={a * tramo(f, 50, 70)} />
              {[0, 1, 2].map((k) => { const r = ((f + k * 15 + i * 7) % 45) / 45; return <circle key={k} cx={p.x} cy={p.y} r={40 + r * 110} fill="none" stroke={C.cobre} strokeWidth={3} opacity={a * 0.5 * (1 - r)} />; })}
              {f > 60 + i * 9 && <circle cx={p.x + (540 - p.x) * viaje} cy={p.y + (610 - p.y) * viaje} r={11} fill={C.cobre} />}
            </g>
          );
        })}
      </svg>
      {FUENTES.map((p, i) => (
        <div key={i} style={{ position: "absolute", left: p.x - 55, top: p.y - 55, width: 110, height: 110, borderRadius: "50%", background: "#fff", display: "grid", placeItems: "center",
          boxShadow: "0 16px 40px -14px rgba(42,26,18,.35)", transform: `scale(${tramo(f, 10 + i * 6, 30 + i * 6)})` }}>{p.radio ? <Radio /> : <Diario />}</div>
      ))}
      <div style={{ position: "absolute", left: 540 - 70, top: 610 - 70, width: 140, height: 140, borderRadius: "50%", background: C.pardo, display: "grid", placeItems: "center",
        boxShadow: `0 0 0 ${10 + 6 * Math.sin(f / 6)}px rgba(180,84,42,.18)` }}><Punto r={22} f={f} /></div>
      <div style={{ position: "absolute", left: 80, right: 80, top: 1000, display: "flex", justifyContent: "center", gap: 70, opacity: tramo(f, 40, 60) }}>
        {[[286, "radios"], [407, "medios"]].map(([n, k]) => (
          <div key={k as string} style={{ textAlign: "center" }}>
            <div style={{ fontSize: 110, fontWeight: 800, letterSpacing: -4, color: C.cobre4, fontVariantNumeric: "tabular-nums" }}>{Math.round((n as number) * tramo(f, 40, 110))}</div>
            <div style={{ fontSize: 40, fontWeight: 600, color: C.tinta2, marginTop: -10 }}>{k}</div>
          </div>
        ))}
      </div>
      <div style={{ position: "absolute", left: 0, right: 0, top: 1210, display: "flex", justifyContent: "center", gap: 18 }}>
        {lenguas.map((l, i) => { const on = tramo(f, 115 + i * 14, 130 + i * 14); return (
          <div key={l} style={{ fontSize: 38, fontWeight: 650, padding: "14px 30px", borderRadius: 999, opacity: tramo(f, 100, 115),
            background: on ? `rgba(180,84,42,${on})` : "#fff", color: on > 0.5 ? "#fff" : C.tinta, boxShadow: "0 0 0 2px #dfe5e4" }}>{l}</div>); })}
      </div>
      <div style={{ position: "absolute", left: 70, right: 70, top: 1340, background: "#fff", borderRadius: 32, padding: "34px 40px", boxShadow: "0 40px 80px -30px rgba(42,26,18,.4)",
        transform: `translateY(${(1 - tarjeta) * 500}px)`, opacity: tarjeta }}>
        <div style={{ display: "flex", justifyContent: "space-between", fontSize: 30, color: C.tinta2, fontWeight: 600 }}><span>Radio local · 6:40 a. m.</span>
          <span style={{ color: "#fff", background: C.cobre, borderRadius: 999, padding: "4px 18px" }}>Paro anunciado</span></div>
        <div style={{ fontSize: 50, fontWeight: 750, lineHeight: 1.12, marginTop: 16, letterSpacing: -1 }}>Convocan paro de 48 horas en la provincia desde el lunes</div>
      </div>
      <Rotulo lineas={[[0, "Se anuncia antes"], [150, "Tremor lo escucha"]]} abajo={1650} />
    </Entra>
  );
};

/* 4. Seguimiento: menciones por semana y tono */
export const Seguimiento: React.FC = () => {
  const f = useCurrentFrame();
  const semanas = [4, 6, 3, 5, 4, 7, 5, 6, 15];
  const aguja = interpolate(tramo(f, 90, 150, mueve), [0, 1], [50, 86]);
  return (
    <Entra>
      <Calles op={0.5} />
      <div style={{ position: "absolute", left: 70, right: 70, top: 300, background: "#fff", borderRadius: 40, padding: "48px 50px", boxShadow: "0 40px 90px -30px rgba(42,26,18,.35)" }}>
        <div style={{ fontSize: 34, color: C.tinta2, fontWeight: 600 }}>Su proyecto en prensa y radio</div>
        <div style={{ display: "flex", alignItems: "baseline", gap: 20, marginTop: 6 }}>
          <span style={{ fontSize: 120, fontWeight: 800, color: C.cobre4, letterSpacing: -5 }}>+{Math.round(180 * tramo(f, 40, 100))}%</span>
          <span style={{ fontSize: 36, fontWeight: 600 }}>menciones esta semana</span>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(9, 1fr)", gap: 14, alignItems: "end", height: 420, marginTop: 30, borderBottom: `4px solid ${C.tinta}` }}>
          {semanas.map((n, i) => <div key={i} style={{ height: `${(n / 15) * 100 * tramo(f, 10 + i * 6, 40 + i * 6 + (i === 8 ? 30 : 0))}%`, borderRadius: "10px 10px 0 0", background: i === 8 ? C.cobre : C.gris }} />)}
        </div>
        <div style={{ marginTop: 56, fontSize: 34, fontWeight: 600, color: C.tinta2 }}>Tono</div>
        <div style={{ position: "relative", height: 28, borderRadius: 14, marginTop: 16, background: `linear-gradient(90deg, ${C.verde}, ${C.linea} 50%, ${C.cobre})` }}>
          <div style={{ position: "absolute", left: `${aguja}%`, top: -14, width: 56, height: 56, marginLeft: -28, borderRadius: "50%", background: "#fff", border: `8px solid ${C.tinta}` }} />
        </div>
        <div style={{ display: "flex", justifyContent: "space-between", fontSize: 30, color: C.tinta2, marginTop: 22 }}><span>Positivo</span><span>Negativo</span></div>
      </div>
      <Rotulo lineas={[[10, "Cuánto se habla"], [110, "Y en qué tono"]]} abajo={200} />
    </Entra>
  );
};

/* 5. Predicción: el país, el riesgo por zona y el acercamiento a una operación */
const pseudo = (i: number) => { const x = Math.sin(i * 12.9898) * 43758.5453; return x - Math.floor(x); };
export const Prediccion: React.FC = () => {
  const f = useCurrentFrame();
  const E = 0.86, X0 = (1080 - 1000 * E) / 2, Y0 = 230;
  const [mx, my] = (datos.ruta as Record<string, number[][]>)["Mina a Callalli"][0];
  const z = tramo(f, 130, 200, mueve);
  const esc = 1 + z * 2.4;
  const tx = (540 - (X0 + mx * E)) * z, ty = (820 - (Y0 + my * E)) * z;
  const ficha = tramo(f, 190, 215);
  const pct = Math.round(33 * tramo(f, 195, 250));
  return (
    <Entra>
      <AbsoluteFill style={{ transform: `translate(${tx}px, ${ty}px) scale(${esc})`, transformOrigin: `${X0 + mx * E}px ${Y0 + my * E}px` }}>
        <svg width={1080} height={1920} style={{ position: "absolute", inset: 0 }}>
          <g transform={`translate(${X0} ${Y0}) scale(${E})`}>
            <path d={trazo(datos.peru) + "Z"} fill="#fff" stroke={C.linea} strokeWidth={3} />
            {datos.operaciones.map(([x, y], i) => {
              const r = pseudo(i), on = tramo(f, 30 + r * 60, 50 + r * 60);
              const col = r > 0.93 ? C.cobre4 : r > 0.8 ? C.cobre : r > 0.5 ? C.cobre2 : C.cobre1;
              return <circle key={i} cx={x} cy={y} r={5 + (r > 0.8 ? 3 : 0)} fill={on ? col : C.gris} opacity={0.4 + on * 0.6} />;
            })}
            <circle cx={mx} cy={my} r={14 + 10 * ((f % 40) / 40)} fill="none" stroke={C.cobre4} strokeWidth={3} opacity={z} />
          </g>
        </svg>
      </AbsoluteFill>
      <div style={{ position: "absolute", left: 70, right: 70, top: 1080, background: "#fff", borderRadius: 36, padding: "40px 46px", boxShadow: "0 40px 90px -30px rgba(42,26,18,.4)",
        opacity: ficha, transform: `translateY(${(1 - ficha) * 80}px)` }}>
        <div style={{ fontSize: 34, color: C.tinta2, fontWeight: 600 }}>Su operación · próximos 3 meses</div>
        <div style={{ display: "flex", alignItems: "baseline", gap: 24 }}>
          <span style={{ fontSize: 150, fontWeight: 800, color: C.cobre4, letterSpacing: -6 }}>{pct}%</span>
          <span style={{ fontSize: 40, fontWeight: 700, color: "#fff", background: C.cobre, borderRadius: 999, padding: "6px 24px" }}>Alto</span>
        </div>
        <div style={{ fontSize: 34, color: C.tinta2 }}>de un paro o bloqueo contra la operación</div>
      </div>
      <Rotulo lineas={[[10, "El riesgo de cada zona"], [205, "A tres meses"]]} abajo={170} />
    </Entra>
  );
};

/* 6. Ruta: la ruta real de Bateas, tramo por tramo */
const TRAMOS: [string, number][] = [["Mina a Callalli", 9], ["Bajada a Arequipa", 29], ["Puerto de Matarani, zinc", 29], ["Panamericana Sur al Callao, plomo", 25]];
export const Ruta: React.FC = () => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const R = datos.ruta as Record<string, number[][]>;
  const lineas = TRAMOS.map(([k]) => (k.startsWith("Panamericana") ? R[k].slice(0, 70) : R[k]));
  const todos = lineas.flat();
  const xs = todos.map((p) => p[0]), ys = todos.map((p) => p[1]);
  const [x0, x1, y0, y1] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
  const k = Math.min(860 / (x1 - x0), 900 / (y1 - y0));
  const P = (p: number[]) => [110 + (p[0] - x0) * k, 330 + (p[1] - y0) * k];
  const banner = spring({ frame: f - 150, fps, config: { damping: 14 } });
  const camion = sobre(lineas[1].map(P), tramo(f, 140, 225, (t) => t));
  return (
    <Entra>
      <Calles op={0.7} />
      <AbsoluteFill style={{ perspective: 1600 }}>
        <div style={{ position: "absolute", inset: 0, transform: `rotateX(${32 - 10 * tramo(f, 0, 230, mueve)}deg) scale(${1.05 + 0.08 * tramo(f, 140, 230)})`, transformOrigin: "50% 60%" }}>
          <svg width={1080} height={1920} style={{ position: "absolute", inset: 0 }}>
            <path d={trazo(datos.peru.map(P)) + "Z"} fill="#fff" stroke={C.linea} strokeWidth={4} opacity={0.9} />
            {lineas.slice(1).map((l, i) => { const [a, b] = [P(lineas[i][lineas[i].length - 1]), P(l[0])]; return (
              <line key={"u" + i} x1={a[0]} y1={a[1]} x2={b[0]} y2={b[1]} stroke={C.gris} strokeWidth={6} strokeDasharray="4 14" strokeLinecap="round" opacity={tramo(f, 40 + i * 30, 60 + i * 30)} />); })}
            {lineas.map((l, i) => {
              const d = trazo(l.map(P)), largo = sobre(l.map(P), 1).total;
              const a = tramo(f, 10 + i * 30, 50 + i * 30, mueve);
              const col = TRAMOS[i][1] >= 25 ? C.cobre : C.cobre2;
              const foco = i === 1 ? tramo(f, 150, 170) : 0;
              return (
                <g key={i}>
                  <path d={d} stroke="#fff" strokeWidth={30 + foco * 10} fill="none" strokeLinecap="round" strokeLinejoin="round" strokeDasharray={largo} strokeDashoffset={largo * (1 - a)} />
                  <path d={d} stroke={col} strokeWidth={16 + foco * 10} fill="none" strokeLinecap="round" strokeLinejoin="round" strokeDasharray={largo} strokeDashoffset={largo * (1 - a)} />
                </g>
              );
            })}
            {f > 150 && <circle cx={camion.x} cy={camion.y} r={20} fill={C.tinta} stroke="#fff" strokeWidth={6} />}
          </svg>
          {lineas.map((l, i) => { const m = sobre(l.map(P), 0.5); const a = tramo(f, 40 + i * 30, 60 + i * 30); return (
            <div key={i} style={{ position: "absolute", left: m.x + 24, top: m.y - 34, fontSize: 40, fontWeight: 800, background: "#fff", color: TRAMOS[i][1] >= 25 ? C.cobre4 : C.tinta,
              borderRadius: 16, padding: "6px 18px", boxShadow: "0 10px 30px -10px rgba(42,26,18,.4)", opacity: a, transform: `scale(${0.8 + a * 0.2})` }}>{TRAMOS[i][1]}%</div>); })}
        </div>
      </AbsoluteFill>
      <div style={{ position: "absolute", left: 60, right: 60, top: 120, background: C.verde, color: "#fff", borderRadius: 30, padding: "30px 38px", display: "flex", alignItems: "center", gap: 28,
        transform: `translateY(${(1 - banner) * -260}px)` }}>
        <svg width={70} height={70} viewBox="0 0 70 70"><path d="M20 60 V30 Q20 20 30 20 H52 M42 10 L54 20 L42 30" stroke="#fff" strokeWidth={7} fill="none" strokeLinecap="round" strokeLinejoin="round" /></svg>
        <div style={{ flex: 1 }}><div style={{ fontSize: 50, fontWeight: 800 }}>Bajada a Arequipa</div><div style={{ fontSize: 32, opacity: 0.85 }}>Riesgo de corte en 3 meses</div></div>
        <div style={{ fontSize: 76, fontWeight: 800 }}>29%</div>
      </div>
      <Rotulo lineas={[[10, "Su ruta de salida"], [150, "Tramo por tramo"]]} abajo={180} />
    </Entra>
  );
};

/* 7. El aviso llega al teléfono */
const Notificacion: React.FC<{ titulo: string; texto: string; desde: number; urgente?: boolean }> = ({ titulo, texto, desde, urgente }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({ frame: f - desde, fps, config: { damping: 13 } });
  return (
    <div style={{ background: "rgba(255,255,255,.96)", borderRadius: 34, padding: "26px 28px", boxShadow: "0 20px 40px -16px rgba(0,0,0,.35)", display: "flex", gap: 22,
      transform: `translateY(${(1 - s) * -180}px) scale(${0.92 + s * 0.08})`, opacity: s, marginBottom: 18 }}>
      <div style={{ width: 64, height: 64, borderRadius: 16, background: urgente ? C.cobre : C.pardo, display: "grid", placeItems: "center", flex: "none" }}>
        <div style={{ width: 22, height: 22, borderRadius: "50%", background: urgente ? "#fff" : C.cobre }} /></div>
      <div><div style={{ fontSize: 26, color: C.tinta2, fontWeight: 600 }}>TREMOR · ahora</div>
        <div style={{ fontSize: 34, fontWeight: 800, marginTop: 2 }}>{titulo}</div>
        <div style={{ fontSize: 28, color: C.tinta2, lineHeight: 1.3, marginTop: 4 }}>{texto}</div></div>
    </div>
  );
};
export const Aviso: React.FC = () => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const tel = spring({ frame: f, fps, config: { damping: 16 } });
  return (
    <Entra fondo={C.piedra}>
      <div style={{ position: "absolute", left: 200, top: 190, width: 680, height: 1380, borderRadius: 90, background: C.tinta, padding: 22,
        transform: `translateY(${(1 - tel) * 400}px) rotate(${(1 - tel) * -6}deg)`, boxShadow: "0 60px 120px -40px rgba(42,26,18,.6)" }}>
        <div style={{ position: "relative", width: "100%", height: "100%", borderRadius: 70, overflow: "hidden", background: `linear-gradient(170deg, #f1e5dc, #e3a67c 60%, #8a3213)` }}>
          <div style={{ textAlign: "center", color: "#fff", marginTop: 120, fontSize: 130, fontWeight: 300, letterSpacing: -4 }}>6:52</div>
          <div style={{ textAlign: "center", color: "#fff", fontSize: 32, opacity: 0.9 }}>lunes</div>
          <div style={{ position: "absolute", left: 22, right: 22, top: 430 }}>
            <Notificacion desde={35} urgente titulo="Paro anunciado en su ruta" texto="Bajada a Arequipa, desde el lunes por 48 horas. Fuente: radio local." />
            <Notificacion desde={110} titulo="Vía interrumpida" texto="La SUTRAN reporta un bloqueo vigente en el tramo." />
          </div>
        </div>
      </div>
      <Rotulo lineas={[[20, "El aviso llega"], [100, "A su teléfono"]]} abajo={110} />
    </Entra>
  );
};

/* 8. La plataforma real */
export const Plataforma: React.FC = () => {
  const f = useCurrentFrame();
  const a = tramo(f, 0, 50, mueve);
  return (
    <Entra fondo={C.pardo}>
      <AbsoluteFill style={{ perspective: 1800 }}>
        <div style={{ position: "absolute", left: 40, right: 40, top: 520, transform: `rotateX(${(1 - a) * 28}deg) scale(${0.85 + a * 0.15})`, transformOrigin: "50% 100%" }}>
          <div style={{ background: "#111", borderRadius: "28px 28px 0 0", padding: 18 }}>
            <OffthreadVideo src={staticFile("recorrido.mp4")} trimBefore={117} muted style={{ width: "100%", display: "block", borderRadius: 10 }} />
          </div>
          <div style={{ height: 34, background: "linear-gradient(#cfd4d3, #9aa3a2)", borderRadius: "0 0 40px 40px", margin: "0 -30px" }} />
        </div>
      </AbsoluteFill>
      <Rotulo claro lineas={[[10, "Todo en una plataforma"]]} abajo={330} />
    </Entra>
  );
};

/* 9. Cierre */
export const Cierre: React.FC = () => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({ frame: f - 10, fps, config: { damping: 15 } });
  const E = 0.7, X0 = (1080 - 700) / 2, Y0 = 120;
  return (
    <Entra>
      <svg width={1080} height={1920} style={{ position: "absolute", inset: 0, opacity: 0.55 }}>
        <g transform={`translate(${X0} ${Y0}) scale(${E})`}>
          <path d={trazo(datos.peru) + "Z"} fill="#fff" stroke={C.linea} strokeWidth={3} />
          {datos.operaciones.filter((_, i) => i % 3 === 0).map(([x, y], i) => { const k = ((f + i * 7) % 60) / 60; return <circle key={i} cx={x} cy={y} r={4 + k * 8} fill={C.cobre} opacity={0.8 - k * 0.8} />; })}
        </g>
      </svg>
      <div style={{ position: "absolute", left: 80, right: 80, top: 1180, textAlign: "center", opacity: s, transform: `translateY(${(1 - s) * 50}px)` }}>
        <div style={{ display: "inline-flex", alignItems: "center", gap: 30 }}><Punto r={34} f={f} /><span style={{ fontSize: 150, fontWeight: 800, letterSpacing: -5 }}>Tremor</span></div>
        <div style={{ fontSize: 50, fontWeight: 600, color: C.tinta2, lineHeight: 1.2, marginTop: 24, opacity: tramo(f, 30, 50) }}>Inteligencia de riesgo social para operaciones en territorio</div>
        <div style={{ fontSize: 34, color: C.cobre4, marginTop: 40, fontWeight: 600, opacity: tramo(f, 50, 70) }}>nicosil02.github.io/tremor</div>
      </div>
    </Entra>
  );
};
