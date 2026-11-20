// Construction des URL du site, en un seul endroit.
export const chemins = {
  accueil: () => "/",
  voyage: (slug: string) => `/voyages/${encodeURIComponent(slug)}`,
  jour: (slug: string, date: string) => `/voyages/${encodeURIComponent(slug)}/jours/${date}`,
  photo: (slug: string, date: string, id: number) =>
    `/voyages/${encodeURIComponent(slug)}/jours/${date}/photos/${id}`,
};

/**
 * Clé de la « page » affichée : l'URL sans la partie visionneuse. Ouvrir une
 * photo ne change pas de page (la page jour reste dessous) ; passer d'un jour
 * à l'autre, si.
 */
export function clePage(pathname: string): string {
  return pathname.replace(/\/photos\/[^/]+\/?$/, "");
}
