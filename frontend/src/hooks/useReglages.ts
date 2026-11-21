import { useSyncExternalStore } from "react";
import type { Reglages } from "../lib/mouvement";
import { EVENEMENT_REGLAGES, REGLAGES_DEFAUT, reglages } from "../lib/mouvement";

function abonner(changement: () => void) {
  window.addEventListener(EVENEMENT_REGLAGES, changement);
  return () => window.removeEventListener(EVENEMENT_REGLAGES, changement);
}

/** Réglages du labo, réactifs (toujours les valeurs par défaut en prod). */
export function useReglages(): Reglages {
  return useSyncExternalStore(abonner, reglages, () => REGLAGES_DEFAUT);
}
