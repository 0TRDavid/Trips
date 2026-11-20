// Identifiants stables des éléments qui passeront d'une page à l'autre à
// l'étape 6 (animations). Le même identifiant est posé sur l'élément de départ
// et sur celui d'arrivée, en attribut `data-transition-id` :
//   - la carte d'un voyage (accueil)  →  l'en-tête du voyage
//   - la miniature d'une photo (jour) →  la photo en plein écran
// À l'étape 6, ils serviront de `layoutId` (Motion) ou de
// `view-transition-name` (CSS), sans toucher aux pages.

export const idVoyage = (slug: string) => `voyage-${slug}`;
export const idPhoto = (id: number) => `photo-${id}`;
