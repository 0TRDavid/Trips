import { useSyncExternalStore } from "react";
import { EVENEMENT_REGLAGES, reglages } from "../lib/mouvement";

const REQUETE = "(prefers-reduced-motion: reduce)";

function abonner(changement: () => void) {
  const liste = window.matchMedia(REQUETE);
  liste.addEventListener("change", changement);
  // En dev, le labo peut simuler le réglage.
  window.addEventListener(EVENEMENT_REGLAGES, changement);
  return () => {
    liste.removeEventListener("change", changement);
    window.removeEventListener(EVENEMENT_REGLAGES, changement);
  };
}

/** Lecture ponctuelle, hors composant (Layout, vols). */
export function mouvementReduit(): boolean {
  return window.matchMedia(REQUETE).matches || reglages().reduit;
}

/**
 * Vrai si le système demande de réduire les animations. Réactif : changer le
 * réglage pendant la visite s'applique tout de suite, sans recharger.
 *
 * (useSyncExternalStore : la façon React de lire une valeur qui vit hors de
 * React, ici une media query, sans état dupliqué ni effet à écrire.)
 */
export function useMouvementReduit(): boolean {
  return useSyncExternalStore(abonner, mouvementReduit, () => false);
}
