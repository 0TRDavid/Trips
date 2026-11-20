import { useRef } from "react";
import type { PointerEvent as ReactPointerEvent } from "react";

export type Direction = "precedent" | "suivant";

/**
 * Décide si un geste est un glissement horizontal.
 * - assez long (60 px) OU assez rapide (0,4 px/ms sur au moins 25 px) ;
 * - nettement plus horizontal que vertical (sinon c'est un défilement).
 * Glisser vers la gauche = photo suivante.
 */
export function decisionGlissement(dx: number, dy: number, dureeMs: number): Direction | null {
  const ax = Math.abs(dx);
  if (ax < 25 || ax < Math.abs(dy) * 1.5) return null;
  const vitesse = ax / Math.max(dureeMs, 1);
  if (ax < 60 && vitesse < 0.4) return null;
  return dx < 0 ? "suivant" : "precedent";
}

/**
 * Glissement horizontal au doigt (Pointer Events, sans dépendance).
 * Ignoré pour la souris (les flèches suffisent) et dès que deux doigts
 * touchent l'écran (zoom par pincement du navigateur).
 * Renvoie les gestionnaires à poser sur l'élément.
 */
export function useGlissement(surGlissement: (d: Direction) => void) {
  const depart = useRef<{ x: number; y: number; t: number; id: number } | null>(null);
  const doigts = useRef(new Set<number>());

  const fin = (e: ReactPointerEvent) => {
    doigts.current.delete(e.pointerId);
    const d = depart.current;
    if (!d || d.id !== e.pointerId) return;
    depart.current = null;
    const direction = decisionGlissement(e.clientX - d.x, e.clientY - d.y, e.timeStamp - d.t);
    if (direction) surGlissement(direction);
  };

  return {
    onPointerDown: (e: ReactPointerEvent) => {
      if (e.pointerType === "mouse") return;
      doigts.current.add(e.pointerId);
      // Deuxième doigt : c'est un pincement, on abandonne le geste.
      depart.current =
        doigts.current.size === 1
          ? { x: e.clientX, y: e.clientY, t: e.timeStamp, id: e.pointerId }
          : null;
    },
    onPointerUp: fin,
    onPointerCancel: (e: ReactPointerEvent) => {
      doigts.current.delete(e.pointerId);
      depart.current = null;
    },
  };
}
