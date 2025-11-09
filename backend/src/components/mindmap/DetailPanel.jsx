import { THEME } from "./theme";
export default function DetailPanel({ node, onClose }) {
  if (!node) return null;
  return (
    <div className={`fixed top-0 right-0 h-full w-[380px] md:w-[440px] ${THEME.card} ${THEME.text} p-5 z-40`}>
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-bold">{node.icon} {node.label}</h3>
        <button onClick={onClose} className="text-sm opacity-80 hover:opacity-100">Close</button>
      </div>
      <div className={`${THEME.subtext} text-sm space-y-3`}>
        <p><strong>Status:</strong> {node.badge || "—"}</p>
        <p><strong>Action:</strong> {node.action || "—"}</p>
      </div>
    </div>
  );
}
