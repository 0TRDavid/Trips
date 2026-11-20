import { useSyncExternalStore } from "react";

const REQUETE = "(prefers-reduced-motion: reduce)";

function abonner(changement: () => void) {
  const liste = window.matchMedia(REQUETE);
  liste.addEventListener("change", changement);
  return () => liste.removeEventListener("change", changement);
}

/**
 * Vrai si le système demande de réduire les animations. Réactif : changer le
 * réglage pendant la visite s'applique tout de suite, sans recharger.
 *
 * (useSyncExternalStore : la façon React de lire une valeur qui vit hors de
 * React, ici une media query, sans état dupliqué ni effet à écrire.)
 */
export function useMouvementReduit(): boolean {
  return useSyncExternalStore(
    abonner,
    () => window.matchMedia(REQUETE).matches,
    () => false,
  );
}
