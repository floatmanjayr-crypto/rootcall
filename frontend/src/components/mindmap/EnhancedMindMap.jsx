import React, { useMemo, useState, useEffect } from "react";
import { motion } from "framer-motion";

/* ---- theme tokens ---- */
const THEME = {
  bg: "#070B14",
  text: "#EAF6FF",
  voice: "#52E3C2",
  sms: "#7B8CFF",
  email: "#FF9B6A",
  infra: "#00FFD5",
};

/* ---- helpers ---- */
const orbit = (count, r, offset = 0) =>
  new Array(count).fill(0).map((_, i) => {
    const a = (i / count) * Math.PI * 2 + offset;
    return { x: Math.cos(a) * r, y: Math.sin(a) * r };
  });

const edgePoint = (cx, cy, tx, ty, r) => {
  const ang = Math.atan2(ty - cy, tx - cx);
  return { x: cx + Math.cos(ang) * r, y: cy + Math.sin(ang) * r };
};

/* ---- bubble ---- */
function Bubble({ x = 0, y = 0, label, icon, hub = false, draggable = false, onDragEnd }) {
  return (
    <motion.div
      style={{
        position: "absolute",
        left: `calc(50% + ${x - 72}px)`,
        top: `calc(50% + ${y - 28}px)`,
        padding: "12px 16px",
        borderRadius: 999,
        background: "rgba(255,255,255,0.08)",
        border: `1px solid rgba(82,227,194,${hub ? 0.35 : 0.22})`,
        color: THEME.text,
        fontWeight: 600,
        whiteSpace: "nowrap",
        backdropFilter: "blur(6px)",
        boxShadow: hub ? "0 0 30px rgba(82,227,194,.25)" : "0 8px 28px rgba(0,0,0,.35)",
        zIndex: 2,
        userSelect: "none",
      }}
      whileHover={{ scale: 1.05 }}
      drag={draggable}
      dragMomentum={true}
      dragElastic={0.15}
      dragConstraints={{
        left: -window.innerWidth,
        right: window.innerWidth,
        top: -window.innerHeight,
        bottom: window.innerHeight,
      }}
      onDragEnd={(e) => {
        if (!onDragEnd) return;
        const rect = e.currentTarget.getBoundingClientRect();
        const cx = window.innerWidth / 2;
        const cy = window.innerHeight / 2;
        onDragEnd({ x: rect.left + rect.width / 2 - cx, y: rect.top + rect.height / 2 - cy });
      }}
    >
      {icon ? `${icon} ` : ""}{label}
    </motion.div>
  );
}

/* ---- full-screen connector overlay ---- */
function ConnectorLayer({ center, hubs, rCenter = 70, rHub = 72 }) {
  const W = 4000, H = 4000;
  return (
    <svg
      width="100%" height="100%"
      viewBox={`${-W / 2} ${-H / 2} ${W} ${H}`}
      style={{ position: "absolute", inset: 0, zIndex: 1, pointerEvents: "none", display: "block" }}
    >
      <defs>
        <filter id="blurGlow" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur in="SourceGraphic" stdDeviation="2" />
        </filter>
      </defs>

      {hubs.map((h) => {
        const color = h.color;
        const p1 = edgePoint(center.x, center.y, h.to.x, h.to.y, rCenter);
        const p2 = edgePoint(h.to.x, h.to.y, center.x, center.y, rHub);
        const dx = p2.x - p1.x, dy = p2.y - p1.y;
        const len = Math.hypot(dx, dy) || 1;
        const nx = -dy / len, ny = dx / len;
        const curve = Math.min(64, len * 0.22);
        const cx = (p1.x + p2.x) / 2 + nx * curve;
        const cy = (p1.y + p2.y) / 2 + ny * curve;

        return (
          <g key={h.id}>
            <path d={`M ${p1.x},${p1.y} Q ${cx},${cy} ${p2.x},${p2.y}`} fill="none" stroke={`${color}66`} strokeWidth="1.2" />
            <motion.path
              d={`M ${p1.x},${p1.y} Q ${cx},${cy} ${p2.x},${p2.y}`}
              fill="none"
              stroke={color}
              strokeWidth="2.2"
              strokeDasharray="7 11"
              animate={{ strokeDashoffset: [0, -36] }}
              transition={{ repeat: Infinity, duration: 2.3, ease: "linear" }}
              style={{ filter: "url(#blurGlow)", opacity: 0.9 }}
            />
          </g>
        );
      })}
    </svg>
  );
}

/* ---- main ---- */
export default function EnhancedMindMap() {
  console.log("EnhancedMindMap v2 mounted");

  const HUBS = [
    { id: "communications", label: "Communications", icon: "í³¡", color: THEME.voice },
    { id: "automation", label: "Automation", icon: "í·©", color: THEME.sms },
    { id: "assets", label: "Assets & Provisioning", icon: "í·‚ï¸", color: THEME.email },
    { id: "insights", label: "Insights & Admin", icon: "í³ˆ", color: THEME.infra },
  ];

  const R = 240;
  const initial = useMemo(() => orbit(HUBS.length, R, Math.PI / 8), []);
  const [pos, setPos] = useState(() => Object.fromEntries(HUBS.map((h, i) => [h.id, initial[i]])));

  useEffect(() => {
    const saved = localStorage.getItem("runnerb_layout");
    if (saved) {
      try { const parsed = JSON.parse(saved); if (parsed && parsed.pos) setPos(parsed.pos); } catch {}
    }
  }, []);
  useEffect(() => {
    localStorage.setItem("runnerb_layout", JSON.stringify({ pos }));
  }, [pos]);

  const center = { x: 0, y: 0 };
  const rCore = 70, rHub = 72;
  const overlayHubs = HUBS.map(h => ({ id: h.id, to: pos[h.id], color: h.color }));

  return (
    <div style={{ position: "relative", minHeight: "88vh", background: THEME.bg, color: THEME.text, overflow: "hidden" }}>
      <div style={{
        position: "absolute", inset: 0, zIndex: 0,
        background: "radial-gradient(1000px 700px at 10% 15%, rgba(11,27,59,.35), transparent), radial-gradient(1000px 700px at 85% 80%, rgba(14,46,92,.35), transparent)"
      }}/>
      <div style={{
        position: "absolute", inset: 0, zIndex: 0, opacity: 0.35,
        backgroundImage: "radial-gradient(rgba(255,255,255,0.13) 1px, transparent 1px)",
        backgroundSize: "24px 24px"
      }}/>

      <ConnectorLayer center={center} hubs={overlayHubs} rCenter={rCore} rHub={rHub} />

      <Bubble hub icon="í· " label="Runner-B Core" x={0} y={0} />

      {HUBS.map(h => (
        <Bubble
          key={h.id}
          icon={h.icon}
          label={h.label}
          x={pos[h.id].x}
          y={pos[h.id].y}
          draggable
          onDragEnd={(p) => setPos(prev => ({ ...prev, [h.id]: p }))}
        />
      ))}

      <div style={{
        position: "absolute", right: 16, bottom: 16, zIndex: 3,
        color: "rgba(234,246,255,.8)", fontSize: 12
      }}>
        <button
          onClick={() => setPos(Object.fromEntries(HUBS.map((h, i) => [h.id, initial[i]])))}
          style={{
            padding: "8px 10px", borderRadius: 10, background: "rgba(255,255,255,0.08)",
            border: "1px solid rgba(82,227,194,0.25)", color: THEME.text
          }}
        >
          Reset layout
        </button>
      </div>
    </div>
  );
}
