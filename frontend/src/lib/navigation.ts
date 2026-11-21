// Nature et sens d'un changement de page, pour choisir la transition.
//
// Le sens est SÉMANTIQUE, pas tiré de l'historique : on « avance » quand on
// descend dans le carnet (accueil → voyage → jour) ou qu'on passe au jour
// suivant ; on « recule » dans l'autre cas. Le bouton retour du navigateur
// produit donc naturellement la transition inverse de celle de l'aller, et
// « jour précédent » glisse dans le même sens que « retour ».

import type { GenreNavigation, Navigation, Sens } from "./mouvement";

type Ecran =
  | { niveau: 0 }
  | { niveau: 1; slug: string }
  | { niveau: 2; slug: string; date: string }
  | { niveau: -1 };

/** Écran correspondant à une clé de page (`clePage`, sans la visionneuse). */
export function ecranDe(chemin: string): Ecran {
  const morceaux = chemin.split("/").filter(Boolean).map(decodeURIComponent);
  if (morceaux.length === 0) return { niveau: 0 };
  if (morceaux[0] === "voyages" && morceaux.length === 2) return { niveau: 1, slug: morceaux[1] };
  if (morceaux[0] === "voyages" && morceaux.length === 4 && morceaux[2] === "jours") {
    return { niveau: 2, slug: morceaux[1], date: morceaux[3] };
  }
  return { niveau: -1 };
}

/** 1 si l'on avance (plus profond, ou jour plus tardif), -1 sinon. */
export function sensNavigation(avant: string, apres: string): Sens {
  const a = ecranDe(avant);
  const b = ecranDe(apres);
  if (a.niveau === 2 && b.niveau === 2 && a.slug === b.slug) return b.date >= a.date ? 1 : -1;
  // Page inconnue (404) : comptée comme une page de premier niveau.
  const profondeur = (e: Ecran) => (e.niveau === -1 ? 1 : e.niveau);
  return profondeur(b) >= profondeur(a) ? 1 : -1;
}

/** Genre de transition entre deux pages (hors réduction des animations). */
export function genreNavigation(avant: string, apres: string): GenreNavigation {
  const a = ecranDe(avant);
  const b = ecranDe(apres);
  if (a.niveau === 2 && b.niveau === 2 && a.slug === b.slug) return "jour";
  const niveaux = [a.niveau, b.niveau].sort().join();
  if (niveaux === "0,1") return "voyage";
  const slugs = [a, b].map((e) => ("slug" in e ? e.slug : null));
  if (niveaux === "1,2" && slugs[0] === slugs[1]) return "ouvrirJour";
  return "page";
}

export function navigation(avant: string, apres: string, opts: { reduit: boolean; dejaAnime: boolean }): Navigation {
  const sens = sensNavigation(avant, apres);
  if (opts.dejaAnime) return { genre: "aucune", sens };
  if (opts.reduit) return { genre: "fondu", sens };
  return { genre: genreNavigation(avant, apres), sens };
}

// --- Geste « retour » natif -------------------------------------------------------
// Safari iOS (et Chrome Android) animent eux-mêmes le glissement « retour »
// depuis le bord de l'écran. `hasUAVisualTransition` le signale : on ne
// rejoue alors pas notre propre animation par-dessus.

let retourDejaAnime = -Infinity; // instant du dernier popstate déjà animé

if (typeof window !== "undefined") {
  window.addEventListener("popstate", (e) => {
    const anime = (e as PopStateEvent & { hasUAVisualTransition?: boolean }).hasUAVisualTransition === true;
    retourDejaAnime = anime ? performance.now() : -Infinity;
  });
}

/**
 * Vrai si la navigation en cours vient d'un « retour » déjà animé par le
 * navigateur (popstate de moins de 500 ms). Remis à zéro à la lecture.
 */
export function consommerRetourDejaAnime(): boolean {
  const recent = performance.now() - retourDejaAnime < 500;
  retourDejaAnime = -Infinity;
  return recent;
}
