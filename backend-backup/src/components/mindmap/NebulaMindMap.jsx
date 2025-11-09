import React, { useMemo } from "react";
import Bubble from "./Bubble";
import Connector from "./Connector";
import { THEME } from "./theme";
import categories from "../../data/categories.json";

export default function NebulaMindMap() {
  const center = { x: 0, y: 0 };
  const radius = 200;
  const orbitPositions = (count) =>
    new Array(count).fill(0).map((_, i) => ({
      x: Math.cos((i / count) * Math.PI * 2) * radius,
      y: Math.sin((i / count) * Math.PI * 2) * radius,
    }));
  const hubs = useMemo(() => orbitPositions(categories.length), []);
  return (
    <div className={`${THEME.bg} min-h-screen flex items-center justify-center relative`}>
      {hubs.map((pos, i) => (
        <React.Fragment key={categories[i].id}>
          <Connector from={center} to={pos} />
          <Bubble label={categories[i].label} icon={categories[i].icon} x={pos.x} y={pos.y}/>
        </React.Fragment>
      ))}
      <Bubble hub icon="í· " label="Runner-B Core" x={-60} y={-24}/>
    </div>
  );
}
