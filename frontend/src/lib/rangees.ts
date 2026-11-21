/** Galerie plein écran (mosaïque, page par page) : ordinateur seulement ; le téléphone garde ses rangées. */
export function galeriePleinEcran(): boolean {
  return window.matchMedia("(min-width: 700px)").matches;
}

// --- Mosaïque plein écran (ordinateur) ---------------------------------------
// Deux photos par écran, bord à bord : côte à côte, ou l'une au-dessus de
// l'autre (panoramas), selon ce qui les rogne le moins (photos en
// « couvrir »). Une photo seule (heure d'une seule photo, ou la dernière d'une
// heure impaire) garde ses proportions : entière, sur sa version floue.

/** Case d'un gabarit, en fractions de l'écran. */
export type Case = { x: number; y: number; l: number; h: number };
export type PageMosaique = { gabarit: "seule" | "deux-colonnes" | "deux-lignes"; debut: number; cases: Case[] };

const GABARITS_PAIRE = {
  "deux-colonnes": [
    { x: 0, y: 0, l: 0.5, h: 1 },
    { x: 0.5, y: 0, l: 0.5, h: 1 },
  ],
  "deux-lignes": [
    { x: 0, y: 0, l: 1, h: 0.5 },
    { x: 0, y: 0.5, l: 1, h: 0.5 },
  ],
} as const satisfies Record<string, Case[]>;

const SEULE: Case[] = [{ x: 0, y: 0, l: 1, h: 1 }];

/** Part de la photo perdue quand elle couvre une case de ratio `rc`. */
const rognage = (rp: number, rc: number) => 1 - Math.min(rp / rc, rc / rp);

export function mosaiquePleinEcran(ratios: number[], largeur: number, hauteur: number): PageMosaique[] {
  const ecran = largeur / hauteur;
  const pages: PageMosaique[] = [];
  for (let debut = 0; debut < ratios.length; debut += 2) {
    if (debut + 1 >= ratios.length) {
      pages.push({ gabarit: "seule", debut, cases: SEULE });
      break;
    }
    const perte = (cases: readonly Case[]) =>
      cases.reduce((t, c, k) => t + rognage(ratios[debut + k], (c.l / c.h) * ecran), 0);
    const gabarit = perte(GABARITS_PAIRE["deux-lignes"]) < perte(GABARITS_PAIRE["deux-colonnes"]) ? "deux-lignes" : "deux-colonnes";
    pages.push({ gabarit, debut, cases: [...GABARITS_PAIRE[gabarit]] });
  }
  return pages;
}
