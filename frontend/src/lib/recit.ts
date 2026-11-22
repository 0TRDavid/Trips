import type { BlocRecit } from "../api/types";
import { heureLocale, momentsParHeure } from "./dates";

// Récit intercalé entre les moments de la journée.
//
// Le serveur découpe le récit aux lignes `[[14h]]` / `[[14h30]]`
// (voyages/markdown.py: decouper_recit) ; ici, on place chaque bloc juste
// avant la première photo prise à cette heure ou après, dans l'ordre reçu de
// l'API (retouches de l'admin comprises). Les photos sont regroupées par heure
// par momentsParHeure() : un nouveau moment commence dès que l'heure change.
//
// - un bloc qui tombe au début d'un moment se place AVANT son intitulé
//   (« avant le moment de 14 h ») ;
// - un bloc qui tombe au milieu (14 h 30) coupe les rangées du moment, qui
//   reprennent sous le même intitulé ;
// - un bloc sans heure (texte écrit avant tout marqueur) va en tête ;
// - un bloc plus tard que toutes les photos va à la fin.

type AvecPrise = { prise_le: string | null };

export type Segment<T> = { genre: "photos"; photos: T[] } | { genre: "recit"; html: string };

export type ElementJournee<T> =
  | { genre: "recit"; html: string }
  | { genre: "moment"; heure: number | null; segments: Segment<T>[] };

/** Index de la première photo prise à `heure` ("HH:MM") ou après ; photos.length si aucune. */
function indexInsertion<T extends AvecPrise>(photos: T[], heure: string): number {
  const i = photos.findIndex((p) => {
    const h = heureLocale(p.prise_le);
    return h !== "" && h >= heure;
  });
  return i === -1 ? photos.length : i;
}

const heureDe = (p: AvecPrise): number | null => {
  const m = p.prise_le?.match(/T(\d{2}):/);
  return m ? Number(m[1]) : null;
};

export function entremeler<T extends AvecPrise>(photos: T[], blocs: BlocRecit[]): ElementJournee<T>[] {
  const elements: ElementJournee<T>[] = [];
  // Blocs à insérer avant la photo d'index i (dans l'ordre d'écriture).
  const avant = new Map<number, string[]>();
  for (const bloc of blocs) {
    if (bloc.heure === null) {
      elements.push({ genre: "recit", html: bloc.html });
      continue;
    }
    const i = indexInsertion(photos, bloc.heure);
    avant.set(i, [...(avant.get(i) ?? []), bloc.html]);
  }

  let debut = 0; // index global de la première photo du moment
  for (const { heure, photos: duMoment } of momentsParHeure(photos)) {
    for (const html of avant.get(debut) ?? []) elements.push({ genre: "recit", html });
    const segments: Segment<T>[] = [];
    duMoment.forEach((photo, j) => {
      if (j > 0) for (const html of avant.get(debut + j) ?? []) segments.push({ genre: "recit", html });
      const dernier = segments.at(-1);
      if (dernier?.genre === "photos") dernier.photos.push(photo);
      else segments.push({ genre: "photos", photos: [photo] });
    });
    elements.push({ genre: "moment", heure, segments });
    debut += duMoment.length;
  }
  for (const html of avant.get(photos.length) ?? []) elements.push({ genre: "recit", html });
  return elements;
}

/** Heure de la première et de la dernière photo datée (« 7 h », « 21 h »), pour la progression. */
export function bornesHeures<T extends AvecPrise>(photos: T[]): [number, number] | null {
  const heures = photos.map(heureDe).filter((h): h is number => h !== null);
  return heures.length ? [Math.min(...heures), Math.max(...heures)] : null;
}
