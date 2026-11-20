import { useEffect, useRef } from "react";

/**
 * Raccourcis clavier globaux, ex. { ArrowLeft: precedent, Escape: fermer }.
 * Les fonctions peuvent changer à chaque rendu sans réabonner l'écouteur
 * (on garde toujours la dernière version dans une ref).
 */
export function useTouchesClavier(touches: Record<string, () => void>) {
  const ref = useRef(touches);
  ref.current = touches;

  useEffect(() => {
    const surTouche = (e: KeyboardEvent) => {
      if (e.altKey || e.ctrlKey || e.metaKey) return; // laisse Alt+← (retour) au navigateur
      const action = ref.current[e.key];
      if (!action) return;
      e.preventDefault();
      action();
    };
    window.addEventListener("keydown", surTouche);
    return () => window.removeEventListener("keydown", surTouche);
  }, []);
}
