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
//
// Fluidité : toute la trajectoire (ressort compris) est calculée d'avance en
// une soixantaine d'étapes par seconde, puis confiée au navigateur
// (Web Animations, transform seulement) qui la joue HORS du fil principal.
// Le montage de la page d'arrivée (carte, photos) peut bloquer ce fil
// pendant 100 ms et plus : un vol calculé image par image en JavaScript
// saccadait à chaque blocage.

import { cubicBezier, spring } from "motion/react";
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

const IMAGES_PAR_SECONDE = 60;

/**
 * Avancement 0 → 1 (un ressort peut dépasser 1) échantillonné à intervalles
 * réguliers, et durée totale en ms. Gère les ressorts et les courbes de Bézier.
 */
export function echantillonner(transition: Transition): { avancements: number[]; duree: number } {
  const tr = transition as { type?: string; duration?: number; ease?: number[]; visualDuration?: number; bounce?: number };
  const pas = 1000 / IMAGES_PAR_SECONDE;
  const avancements: number[] = [];
  if (tr.type === "spring") {
    const generateur = spring({ keyframes: [0, 1], visualDuration: tr.visualDuration, bounce: tr.bounce });
    for (let t = 0; t < 5000; t += pas) {
      const { value, done } = generateur.next(t);
      avancements.push(value);
      if (done) break;
    }
    avancements[avancements.length - 1] = 1;
    return { avancements, duree: (avancements.length - 1) * pas };
  }
  const duree = (tr.duration ?? 0.3) * 1000;
  const courbe = tr.ease && tr.ease.length === 4 ? cubicBezier(tr.ease[0], tr.ease[1], tr.ease[2], tr.ease[3]) : (x: number) => x;
  const n = Math.max(2, Math.ceil(duree / pas) + 1);
  for (let i = 0; i < n; i++) avancements.push(courbe(i / (n - 1)));
  return { avancements, duree };
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
export function lancerVol({ source, cible, transition, atterri, fin }: Options) {
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

  // Trajectoire calculée d'avance, jouée par le navigateur (voir en tête).
  const { avancements, duree } = echantillonner(transition);
  const etats = avancements.map((p) => etatVol(depart, arrivee, image.taille, p));
  const options: KeyframeAnimationOptions = { duration: Math.max(duree, 1), easing: "linear", fill: "forwards" };
  const animations = [
    boite.animate(etats.map((e) => ({ transform: e.boite })), options),
    img.animate(etats.map((e) => ({ transform: e.image })), options),
  ];

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
    animations.forEach((a) => a.cancel());
    atterrir();
    masques.forEach((el, i) => (el.style.opacity = opacites[i]));
    calque.remove();
    if (volEnCours === vol) volEnCours = null;
    fin?.();
  };
  const vol = { arreter: terminer };
  volEnCours = vol;

  animations[0].finished.then(
    () => {
      if (termine) return;
      atterrir();
      // L'arrivée est révélée sous le clone ; le clone part dès qu'elle est nette.
      masques.forEach((el, i) => (el.style.opacity = opacites[i]));
      if (arriveePrete(cible)) return terminer();
      const imgCible = cible.querySelector("img");
      imgCible?.addEventListener("load", () => requestAnimationFrame(terminer), { once: true });
      setTimeout(terminer, 1200);
    },
    () => {
      /* annulée par terminer() */
    },
  );
}
