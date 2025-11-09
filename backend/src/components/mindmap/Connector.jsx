import { THEME } from "./theme";
export default function Connector({ from,to }) {
  const x1=from.x,y1=from.y,x2=to.x,y2=to.y;
  const len=Math.hypot(x2-x1,y2-y1);
  const angle=Math.atan2(y2-y1,x2-x1)*(180/Math.PI);
  const midX=(x1+x2)/2,midY=(y1+y2)/2;
  return (
    <div className="absolute bg-[#52E3C2]" style={{
      width:len,height:2,
      transform:`translate(${midX-len/2}px,${midY}px) rotate(${angle}deg)`,
      boxShadow:`0 0 8px ${THEME.primary}`
    }} />
  );
}
