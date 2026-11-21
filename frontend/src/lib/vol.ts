// « Vol » d'un élément partagé entre deux écrans : la carte d'un voyage qui
// devient l'en-tête, la miniature qui devient la photo plein écran (et
// l'inverse au retour).
//
// Principe (FLIP) : un CLONE de l'image est posé, en position fixe, à la
// place et à la taille FINALES de l'élément d'arrivée ; on l'anime ensuite
// depuis le rectangle de départ jusque-là, uniquement par transform
// (translate + scale) : aucune mise en page recalculée pendant le vol.
//
// Quand le ratio change (carte 4:5 → en-tête très large), une simple mise à
// l'échelle déformerait la photo. L'image intérieure reçoit donc une
// contre-échelle calculée à chaque image, pour qu'elle « couvre » toujours la
// boîte courante (comme `object-fit: cover`) : la photo se recadre en
// grandissant, sans jamais s'étirer. Pas de fondu : le clone EST l'image, et
// l'élément d'arrivée apparaît à sa place à l'atterrissage.
//
// Le clone est indépendant des pages : la page de départ peut disparaître,
// la page d'arrivée défiler ou charger, le vol continue.

import { animate } from "motion/react";
import type { Transition } from "motion/react";

export type Rect = { x: number; y: number; w: number; h: number };
type Taille = { w: number; h: number };

export const rectDe = (el: Element): Rect => {
  const r = el.getBoundingClientRect();
  return { x: r.left, y: r.top, w: r.width, h: r.height };
};

const lerp = (a: number, b: number, p: number) => a + (b - a) * p;

/** Échelle qui fait couvrir la boîte par une image de taille `image` (object-fit: cover). */
export const echelleCouverture = (boite: Taille, image: Taille) => Math.max(boite.w / image.w, boite.h / image.h);

/**
 * Transforms du clone à l'avancement `p` (0 = départ, 1 = arrivée ; un
 * ressort peut dépasser 1). Le clone mesure `arrivee` ; son image intérieure
 * a le ratio de la photo et couvre `arrivee`.
 */
export function etatVol(depart: Rect, arrivee: Rect, photo: Taille, p: number) {
  const boite = {
    x: lerp(depart.x, arrivee.x, p),
    y: lerp(depart.y, arrivee.y, p),
    w: Math.max(1, lerp(depart.w, arrivee.w, p)),
    h: Math.max(1, lerp(depart.h, arrivee.h, p)),
  };
  const sx = boite.w / arrivee.w;
  const sy = boite.h / arrivee.h;
  // Échelle de la photo voulue pour la boîte courante, rapportée à celle de l'arrivée.
  const k = echelleCouverture(boite, photo) / echelleCouverture(arrivee, photo);
  return {
    boite: `translate(${boite.x - arrivee.x}px, ${boite.y - arrivee.y}px) scale(${sx}, ${sy})`,
    image: `scale(${k / sx}, ${k / sy})`,
  };
}

/** Rectangle visible au moins en partie dans la fenêtre ? */
export const estVisible = (r: Rect) =>
  r.w > 0 && r.h > 0 && r.y < window.innerHeight && r.y + r.h > 0 && r.x < window.innerWidth && r.x + r.w > 0;

export const selecteurTransition = (id: string) => `[data-transition-id="${CSS.escape(id)}"]`;

/** L'autre élément portant le même identifiant (celui de l'écran qu'on quitte), s'il est visible. */
export function trouverSource(id: string, cible: Element): Element | null {
  for (const el of document.querySelectorAll(selecteurTransition(id))) {
    if (el === cible || cible.contains(el) || el.contains(cible)) continue;
    if (estVisible(rectDe(el))) return el;
  }
  return null;
}

/** Image affichée par un élément (déjà chargée de préférence : aucun délai). */
function imageDe(el: Element): { src: string; taille: Taille } | null {
  const img = el.querySelector("img");
  if (!img) return null;
  const src = img.currentSrc || img.src;
  if (!src) return null;
  const w = img.naturalWidth || Number(img.getAttribute("width")) || 1;
  const h = img.naturalHeight || Number(img.getAttribute("height")) || 1;
  return { src, taille: { w, h } };
}

/** Image affichée par l'élément d'arrivée est-elle prête ? */
const arriveePrete = (el: Element) => {
  const img = el.querySelector("img");
  return !img || img.hasAttribute("data-chargee");
};

type Options = {
  source: Element;
  cible: Element;
  transition: Transition;
  /** Rideau (variante C du voyage) : couleur qui se déploie de la source à tout l'écran. */
  rideau?: string;
  /** Appelé à la fin du mouvement (avant que le clone soit retiré). */
  atterri?: () => void;
  /** Appelé quand l'élément d'arrivée est révélé et le clone retiré. */
  fin?: () => void;
};

let volEnCours: { arreter: () => void } | null = null;

/** Termine immédiatement le vol en cours (nouvelle navigation pendant un vol). */
export function arreterVol() {
  volEnCours?.arreter();
}

/**
 * Lance un vol de `source` vers `cible`. Pendant le vol, les deux éléments
 * réels sont masqués (opacity 0) ; à l'atterrissage, la cible réapparaît
 * telle quelle et le clone est retiré, dès que l'image de la cible est
 * chargée (sinon on garderait l'aperçu flou une fraction de seconde).
 */
export function lancerVol({ source, cible, transition, rideau, atterri, fin }: Options) {
  arreterVol();
  const image = imageDe(source) ?? imageDe(cible);
  const depart = rectDe(source);
  const arrivee = rectDe(cible);
  if (!image || !estVisible(depart) || arrivee.w === 0 || arrivee.h === 0) {
    atterri?.();
    fin?.();
    return;
  }

  const masques = [source, cible] as HTMLElement[];
  const opacites = masques.map((el) => el.style.opacity);
  masques.forEach((el) => (el.style.opacity = "0"));

  const calque = document.createElement("div");
  calque.setAttribute("aria-hidden", "true");
  calque.className = "calque-vol";

  let voile: HTMLDivElement | null = null;
  if (rideau) {
    voile = document.createElement("div");
    voile.className = "calque-vol-rideau";
    voile.style.background = rideau;
    calque.append(voile);
  }

  const boite = document.createElement("div");
  boite.className = "calque-vol-boite";
  Object.assign(boite.style, {
    left: `${arrivee.x}px`,
    top: `${arrivee.y}px`,
    width: `${arrivee.w}px`,
    height: `${arrivee.h}px`,
    borderRadius: getComputedStyle(cible).borderRadius,
  });
  const img = document.createElement("img");
  img.alt = "";
  img.src = image.src;
  img.decoding = "sync";
  const s = echelleCouverture(arrivee, image.taille);
  const iw = image.taille.w * s;
  const ih = image.taille.h * s;
  Object.assign(img.style, {
    width: `${iw}px`,
    height: `${ih}px`,
    left: `${(arrivee.w - iw) / 2}px`,
    top: `${(arrivee.h - ih) / 2}px`,
  });
  boite.append(img);
  calque.append(boite);
  document.body.append(calque);

  const appliquer = (p: number) => {
    const etat = etatVol(depart, arrivee, image.taille, p);
    boite.style.transform = etat.boite;
    img.style.transform = etat.image;
    if (voile) {
      const plein = { x: 0, y: 0, w: window.innerWidth, h: window.innerHeight };
      const r = { x: lerp(depart.x, plein.x, p), y: lerp(depart.y, plein.y, p), w: lerp(depart.w, plein.w, p), h: lerp(depart.h, plein.h, p) };
      voile.style.transform = `translate(${r.x}px, ${r.y}px) scale(${r.w / plein.w}, ${r.h / plein.h})`;
    }
  };
  appliquer(0);

  let termine = false;
  let aAtterri = false;
  const atterrir = () => {
    if (aAtterri) return;
    aAtterri = true;
    atterri?.();
  };
  const terminer = () => {
    if (termine) return;
    termine = true;
    controle.stop();
    atterrir();
    masques.forEach((el, i) => (el.style.opacity = opacites[i]));
    calque.remove();
    if (volEnCours === vol) volEnCours = null;
    fin?.();
  };
  const vol = { arreter: terminer };
  volEnCours = vol;

  const controle = animate(0, 1, { ...transition, onUpdate: appliquer });
  controle.then(() => {
    if (termine) return;
    appliquer(1);
    atterrir();
    // L'arrivée est révélée sous le clone ; le clone part dès qu'elle est nette.
    masques.forEach((el, i) => (el.style.opacity = opacites[i]));
    if (voile) voile.style.opacity = "0";
    if (arriveePrete(cible)) return terminer();
    const imgCible = cible.querySelector("img");
    imgCible?.addEventListener("load", () => requestAnimationFrame(terminer), { once: true });
    setTimeout(terminer, 1200);
  });
}
