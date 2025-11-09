import React from "react";
import { motion } from "framer-motion";

export default function Bubble({
  x=0, y=0, label, icon, hub=false,
  onDragEnd, draggable=false
}) {
  const base = {
    position: "absolute",
    left: `calc(50% + ${x - 60}px)`,
    top:  `calc(50% + ${y - 24}px)`,
    padding: "10px 14px",
    borderRadius: 999,
    background: "rgba(255,255,255,0.08)",
    border: `1px solid rgba(82,227,194,${hub ? 0.35 : 0.2})`,
    color: "#EAF6FF",
    whiteSpace: "nowrap",
    fontFamily: "system-ui, -apple-system, Segoe UI, Roboto, sans-serif",
    fontWeight: 600,
    boxShadow: hub ? "0 0 30px rgba(82,227,194,.25)" : "0 6px 24px rgba(0,0,0,.35)",
    zIndex: 2
  };

  return (
    <motion.div
      style={base}
      whileHover={{ scale: 1.05 }}
      drag={draggable}
      dragMomentum={true}
      dragElastic={0.15}
      dragConstraints={{ left: -window.innerWidth, right: window.innerWidth, top: -window.innerHeight, bottom: window.innerHeight }}
      onDragEnd={(e, info) => {
        if (!onDragEnd) return;
        const rect = e.target.getBoundingClientRect();
        const cx = window.innerWidth / 2;
        const cy = window.innerHeight / 2;
        const newX = rect.left + rect.width/2 - cx;
        const newY = rect.top  + rect.height/2 - cy;
        onDragEnd({ x: newX, y: newY });
      }}
    >
      {icon ? icon + " " : ""}{label}
    </motion.div>
  );
}
