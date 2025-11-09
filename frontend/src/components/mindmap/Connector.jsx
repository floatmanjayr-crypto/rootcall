import React from "react";

const COLOR = {
  voice: "#52E3C2",
  sms:   "#7B8CFF",
  email: "#FF9B6A",
  infra: "#00FFD5",
};

function edgePoint(cx, cy, tx, ty, r) {
  const ang = Math.atan2(ty - cy, tx - cx);
  return { x: cx + Math.cos(ang) * r, y: cy + Math.sin(ang) * r };
}

export default function ConnectorOverlay({
  center = { x:0, y:0 },
  hubs = [],              // [{ to:{x,y}, channel, rTo }]
  rCenter = 60
}) {
  const W = 4000, H = 4000;

  const paths = hubs.map((h, i) => {
    const color = COLOR[h.channel] || COLOR.voice;
    const p1 = edgePoint(center.x, center.y, h.to.x, h.to.y, rCenter);
    const p2 = edgePoint(h.to.x, h.to.y, center.x, center.y, h.rTo ?? 60);

    // curve control point
    const dx = p2.x - p1.x, dy = p2.y - p1.y;
    const len = Math.hypot(dx, dy) || 1;
    const nx = -dy / len, ny = dx / len;
    const curve = Math.min(64, len * 0.2);
    const cx = (p1.x + p2.x) / 2 + nx * curve;
    const cy = (p1.y + p2.y) / 2 + ny * curve;

    return { id: i, color, p1, p2, d: `M ${p1.x},${p1.y} Q ${cx},${cy} ${p2.x},${p2.y}` };
  });

  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        zIndex: 1,            // above bg, below nodes
        pointerEvents: "none",
      }}
    >
      <svg
        width="100%"
        height="100%"
        viewBox={`${-W/2} ${-H/2} ${W} ${H}`}
        style={{ display:"block" }}
      >
        {paths.map(p => (
          <g key={p.id}>
            {/* THICK base line so it's obvious */}
            <path d={p.d} fill="none" stroke={p.color} strokeWidth="3.5" opacity="0.9" />
            {/* endpoint dots for debugging visibility */}
            <circle cx={p.p1.x} cy={p.p1.y} r="5.5" fill={p.color} opacity="0.9" />
            <circle cx={p.p2.x} cy={p.p2.y} r="5.5" fill={p.color} opacity="0.9" />
          </g>
        ))}
      </svg>
    </div>
  );
}
