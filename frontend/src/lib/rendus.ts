import type { PhotoResume, TailleRendu } from "../api/types";

const ORDRE: TailleRendu[] = ["miniature", "moyenne", "grande"];

/**
 * srcset du navigateur : « url largeurw » pour chaque rendu disponible.
 * Le navigateur choisit lui-même la plus petite image suffisante selon
 * `sizes` et la densité de l'écran : on ne charge jamais plus que nécessaire.
 */
export function srcset(photo: PhotoResume): string {
  return ORDRE.flatMap((taille) => {
    const r = photo.rendus[taille];
    return r ? [`${r.url} ${r.largeur}w`] : [];
  }).join(", ");
}

/** Image de repli (attribut src) : la moyenne, sinon ce qui existe. */
export function srcParDefaut(photo: PhotoResume): string | undefined {
  const r = photo.rendus.moyenne ?? photo.rendus.grande ?? photo.rendus.miniature;
  return r?.url;
}

/** URL du plus grand rendu (préchargement de la visionneuse). */
export function plusGrandRendu(photo: PhotoResume): string | undefined {
  return (photo.rendus.grande ?? photo.rendus.moyenne ?? photo.rendus.miniature)?.url;
}

/** Ratio largeur / hauteur de la photo affichée (orientation déjà appliquée). */
export function ratio(photo: PhotoResume): number {
  return photo.largeur > 0 && photo.hauteur > 0 ? photo.largeur / photo.hauteur : 1;
}
