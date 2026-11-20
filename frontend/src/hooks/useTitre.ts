import { useEffect } from "react";

/** Titre de l'onglet (et de l'entrée d'historique). */
export function useTitre(titre: string | undefined) {
  useEffect(() => {
    document.title = titre ? `${titre} · Carnet de voyages` : "Carnet de voyages";
  }, [titre]);
}
