import type { ReactNode } from "react";
import { motion } from "motion/react";
import { useMouvementReduit } from "../hooks/useMouvementReduit";
import { variantesBloc } from "../lib/mouvement";

/**
 * Bloc d'une page qui apparaît en cascade après l'arrivée de la page.
 * Il hérite des étapes de la page (initial → visible) : c'est la page qui
 * règle le délai et l'intervalle entre les blocs (lib/mouvement.ts).
 */
export default function Apparition({ children, className }: { children: ReactNode; className?: string }) {
  const reduit = useMouvementReduit();
  return (
    <motion.div className={className} variants={variantesBloc(reduit)}>
      {children}
    </motion.div>
  );
}
