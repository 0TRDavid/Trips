// Système de mouvement du site : TOUTES les durées, courbes et ressorts sont
// ici. Les composants n'écrivent jamais de valeur en dur, ils appellent les
// fonctions de ce fichier, qui appliquent les règles :
//   - une sortie est plus rapide que l'entrée correspondante (facteurSortie) ;
//   - le sens d'un glissement suit le sens de la navigation (sens = 1 : on
//     avance, -1 : on recule ; voir lib/navigation.ts) ;
//   - on n'anime que transform et opacity, écrits tels quels (pas x / y) : rien
//     qui oblige à recalculer la mise en page, et le navigateur joue
//     l'animation hors du fil principal (test dans mouvement.test.ts) ;
//   - « réduire les animations » : tout devient un simple fondu.
//
// En dev, la page /labo peut ralentir le temps et
// simuler « réduire les animations » (réglages lus dans localStorage). En
// prod, `import.meta.env.DEV` est faux : ce code disparaît du build.

import type { Transition, Variants } from "motion/react";

// --- Tokens -------------------------------------------------------------------

/** Durées, en secondes. */
export const duree = { rapide: 0.18, normale: 0.32, lente: 0.55 } as const;

/** Courbes de Bézier. */
export const courbe = {
  /** expo-out : arrive vite, se pose doucement (ce qui entre). */
  entree: [0.16, 1, 0.3, 1],
  /** expo-in : démarre doucement, part sans traîner (ce qui sort). */
  sortie: [0.7, 0, 0.84, 0],
  /** symétrique, pour ce qui se déplace d'un point à un autre sans entrer ni sortir. */
  standard: [0.65, 0, 0.35, 1],
} as const satisfies Record<string, readonly [number, number, number, number]>;

/** Ressorts Motion : `visualDuration` = durée perçue, `bounce` = rebond (0 = aucun). */
export const ressort = {
  /** élément partagé qui grandit (carte → en-tête, miniature → plein écran). */
  partage: { visualDuration: 0.5, bounce: 0.12 },
  /** retour plus nerveux (plein écran → miniature). */
  vif: { visualDuration: 0.35, bounce: 0.2 },
} as const;

/** Une sortie dure 65 % de son entrée. */
export const facteurSortie = 0.65;

/** Distances, en px. */
export const distance = { glissement: 40, montee: 12, cascade: 16 } as const;

/** Décalage entre deux blocs qui apparaissent en cascade, en secondes. */
export const intervalleCascade = 0.06;

/** « Réduire les animations » : durée du fondu qui remplace tout. */
export const DUREE_REDUITE = 0.15;

/** Publie les durées en variables CSS (`--duree-rapide`…) pour les petites transitions CSS (survol). */
export function publierDureesCss(racine: HTMLElement = document.documentElement) {
  for (const [nom, d] of Object.entries(duree)) racine.style.setProperty(`--duree-${nom}`, `${d}s`);
}

// --- Réglages du labo -----------------------------------------------------------
// Variantes validées à l'œil le 21/11/2026 : ressort carte → en-tête, ressort
// miniature ↔ plein écran, page entière entre deux jours, fond en halos fixes.
// Les autres ont été retirées ; le labo sert à rejouer et à ralentir.

export type Reglages = {
  /** Multiplicateur des durées (1 = normal, 4 = quatre fois plus lent). */
  ralenti: number;
  /** Simule `prefers-reduced-motion: reduce`. */
  reduit: boolean;
};

export const REGLAGES_DEFAUT: Reglages = { ralenti: 1, reduit: false };

export const CLE_REGLAGES = "carnet-labo";
export const EVENEMENT_REGLAGES = "carnet-reglages";

let cache: Reglages | null = null;

function lireReglages(): Reglages {
  try {
    const brut = localStorage.getItem(CLE_REGLAGES);
    if (!brut) return REGLAGES_DEFAUT;
    const lu = JSON.parse(brut) as Partial<Reglages>;
    return {
      ralenti: typeof lu.ralenti === "number" && lu.ralenti > 0 ? lu.ralenti : 1,
      reduit: lu.reduit === true,
    };
  } catch {
    return REGLAGES_DEFAUT;
  }
}

if (import.meta.env.DEV && typeof window !== "undefined") {
  // Les iframes du labo sont prévenues par l'événement `storage` quand le labo
  // change un réglage : la prochaine transition l'applique, sans recharger.
  window.addEventListener("storage", (e) => {
    if (e.key !== CLE_REGLAGES) return;
    cache = null;
    window.dispatchEvent(new Event(EVENEMENT_REGLAGES));
  });
}

/** Réglages en vigueur (toujours les valeurs par défaut en prod). */
export function reglages(): Reglages {
  if (!import.meta.env.DEV) return REGLAGES_DEFAUT;
  return (cache ??= lireReglages());
}

/** Enregistre des réglages (labo). */
export function enregistrerReglages(r: Reglages) {
  cache = r;
  try {
    localStorage.setItem(CLE_REGLAGES, JSON.stringify(r));
  } catch {
    /* stockage indisponible : réglage valable pour cette page seulement */
  }
  window.dispatchEvent(new Event(EVENEMENT_REGLAGES));
}


// --- Règles -----------------------------------------------------------------------

/** Durée réelle, ralenti du labo compris. */
const t = (secondes: number) => secondes * reglages().ralenti;

/** Ce qui entre : courbe expo-out. */
export function entree(d: number = duree.normale, delay = 0): Transition {
  return { duration: t(d), ease: courbe.entree, delay: t(delay) };
}

/** Ce qui sort : plus court que l'entrée, courbe expo-in. */
export function sortie(d: number = duree.normale): Transition {
  return { duration: t(d * facteurSortie), ease: courbe.sortie };
}

/** Ressort nommé, éventuellement raccourci (retour d'un élément partagé). */
export function ressortDe(nom: keyof typeof ressort, facteur = 1): Transition {
  const r = ressort[nom];
  return { type: "spring", visualDuration: t(r.visualDuration * facteur), bounce: r.bounce };
}

/** Simple fondu (« réduire les animations »). */
export function fondu(): Transition {
  return { duration: t(DUREE_REDUITE), ease: "linear" };
}

/** Durée perçue d'une transition, en secondes (enchaînements). */
export function dureeDe(transition: Transition): number {
  const tr = transition as { visualDuration?: number; duration?: number; delay?: number };
  return (tr.visualDuration ?? tr.duration ?? 0) + (tr.delay ?? 0);
}

// --- Navigation entre pages -------------------------------------------------------

/**
 * Nature d'un changement de page (voir lib/navigation.ts) :
 * - aucune : premier affichage, ou geste « retour » déjà animé par le navigateur ;
 * - fondu : « réduire les animations » ;
 * - voyage : accueil ↔ voyage (élément partagé carte ↔ en-tête) ;
 * - ouvrirJour : voyage ↔ un de ses jours (vignette de la timeline ↔ en-tête du jour) ;
 * - jour : jour ↔ jour du même voyage (glissement directionnel) ;
 * - page : tout le reste.
 */
export type GenreNavigation = "aucune" | "fondu" | "voyage" | "ouvrirJour" | "jour" | "page";

/** Navigation pendant laquelle une photo vole jusqu'à un en-tête (ou en revient). */
export const avecEnTetePartage = (nav: Navigation) => nav.genre === "voyage" || nav.genre === "ouvrirJour";
export type Sens = 1 | -1;
export type Navigation = { genre: GenreNavigation; sens: Sens };

const AUCUNE: Transition = { duration: 0 };

/**
 * Déplacement écrit en `transform` (et non avec x / y de Motion) : Motion
 * confie alors l'animation au navigateur (Web Animations), qui la joue hors
 * du fil principal. Indispensable : l'arrivée d'une page (carte, dizaines de
 * photos) occupe le fil principal pendant plusieurs dizaines de ms, ce qui
 * faisait saccader les animations calculées en JavaScript.
 * Toujours la même forme `translate(X%, Ypx)`, pour que Motion sache
 * interpoler entre deux étapes.
 */
export const decaler = (xPourcent: number, yPx = 0) => `translate(${xPourcent}%, ${yPx}px)`;
const decalerPx = (xPx: number) => `translate(${xPx}px, 0px)`;
/** À la fin d'une entrée, plus aucun transform : un transform résiduel ferait
 *  du cadre le repère des éléments `position: fixed` (visionneuse). */
const SANS_TRANSFORM = { transform: "none" };

/**
 * Variantes Motion d'une page (initial → visible → sortie), selon la
 * navigation. Fonctions de `custom` : la page qui SORT reçoit la navigation
 * qui la remplace (AnimatePresence lui passe le `custom` le plus récent).
 */
export const variantesPage: Variants = {
  initial: (nav: Navigation) => {
    const { genre, sens } = nav;
    if (genre === "aucune") return { opacity: 1 };
    if (genre === "fondu") return { opacity: 0 };
    if (genre === "jour") return { opacity: 1, transform: decaler(100 * sens) };
    if (genre === "voyage" || genre === "ouvrirJour") return { opacity: 0 };
    return { opacity: 0, transform: decaler(0, distance.montee * sens) };
  },
  visible: (nav: Navigation) => {
    const { genre } = nav;
    const fin = { opacity: 1, transform: decaler(0, 0), transitionEnd: SANS_TRANSFORM };
    if (genre === "aucune") return { ...fin, transition: AUCUNE };
    if (genre === "fondu") return { ...fin, transition: fondu() };
    if (genre === "jour") return { ...fin, transition: entree(duree.lente) };
    if (genre === "voyage" || genre === "ouvrirJour") {
      // La page arrive vite ; ses blocs (<Apparition>) suivent en cascade.
      return {
        ...fin,
        transition: {
          ...entree(duree.rapide),
          delayChildren: t(duree.rapide),
          staggerChildren: t(intervalleCascade),
        },
      };
    }
    // L'entrée attend un peu que la sortie soit engagée : moins de superposition.
    return { ...fin, transition: entree(duree.normale, duree.rapide * 0.5) };
  },
  sortie: (nav: Navigation) => {
    const { genre, sens } = nav;
    if (genre === "aucune") return { opacity: 0, transition: AUCUNE };
    if (genre === "fondu") return { opacity: 0, transition: fondu() };
    if (genre === "jour") {
      // L'ancienne page part d'un bloc de l'autre côté ; plus vite que la
      // nouvelle n'arrive, mais en décélérant pour ne pas sembler « tomber ».
      return { transform: decaler(-100 * sens), transition: { ...sortie(duree.lente), ease: courbe.entree } };
    }
    if (genre === "voyage" || genre === "ouvrirJour") return { opacity: 0, transition: sortie(duree.rapide) };
    return { opacity: 0, transform: decaler(0, (-distance.montee / 2) * sens), transition: sortie(duree.normale) };
  },
};

/** Bloc qui apparaît en cascade dans une page (hérite de `variantesPage`). */
export function variantesBloc(reduit: boolean): Variants {
  if (reduit) return { initial: { opacity: 0 }, visible: () => ({ opacity: 1, transition: fondu() }) };
  return {
    initial: { opacity: 0, transform: decaler(0, distance.cascade) },
    visible: () => ({ opacity: 1, transform: decaler(0, 0), transitionEnd: SANS_TRANSFORM, transition: entree(duree.normale) }),
  };
}

// --- Éléments partagés (lib/vol.ts) ----------------------------------------------

/** Vol d'une vignette vers un en-tête (carte → voyage, timeline → jour). `sens` 1 : vers l'en-tête ; -1 : retour. */
export function volEnTete(sens: Sens): Transition {
  return ressortDe("partage", sens === -1 ? facteurSortie : 1);
}

/** Vol miniature ↔ plein écran. `sens` 1 : ouverture ; -1 : fermeture. */
export function volPhoto(sens: Sens): Transition {
  return sens === 1 ? ressortDe("partage") : ressortDe("vif");
}

/** Photo → photo dans la visionneuse : glissement court dans le sens de la navigation. */
export function variantesPhotoVoisine(reduit: boolean): Variants {
  if (reduit) {
    return {
      initial: { opacity: 0 },
      visible: () => ({ opacity: 1, transition: fondu() }),
      sortie: () => ({ opacity: 0, transition: fondu() }),
    };
  }
  return {
    initial: (sens: Sens) => ({ opacity: 0, transform: decalerPx(distance.glissement * sens) }),
    visible: () => ({ opacity: 1, transform: decalerPx(0), transitionEnd: SANS_TRANSFORM, transition: entree(duree.normale) }),
    sortie: (sens: Sens) => ({
      opacity: 0,
      transform: decalerPx((-distance.glissement / 2) * sens),
      transition: sortie(duree.normale),
    }),
  };
}

/** Fond de la visionneuse qui apparaît / disparaît pendant le vol. */
export function transitionFondVisionneuse(sens: Sens, reduit: boolean): Transition {
  if (reduit) return fondu();
  const vol = dureeDe(volPhoto(sens));
  return sens === 1 ? { duration: vol * 0.6, ease: "linear" } : { duration: vol * 0.8, ease: "linear" };
}
