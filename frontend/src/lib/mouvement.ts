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

/** Page jour (étape 6b) : variantes comparées au labo. */
export const VARIANTES_APPARITION = ["aucune", "fondu", "montee", "cascade"] as const;
export const VARIANTES_COLLANT = ["pousse", "bandeau"] as const;
export type VarianteApparition = (typeof VARIANTES_APPARITION)[number];
export type VarianteCollant = (typeof VARIANTES_COLLANT)[number];

export type Reglages = {
  /** Multiplicateur des durées (1 = normal, 4 = quatre fois plus lent). */
  ralenti: number;
  /** Simule `prefers-reduced-motion: reduce`. */
  reduit: boolean;
  /** Apparition des photos à leur entrée dans l'écran. */
  apparition: VarianteApparition;
  /** Intitulé d'heure collant : chaque intitulé poussé par le suivant, ou un bandeau unique. */
  collant: VarianteCollant;
};

export const REGLAGES_DEFAUT: Reglages = {
  ralenti: 1,
  reduit: false,
  apparition: "montee",
  collant: "pousse",
};

const choix = <T extends string>(valeurs: readonly T[], lu: unknown, defaut: T): T =>
  valeurs.includes(lu as T) ? (lu as T) : defaut;

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
      apparition: choix(VARIANTES_APPARITION, lu.apparition, REGLAGES_DEFAUT.apparition),
      collant: choix(VARIANTES_COLLANT, lu.collant, REGLAGES_DEFAUT.collant),
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

// --- Page jour : défilement (étape 6b) -------------------------------------------
// Animations jouées par le navigateur (element.animate, ou Motion `scroll()`
// branché sur une ViewTimeline native) : rien n'est calculé à chaque image
// sur le fil principal.

/** Réglages du défilement de la page jour. */
export const defilement = {
  /** Ouverture plein écran : étapes (précision du recadrage), part de la
   *  course consacrée au rétrécissement (le reste : le titre passe sous la
   *  photo), glissement (px) du titre qui arrive de la gauche, course minimale
   *  (fraction de la hauteur d'écran), marge (px) entre le titre et le bas
   *  de la photo (la place de l'indication « Glisser »), part de la course au
   *  bout de laquelle l'indication a disparu, amplitude (px) et durée (s) de
   *  son rebond. */
  plein: { etapes: 16, rapport: 0.7, glissementTitre: 56, courseMin: 0.6, margeTitre: 88, finIndice: 0.15, finRecit: 0.3, rebond: 8, dureeRebond: 1.6 },
  /** Apparition des photos : distance (px), décalage entre deux photos d'un même lot (s), plafond du décalage. */
  apparition: { montee: 12, cascade: 28, intervalle: 0.04, intervalleCascade: 0.07, maxDecales: 6 },
  /** Galerie plein écran (page par page) : silence (s) de la
   *  molette au-delà duquel un cran est un nouveau geste ; en deçà, il fait
   *  partie du même geste et il est absorbé. */
  aimant: { calme: 0.2 },
  /** Roulement de l'heure dans le bandeau (fraction de la hauteur du libellé). */
  roulement: 0.6,
  /** Photo animée : temps (s) pendant lequel elle doit rester la plus proche du
   *  centre avant de jouer (on ne télécharge pas les vidéos survolées). */
  election: 0.2,
} as const;

export type AnimationNative = { images: Keyframe[]; options: KeyframeAnimationOptions };

/**
 * Apparition d'une photo (ou d'un bloc du récit) à son entrée dans l'écran,
 * pour `element.animate()`. `rang` : position dans le lot de photos entrées
 * ensemble (décalage plafonné). Null : aucune animation.
 * `fill: "backwards"` tient l'état de départ pendant le délai ; à la fin,
 * l'animation disparaît et l'élément retrouve son style (aucun transform).
 */
export function apparitionPhoto(variante: VarianteApparition, reduit: boolean, rang: number): AnimationNative | null {
  if (variante === "aucune") return null;
  const a = defilement.apparition;
  if (reduit || variante === "fondu") {
    const d = reduit ? DUREE_REDUITE : duree.normale;
    return {
      images: [{ opacity: 0 }, { opacity: 1 }],
      options: { duration: t(d) * 1000, delay: reduit ? 0 : t(Math.min(rang, a.maxDecales) * a.intervalle) * 1000, easing: "linear", fill: "backwards" },
    };
  }
  const cascade = variante === "cascade";
  const dy = cascade ? a.cascade : a.montee;
  const pas = cascade ? a.intervalleCascade : a.intervalle;
  return {
    images: [
      { opacity: 0, transform: `translate(0px, ${dy}px)` },
      { opacity: 1, transform: "none" },
    ],
    options: {
      duration: t(cascade ? duree.lente : duree.normale) * 1000,
      delay: t(Math.min(rang, a.maxDecales) * pas) * 1000,
      easing: cssBezier(courbe.entree),
      fill: "backwards",
    },
  };
}

/** Changement d'heure dans le bandeau : `sens` 1 = on descend dans la journée. */
export function roulementHeure(sens: Sens, reduit: boolean): { entree: AnimationNative; sortie: AnimationNative } {
  if (reduit) {
    const f = { duration: t(DUREE_REDUITE) * 1000, easing: "linear" };
    return {
      entree: { images: [{ opacity: 0 }, { opacity: 1 }], options: f },
      sortie: { images: [{ opacity: 1 }, { opacity: 0 }], options: { ...f, fill: "forwards" } },
    };
  }
  const h = defilement.roulement * 100 * sens;
  return {
    entree: {
      images: [{ opacity: 0, transform: `translate(0px, ${h}%)` }, { opacity: 1, transform: "none" }],
      options: { duration: t(duree.normale) * 1000, easing: cssBezier(courbe.entree) },
    },
    sortie: {
      images: [{ opacity: 1, transform: "translate(0px, 0%)" }, { opacity: 0, transform: `translate(0px, ${-h}%)` }],
      options: { duration: t(duree.normale * facteurSortie) * 1000, easing: cssBezier(courbe.sortie), fill: "forwards" },
    },
  };
}

/** Mesures de l'ouverture plein écran, en px (coordonnées de la page) : haut
 *  du cadre, sa hauteur dans la page (le bandeau), sa hauteur visible au départ
 *  (jusqu'au bas de l'écran) et le bas du titre à sa place, sous le bandeau. */
export type MesuresPlein = { haut: number; bandeau: number; plein: number; basTitre: number };

type ImagesPlein = {
  cadre: { transform: string[] };
  photo: { transform: string[] };
  voile: { opacity: number[] };
  titreSurPhoto: { opacity: number[]; transform: string[] };
  titre: { opacity: number[]; transform: string[] };
  indice: { opacity: number[] };
  /** Récit posé sur la couverture : s'efface au début de la course. */
  recit: { opacity: number[] };
};

/**
 * Ouverture plein écran, liée au défilement. Images régulièrement espacées
 * (une par étape) :
 * - de 0 à `rapport` : le cadre, haut de `bandeau` dans la page, passe de
 *   « étiré jusqu'au bas de l'écran » (scaleY) à sa taille. La photo, haute de
 *   `plein`, est contre-étirée et recentrée : jamais déformée, seulement
 *   recadrée (plusieurs étapes, car 1/s n'est pas linéaire). Le titre reste
 *   collé au bas de la photo, posé dessus ;
 * - de `rapport` à 1 : le titre passe sous la photo, à sa place, et sa
 *   version claire cède la place au titre normal ; le voile s'efface.
 */
export function ouverturePleinEcran({ haut, bandeau, plein, basTitre }: MesuresPlein): ImagesPlein {
  const { etapes: n, rapport, margeTitre } = defilement.plein;
  const s0 = Math.max(plein / bandeau, 1);
  const collé = (s: number) => Math.min(haut + bandeau * s - margeTitre - basTitre, 0);
  const finCollé = collé(1);
  const o: ImagesPlein = {
    cadre: { transform: [] },
    photo: { transform: [] },
    voile: { opacity: [] },
    titreSurPhoto: { opacity: [], transform: [] },
    titre: { opacity: [], transform: [] },
    indice: { opacity: [] },
    recit: { opacity: [] },
  };
  for (let i = 0; i <= n; i++) {
    const p = i / n;
    const q = Math.min(p / rapport, 1); // avancement du rétrécissement
    const r = p <= rapport ? 0 : (p - rapport) / (1 - rapport); // avancement du passage sous la photo
    const s = s0 + (1 - s0) * q;
    // Photo de hauteur `plein` dans un cadre de hauteur `bandeau` étiré de s :
    // scaleY(1/s) l'annule, translateY la centre dans le cadre.
    o.cadre.transform.push(`scale(1, ${s})`);
    o.photo.transform.push(`translate(0px, ${bandeau / 2 - plein / (2 * s)}px) scale(1, ${1 / s})`);
    const ty = p <= rapport ? collé(s) : finCollé * (1 - r);
    const decalage = `translate(0px, ${ty}px)`;
    o.titre.transform.push(decalage);
    o.titreSurPhoto.transform.push(decalage);
    o.titreSurPhoto.opacity.push(1 - r);
    o.titre.opacity.push(r);
    o.voile.opacity.push(1 - r);
    // L'indication « Glisser » s'efface dès les premiers pixels de défilement.
    o.indice.opacity.push(Math.max(1 - p / defilement.plein.finIndice, 0));
    o.recit.opacity.push(Math.max(1 - p / defilement.plein.finRecit, 0));
  }
  return o;
}

/** Course de l'ouverture (px de défilement) : au moins une fraction de l'écran, pour qu'elle ne soit pas brusque. */
export const courseOuverture = (m: MesuresPlein, hauteurEcran: number) =>
  Math.max((m.plein - m.bandeau) / defilement.plein.rapport, hauteurEcran * defilement.plein.courseMin, 1);

/** Repère de la frise des heures : glisse d'un libellé à l'autre (px, depuis le haut de la frise). */
export function deplacementFrise(depart: number, arrivee: number, reduit: boolean): AnimationNative {
  if (reduit) {
    return { images: [{ opacity: 0 }, { opacity: 1 }], options: { duration: t(DUREE_REDUITE) * 1000, easing: "linear" } };
  }
  return {
    images: [{ transform: `translate(0px, ${depart}px)` }, { transform: `translate(0px, ${arrivee}px)` }],
    options: { duration: t(duree.normale) * 1000, easing: cssBezier(courbe.standard) },
  };
}

/** Barre du jour (en-tête compact sur la photo de couverture) : apparaît en
 *  descendant du haut de l'écran, repart plus vite qu'elle n'est venue. */
export function barreJour(visible: boolean, reduit: boolean): AnimationNative {
  const cachee = { opacity: 0, transform: "translate(0px, -100%)" };
  const montree = { opacity: 1, transform: "none" };
  if (reduit) {
    return {
      images: visible ? [{ opacity: 0 }, { opacity: 1 }] : [{ opacity: 1 }, { opacity: 0 }],
      options: { duration: t(DUREE_REDUITE) * 1000, easing: "linear" },
    };
  }
  return visible
    ? { images: [cachee, montree], options: { duration: t(duree.normale) * 1000, easing: cssBezier(courbe.entree) } }
    : { images: [{ ...montree, transform: "translate(0px, 0%)" }, cachee], options: { duration: t(duree.normale * facteurSortie) * 1000, easing: cssBezier(courbe.sortie) } };
}

/** Récit du jour sur la couverture (variantes plein écran) : arrive de la droite au premier cran. */
export function recitCouverture(visible: boolean, reduit: boolean): AnimationNative {
  const cache = { opacity: 0, transform: `translate(${defilement.plein.glissementTitre}px, 0px)` };
  const montre = { opacity: 1, transform: "none" };
  if (reduit) {
    return {
      images: visible ? [{ opacity: 0 }, { opacity: 1 }] : [{ opacity: 1 }, { opacity: 0 }],
      options: { duration: t(DUREE_REDUITE) * 1000, easing: "linear" },
    };
  }
  return visible
    ? { images: [cache, montre], options: { duration: t(duree.lente) * 1000, easing: cssBezier(courbe.entree) } }
    : { images: [{ ...montre, transform: "translate(0px, 0px)" }, cache], options: { duration: t(duree.normale * facteurSortie) * 1000, easing: cssBezier(courbe.sortie) } };
}

/** Rebond de la flèche « Glisser » (en boucle). Null en mouvement réduit : elle reste immobile. */
export function rebondIndice(reduit: boolean): AnimationNative | null {
  if (reduit) return null;
  const { rebond, dureeRebond } = defilement.plein;
  return {
    images: [
      { transform: "translate(0px, 0px)" },
      { transform: `translate(0px, ${rebond}px)` },
      { transform: "translate(0px, 0px)" },
    ],
    options: { duration: t(dureeRebond) * 1000, easing: cssBezier(courbe.standard), iterations: Infinity },
  };
}

/** Le titre de l'ouverture plein écran arrive de la gauche (une fois). */
export function arriveeTitre(reduit: boolean): AnimationNative {
  if (reduit) {
    return { images: [{ opacity: 0 }, { opacity: 1 }], options: { duration: t(DUREE_REDUITE) * 1000, easing: "linear", fill: "backwards" } };
  }
  return {
    images: [
      { opacity: 0, transform: `translate(${-defilement.plein.glissementTitre}px, 0px)` },
      { opacity: 1, transform: "none" },
    ],
    options: { duration: t(duree.lente) * 1000, easing: cssBezier(courbe.entree), fill: "backwards" },
  };
}

function cssBezier(c: readonly [number, number, number, number]): string {
  return `cubic-bezier(${c.join(", ")})`;
}
