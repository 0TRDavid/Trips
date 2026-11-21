// Identifiants stables des éléments qui passent d'une page à l'autre. Le même
// identifiant est posé sur l'élément de départ et sur celui d'arrivée, en
// attribut `data-transition-id` (lib/vol.ts les fait « voler ») :
//   - la carte d'un voyage (accueil)       →  l'en-tête du voyage
//   - la vignette d'un jour (timeline)     →  l'en-tête du jour
//   - la miniature d'une photo (galerie)   →  la photo en plein écran

export const idVoyage = (slug: string) => `voyage-${slug}`;
export const idJour = (slug: string, date: string) => `jour-${slug}-${date}`;
export const idPhoto = (id: number) => `photo-${id}`;
