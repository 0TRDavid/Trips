// Types des réponses de l'API Django (lecture seule). Ils reflètent les
// sérialiseurs de backend/voyages/serializers.py : si l'API change, c'est ici.

export type TailleRendu = "miniature" | "moyenne" | "grande";

export type Rendu = {
  url: string;
  largeur: number;
  hauteur: number;
};

/** Champs communs à toute photo affichable (couverture, vignette, galerie). */
export type PhotoResume = {
  id: number;
  largeur: number;
  hauteur: number;
  /** Couleur dominante, ex. "#908d84". */
  couleur: string;
  /** ThumbHash en base64 (placeholder flou). */
  placeholder: string;
  rendus: Partial<Record<TailleRendu, Rendu>>;
};

/** Photo dans la page d'un jour. */
export type PhotoJour = PhotoResume & {
  /** ISO 8601 avec le décalage du voyage, ex. "2025-06-02T09:56:24+09:00". */
  prise_le: string | null;
  legende: string;
  favori: boolean;
  /** Prénom tiré du sous-dossier Nextcloud ("Hugo"), vide si inconnu. */
  photographe: string;
};

export type VoyageResume = {
  slug: string;
  titre: string;
  /** "AAAA-MM-JJ" */
  date_debut: string | null;
  date_fin: string | null;
  fuseau_horaire: string;
  nb_jours: number;
  nb_photos: number;
  couverture: PhotoResume | null;
};

export type JourResume = {
  date: string;
  titre: string;
  lieu: string;
  nb_photos: number;
  recit_rempli: boolean;
  photo: PhotoResume | null;
};

export type PointTrace = {
  lat: number;
  lon: number;
  jour: string;
};

export type VoyageDetail = VoyageResume & {
  recit_intro: string;
  recit_intro_html: string;
  jours: JourResume[];
  trace: PointTrace[];
};

export type JourVoisin = {
  date: string;
  titre: string;
  photo: PhotoResume | null;
};

export type JourDetail = {
  date: string;
  titre: string;
  lieu: string;
  recit: string;
  recit_html: string;
  voyage: { slug: string; titre: string; fuseau_horaire: string };
  photos: PhotoJour[];
  precedent: JourVoisin | null;
  suivant: JourVoisin | null;
};
