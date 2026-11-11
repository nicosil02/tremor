import React from "react";
import { Composition } from "remotion";
import { TOTAL as TOTAL3D, Vuelo } from "./Vuelo";

export const RemotionRoot: React.FC = () => (
  <>
  <Composition id="Vuelo" component={Vuelo} durationInFrames={TOTAL3D} fps={30} width={1080} height={1920} />
  </>
);
