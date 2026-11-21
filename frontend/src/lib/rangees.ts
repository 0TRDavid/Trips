/** Galerie plein écran (mosaïque, page par page) : ordinateur seulement ; le téléphone garde ses rangées. */
export function galeriePleinEcran(): boolean {
  return window.matchMedia("(min-width: 700px)").matches;
}

// --- Mosaïque plein écran (ordinateur) ---------------------------------------
// Une photo paysage occupe un écran à elle seule : elle le remplit si son
// format est proche de celui de l'écran, sinon elle est entière sur sa version
// floue. Les portraits vont par deux, côte à côte, bord à bord ; un portrait
// sans voisin portrait (suivi d'un paysage, ou dernier de l'heure) est seul,
// entier sur son flou.

/** Case d'un gabarit, en fractions de l'écran. */
export type Case = { x: number; y: number; l: number; h: number };
export type PageMosaique =
  | { gabarit: "seule"; debut: number; cases: Case[]; couvrir: boolean }
  | { gabarit: "deux-colonnes"; debut: number; cases: Case[] };

const DEUX_COLONNES: Case[] = [
  { x: 0, y: 0, l: 0.5, h: 1 },
  { x: 0.5, y: 0, l: 0.5, h: 1 },
];
const SEULE: Case[] = [{ x: 0, y: 0, l: 1, h: 1 }];

/** Une photo seule remplit l'écran si elle y perd au plus cette part d'elle-même. */
const ROGNAGE_MAX_SEULE = 0.15;

/** Part de la photo perdue quand elle couvre une case de ratio `rc`. */
const rognage = (rp: number, rc: number) => 1 - Math.min(rp / rc, rc / rp);
const paysage = (r: number) => r > 1;

export function mosaiquePleinEcran(ratios: number[], largeur: number, hauteur: number): PageMosaique[] {
  const ecran = largeur / hauteur;
  const pages: PageMosaique[] = [];
  let debut = 0;
  while (debut < ratios.length) {
    const r = ratios[debut];
    const suivant = ratios[debut + 1];
    if (!paysage(r) && suivant !== undefined && !paysage(suivant)) {
      pages.push({ gabarit: "deux-colonnes", debut, cases: DEUX_COLONNES });
      debut += 2;
    } else {
      pages.push({ gabarit: "seule", debut, cases: SEULE, couvrir: rognage(r, ecran) <= ROGNAGE_MAX_SEULE });
      debut += 1;
    }
  }
  return pages;
}
