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

/** photo, photo animée (HEIC Samsung avec une courte vidéo) ou vidéo. */
export type TypeMedia = "photo" | "animee" | "video";

/** Vidéos MP4 par petit côté visé ("720", "1080") ; une seule si la source est petite. */
export type VideosMedia = Partial<Record<"720" | "1080", Rendu>>;

/**
 * Photo dans la page d'un jour : en fait un média. Pour une vidéo, `rendus`
 * contient son image d'aperçu (poster) ; pour une photo animée, son image fixe.
 */
export type PhotoJour = PhotoResume & {
  type: TypeMedia;
  /** Durée en secondes (vidéo, ou vidéo d'une photo animée) ; null pour une photo. */
  duree: number | null;
  /** Vide pour une photo. */
  videos: VideosMedia;
  /** ISO 8601 avec le décalage du voyage, ex. "2025-06-02T09:56:24+09:00". */
  prise_le: string | null;
  legende: string;
  favori: boolean;
  /** Prénom tiré du sous-dossier Nextcloud ("Hugo"), vide si inconnu. */
  photographe: string;
};

/**
 * Couleurs tirées des photos d'un voyage ou d'un jour (backend/voyages/palette.py).
 * Contrastes WCAG AA garantis : `accent_texte` sur `fond` et `fond_2`,
 * `sur_accent` sur `accent`.
 */
export type Palette = {
  accent: string;
  accent_texte: string;
  sur_accent: string;
  fond: string;
  fond_2: string;
  degrade: string[];
  /** 3 pastels pour les halos du fond (tout texte y reste AA). */
  halos: string[];
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
  palette: Palette;
};

export type JourResume = {
  date: string;
  titre: string;
  lieu: string;
  nb_photos: number;
  recit_rempli: boolean;
  photo: PhotoResume | null;
  palette: Palette;
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

export type BlocRecit = { heure: string | null; html: string };

export type JourDetail = {
  date: string;
  titre: string;
  lieu: string;
  recit: string;
  recit_html: string;
  /** Récit découpé aux marqueurs `[[14h]]` (heure "14:00", null = avant tout marqueur). */
  recit_blocs: BlocRecit[];
  voyage: { slug: string; titre: string; fuseau_horaire: string };
  photos: PhotoJour[];
  precedent: JourVoisin | null;
  suivant: JourVoisin | null;
  palette: Palette;
};
