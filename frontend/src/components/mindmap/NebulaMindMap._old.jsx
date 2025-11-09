import React, { useMemo, useState } from "react";
import Bubble from "./Bubble";
import ConnectorOverlay from "./Connector";

const HUBS = [
  { id: "communications", label: "Communications", icon: "í³¡", channel: "voice" },
  { id: "automation",     label: "Automation",     icon: "í·©", channel: "voice" },
  { id: "assets",         label: "Assets",         icon: "í·‚ï¸", channel: "infra" },
  { id: "insights",       label: "Insights",       icon: "í³ˆ", channel: "infra" },
];

const orbit = (count, r, offset=0) =>
  new Array(count).fill(0).map((_, i) => {
    const a = (i / count) * Math.PI * 2 + offset;
    return { x: Math.cos(a) * r, y: Math.sin(a) * r };
  });

export default function NebulaMindMap(){
  const R = 220;
  const hubInit = useMemo(()=>orbit(HUBS.length, R, Math.PI/8),[]);
  const [pos, setPos] = useState(() => {
    const m = {}; HUBS.forEach((h, i) => (m[h.id] = hubInit[i])); return m;
  });

  const CORE_R = 60;
  const HUB_R  = 60;

  const overlayHubs = HUBS.map(h => ({
    to: pos[h.id], channel: h.channel, rTo: HUB_R
  }));

  const updateHub = (id, p) => setPos(prev => ({ ...prev, [id]: p }));

  return (
    <div style={{ position:"relative", minHeight:"80vh", background:"#070B14", color:"#EAF6FF" }}>
      {/* dotted bg */}
      <div style={{
        position:"absolute", inset:0, opacity:.35, zIndex:0,
        backgroundImage:"radial-gradient(rgba(255,255,255,0.12) 1px, transparent 1px)",
        backgroundSize:"24px 24px"
      }}/>

      {/* FULL-SCREEN CONNECTORS */}
      <ConnectorOverlay center={{x:0,y:0}} hubs={overlayHubs} rCenter={CORE_R} />

      {/* center bubble (above connectors) */}
      <Bubble hub icon="í· " label="Runner-B Core" x={-60} y={-24} />

      {/* hubs (draggable, above connectors) */}
      {HUBS.map(h => (
        <Bubble
          key={h.id}
          x={pos[h.id].x}
          y={pos[h.id].y}
          label={h.label}
          icon={h.icon}
          draggable
          onDragEnd={(p)=>updateHub(h.id, p)}
        />
      ))}
    </div>
  );
}
