import { motion } from "framer-motion";
import { THEME } from "./theme";
export default function Bubble({ label, icon, x, y, hub=false }) {
  return (
    <motion.div
      className={`${hub ? THEME.hub : THEME.card} ${THEME.text} absolute rounded-full px-4 py-3`}
      style={{ transform:`translate(${x}px,${y}px)` }}
      whileHover={{ scale:1.05 }}
    >
      {icon} {label}
    </motion.div>
  );
}
