import React, { useEffect, useRef, useState } from "react";
import { useCurrentFrame, useDelayRender, useVideoConfig } from "remotion";
import * as maplibregl from "maplibre-gl";
import type { Map as Mapa, StyleSpecification } from "maplibre-gl";
import * as turf from "@turf/turf";
import "maplibre-gl/dist/maplibre-gl.css";
import geo from "./geo.json";

// Relieve real (teselas públicas de elevación de AWS, sin clave) y vías y ríos de OpenFreeMap, pintados con la paleta
// de Tremor: papel, piedra y cobre. Sin rótulos del mapa: los textos los pone el video.
const DEM = { type: "raster-dem" as const, tiles: ["https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"],
  encoding: "terrarium" as const, tileSize: 256, maxzoom: 12, attribution: "Mapzen, AWS" };
const ESTILO: StyleSpecification = {
  version: 8,
  sources: { omt: { type: "vector", url: "https://tiles.openfreemap.org/planet" }, dem: DEM, sombra: DEM },
  sky: { "sky-color": "#f8faf9", "horizon-color": "#f3e1d3", "fog-color": "#f4f1ee", "sky-horizon-blend": 0.7, "horizon-fog-blend": 0.6, "fog-ground-blend": 0.25 },
  layers: [
    { id: "fondo", type: "background", paint: { "background-color": "#efeeea" } },
    { id: "sombra", type: "hillshade", source: "sombra", paint: { "hillshade-exaggeration": 0.75, "hillshade-shadow-color": "#9c8a7e",
      "hillshade-highlight-color": "#ffffff", "hillshade-accent-color": "#c8b6a8", "hillshade-illumination-direction": 315 } },
    { id: "agua", type: "fill", source: "omt", "source-layer": "water", paint: { "fill-color": "#cfdfe3" } },
    { id: "rios", type: "line", source: "omt", "source-layer": "waterway", paint: { "line-color": "#bcd3d9", "line-width": 1.5 } },
    { id: "pais", type: "line", source: "omt", "source-layer": "boundary", filter: ["==", ["get", "admin_level"], 2], paint: { "line-color": "#8d9a99", "line-width": 1.5, "line-dasharray": [3, 2] } },
    { id: "vias", type: "line", source: "omt", "source-layer": "transportation", filter: ["in", ["get", "class"], ["literal", ["primary", "trunk", "motorway", "secondary"]]],
      paint: { "line-color": "#ffffff", "line-width": ["interpolate", ["linear"], ["zoom"], 6, 1, 12, 5] } },
  ],
};

export const CAMINO = turf.lineString(geo.camino);
export const LARGO = turf.length(CAMINO);
export const punto = (km: number) => turf.along(CAMINO, Math.max(0, Math.min(LARGO, km))).geometry.coordinates as [number, number];

export type Camara = { centro: [number, number]; zoom: number; pitch: number; rumbo: number };
type XY = { x: number; y: number } | null;
type Props = {
  camara: (f: number) => Camara;
  preparar?: (m: Mapa) => void;            // capas propias, una vez
  cuadro?: (m: Mapa, f: number) => void;   // datos y pintura de cada cuadro
  lugares?: [number, number][];            // puntos que el video necesita en pantalla
  children?: (xy: XY[]) => React.ReactNode;
};

export const Mapa3D: React.FC<Props> = ({ camara, preparar, cuadro, lugares = [], children }) => {
  const caja = useRef<HTMLDivElement>(null);
  const f = useCurrentFrame();
  const { width, height } = useVideoConfig();
  const { delayRender, continueRender } = useDelayRender();
  const [mapa, setMapa] = useState<Mapa | null>(null);
  const [xy, setXy] = useState<XY[]>([]);
  const [espera] = useState(() => delayRender("Cargando el mapa", { timeoutInMilliseconds: 120000 }));

  const mover = (m: Mapa, k: number) => {
    const c = camara(k);
    m.jumpTo({ center: c.centro, zoom: c.zoom, pitch: c.pitch, bearing: c.rumbo });
    cuadro?.(m, k);
  };
  const medir = (m: Mapa) => setXy(lugares.map((p) => { const q = m.project(p); return q.x > -400 && q.x < width + 400 && q.y > -400 && q.y < height + 400 ? { x: q.x, y: q.y } : null; }));

  useEffect(() => {
    if (!caja.current) return;
    maplibregl.setWorkerUrl(URL.createObjectURL(new Blob([`import "https://unpkg.com/maplibre-gl@${maplibregl.getVersion()}/dist/maplibre-gl-worker.mjs";`], { type: "text/javascript" })));
    const c = camara(f);
    const m = new maplibregl.Map({ container: caja.current, style: ESTILO, center: c.centro, zoom: c.zoom, pitch: c.pitch, bearing: c.rumbo, maxPitch: 85,
      interactive: false, attributionControl: false, fadeDuration: 0, canvasContextAttributes: { preserveDrawingBuffer: true } });
    m.on("load", () => {
      m.setTerrain({ source: "dem", exaggeration: 1.6 });
      preparar?.(m);
      mover(m, f);
      m.once("idle", () => { medir(m); setMapa(m); continueRender(espera); });
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!mapa) return;
    const h = delayRender("Cuadro del mapa", { timeoutInMilliseconds: 120000 });
    mover(mapa, f);
    mapa.once("idle", () => { medir(mapa); continueRender(h); });
    mapa.triggerRepaint();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [f, mapa]);

  return <><div ref={caja} style={{ position: "absolute", width, height }} />{children?.(xy)}</>;
};
