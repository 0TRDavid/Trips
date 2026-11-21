// Système de mouvement du site : TOUTES les durées, courbes et ressorts sont
// ici. Les composants n'écrivent jamais de valeur en dur, ils appellent les
// fonctions de ce fichier, qui appliquent les règles :
//   - une sortie est plus rapide que l'entrée correspondante (facteurSortie) ;
//   - le sens d'un glissement suit le sens de la navigation (sens = 1 : on
//     avance, -1 : on recule ; voir lib/navigation.ts) ;
//   - on n'anime que transform (x, y, scale) et opacity : rien qui oblige le
//     navigateur à recalculer la mise en page (test dans lib.test.ts) ;
//   - « réduire les animations » : tout devient un simple fondu.
//
// En dev, la page /labo peut surcharger les variantes, ralentir le temps et
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

// --- Variantes comparées dans /labo -----------------------------------------------

export type NomTransition = "voyage" | "photo" | "jour" | "page";
export type Variante = "A" | "B" | "C";

/** Libellés des variantes, pour le labo. `null` : variante inexistante. */
export const VARIANTES: Record<NomTransition, Record<Variante, string | null>> = {
  voyage: {
    A: "Ressort doux : l'image grandit avec un léger rebond, la page monte en cascade",
    B: "Cinéma : expo-out sans rebond, la page apparaît après l'atterrissage",
    C: "Rideau : le fond teinté du voyage se déploie depuis la carte",
  },
  photo: {
    A: "Ressort : ouverture souple, fermeture nerveuse",
    B: "Expo : ouverture 0,38 s, fermeture 0,25 s, sans rebond",
    C: "Expo + tirer vers le bas pour fermer (téléphone)",
  },
  jour: {
    A: "Page entière : l'ancienne part sur le côté, la nouvelle arrive de l'autre",
    B: "Glissement court : 40 px et fondu",
    C: "Parallaxe : l'ancienne recule de 30 %, la nouvelle arrive par-dessus",
  },
  page: {
    A: "Fondu et montée de 12 px",
    B: null,
    C: null,
  },
};

export type Reglages = {
  variantes: Record<NomTransition, Variante>;
  /** Multiplicateur des durées (1 = normal, 4 = quatre fois plus lent). */
  ralenti: number;
  /** Simule `prefers-reduced-motion: reduce`. */
  reduit: boolean;
};

export const REGLAGES_DEFAUT: Reglages = {
  variantes: { voyage: "A", photo: "A", jour: "B", page: "A" },
  ralenti: 1,
  reduit: false,
};

export const CLE_REGLAGES = "carnet-labo";
export const EVENEMENT_REGLAGES = "carnet-reglages";

let cache: Reglages | null = null;

function lireReglages(): Reglages {
  try {
    const brut = localStorage.getItem(CLE_REGLAGES);
    if (!brut) return REGLAGES_DEFAUT;
    const lu = JSON.parse(brut) as Partial<Reglages>;
    return {
      variantes: { ...REGLAGES_DEFAUT.variantes, ...lu.variantes },
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

export const variante = (nom: NomTransition): Variante => reglages().variantes[nom];

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
 * - jour : jour ↔ jour du même voyage (glissement directionnel) ;
 * - page : tout le reste.
 */
export type GenreNavigation = "aucune" | "fondu" | "voyage" | "jour" | "page";
export type Sens = 1 | -1;
export type Navigation = { genre: GenreNavigation; sens: Sens };

const AUCUNE: Transition = { duration: 0 };

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
    if (genre === "jour") {
      const v = variante("jour");
      if (v === "A" || v === "C") return { opacity: 1, x: `${100 * sens}%` };
      return { opacity: 0, x: distance.glissement * sens };
    }
    if (genre === "voyage") return { opacity: 0 };
    return { opacity: 0, y: distance.montee * sens };
  },
  visible: (nav: Navigation) => {
    const { genre } = nav;
    const fin = { opacity: 1, x: 0, y: 0 };
    if (genre === "aucune") return { ...fin, transition: AUCUNE };
    if (genre === "fondu") return { ...fin, transition: fondu() };
    if (genre === "jour") {
      const v = variante("jour");
      return { ...fin, transition: entree(v === "B" ? duree.normale : duree.lente) };
    }
    if (genre === "voyage") {
      // La page arrive vite ; ses blocs (<Apparition>) suivent en cascade, après
      // l'atterrissage de l'image en variante B.
      const apresVol = variante("voyage") === "B" ? dureeDe(volVoyage(1)) : duree.rapide;
      return {
        ...fin,
        transition: {
          ...entree(duree.rapide),
          delayChildren: t(apresVol),
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
      const v = variante("jour");
      if (v === "A") return { x: `${-100 * sens}%`, transition: { ...sortie(duree.lente), ease: courbe.entree } };
      if (v === "C") return { x: `${-30 * sens}%`, opacity: 0.3, transition: sortie(duree.lente) };
      return { opacity: 0, x: (-distance.glissement / 2) * sens, transition: sortie(duree.normale) };
    }
    if (genre === "voyage") return { opacity: 0, transition: sortie(duree.rapide) };
    return { opacity: 0, y: (-distance.montee / 2) * sens, transition: sortie(duree.normale) };
  },
};

/** Bloc qui apparaît en cascade dans une page (hérite de `variantesPage`). */
export function variantesBloc(reduit: boolean): Variants {
  if (reduit) return { initial: { opacity: 0 }, visible: () => ({ opacity: 1, transition: fondu() }) };
  return {
    initial: { opacity: 0, y: distance.cascade },
    visible: () => ({ opacity: 1, y: 0, transition: entree(duree.normale) }),
  };
}

// --- Éléments partagés (lib/vol.ts) ----------------------------------------------

/** Vol carte ↔ en-tête du voyage. `sens` 1 : vers l'en-tête ; -1 : retour à la carte. */
export function volVoyage(sens: Sens): Transition {
  const retour = sens === -1 ? facteurSortie : 1;
  if (variante("voyage") === "B") return { duration: t(duree.lente * retour), ease: courbe.entree };
  return ressortDe("partage", retour);
}

/** Vol miniature ↔ plein écran. `sens` 1 : ouverture ; -1 : fermeture. */
export function volPhoto(sens: Sens): Transition {
  if (variante("photo") === "A") return sens === 1 ? ressortDe("partage") : ressortDe("vif");
  return sens === 1 ? { duration: t(0.38), ease: courbe.entree } : { duration: t(0.25), ease: courbe.entree };
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
    initial: (sens: Sens) => ({ opacity: 0, x: distance.glissement * sens }),
    visible: () => ({ opacity: 1, x: 0, transition: entree(duree.normale) }),
    sortie: (sens: Sens) => ({ opacity: 0, x: (-distance.glissement / 2) * sens, transition: sortie(duree.normale) }),
  };
}

/** Fond de la visionneuse qui apparaît / disparaît pendant le vol. */
export function transitionFondVisionneuse(sens: Sens, reduit: boolean): Transition {
  if (reduit) return fondu();
  const vol = dureeDe(volPhoto(sens));
  return sens === 1 ? { duration: vol * 0.6, ease: "linear" } : { duration: vol * 0.8, ease: "linear" };
}
