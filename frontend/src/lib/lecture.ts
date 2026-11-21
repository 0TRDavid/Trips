// Photos animées de la page jour : une seule joue à la fois, celle dont le
// centre est le plus près du centre de l'écran.
//
// Chaque <PhotoAnimee> de la galerie s'inscrit auprès d'un ChefDeLecture
// (fourni par la galerie, composants/GaleriePhotos.tsx). Un IntersectionObserver
// commun tient la liste des photos à moitié visibles (quelques-unes au plus) ;
// on n'élit qu'entre elles, au défilement (une fois par image au plus) et
// quand cette liste change. L'élue est prévenue (rappel `true`), l'ancienne
// aussi (`false`). Une photo qui a fini de jouer se retire (`terminer`) : elle
// redevient une image fixe et l'élection passe à la suivante.
//
// Pause générale (`suspendre`) : visionneuse ouverte, onglet caché.
//
// Une photo n'est élue qu'après être restée la plus proche du centre pendant
// `defilement.election` : pendant un défilement continu, on ne télécharge ni
// ne joue les vidéos qu'on ne fait que survoler.

import { defilement } from "./mouvement";

export type Boite = { top: number; bottom: number };

/** Index de la boîte dont le centre est le plus proche de `centre` ; -1 si aucune. */
export function plusProcheDuCentre(boites: Boite[], centre: number): number {
  let meilleur = -1;
  let ecart = Infinity;
  boites.forEach((b, i) => {
    const e = Math.abs((b.top + b.bottom) / 2 - centre);
    if (e < ecart) {
      ecart = e;
      meilleur = i;
    }
  });
  return meilleur;
}

type Rappel = (elue: boolean) => void;

export class ChefDeLecture {
  private rappels = new Map<Element, Rappel>();
  private visibles = new Set<Element>();
  private elue: Element | null = null;
  private suspendu = false;
  private cache = false;
  private image = 0;
  private observateur: IntersectionObserver | null = null;
  private ecoute = false;
  private pretendante: Element | null = null;
  private minuterie: ReturnType<typeof setTimeout> | undefined;

  constructor() {
    if (typeof window === "undefined") return;
    this.observateur = new IntersectionObserver(
      (entrees) => {
        for (const e of entrees) {
          if (e.isIntersecting && e.intersectionRatio >= 0.5) this.visibles.add(e.target);
          else this.visibles.delete(e.target);
        }
        this.ecouter(this.visibles.size > 0);
        this.elire();
      },
      { threshold: [0, 0.5] },
    );
    document.addEventListener("visibilitychange", this.surVisibilite);
  }

  inscrire(element: Element, rappel: Rappel): () => void {
    this.rappels.set(element, rappel);
    this.observateur?.observe(element);
    return () => this.retirer(element);
  }

  /** La photo a fini de jouer : elle ne sera plus élue. */
  terminer(element: Element) {
    this.retirer(element);
  }

  suspendre(suspendu: boolean) {
    this.suspendu = suspendu;
    this.elire();
  }

  detruire() {
    this.observateur?.disconnect();
    this.ecouter(false);
    cancelAnimationFrame(this.image);
    clearTimeout(this.minuterie);
    document.removeEventListener("visibilitychange", this.surVisibilite);
    this.rappels.clear();
    this.visibles.clear();
    this.elue = null;
  }

  private retirer(element: Element) {
    this.observateur?.unobserve(element);
    this.visibles.delete(element);
    this.rappels.delete(element);
    if (this.elue === element) {
      this.elue = null;
      this.elire();
    }
  }

  private surVisibilite = () => {
    this.cache = document.visibilityState === "hidden";
    this.elire();
  };

  private surDefilement = () => {
    if (this.image) return;
    this.image = requestAnimationFrame(() => {
      this.image = 0;
      this.elire();
    });
  };

  private ecouter(oui: boolean) {
    if (oui === this.ecoute) return;
    this.ecoute = oui;
    if (oui) window.addEventListener("scroll", this.surDefilement, { passive: true });
    else window.removeEventListener("scroll", this.surDefilement);
  }

  private meilleure(): Element | null {
    if (this.suspendu || this.cache || this.visibles.size === 0) return null;
    const candidates = [...this.visibles];
    const i = plusProcheDuCentre(
      candidates.map((c) => c.getBoundingClientRect()),
      window.innerHeight / 2,
    );
    return candidates[i] ?? null;
  }

  private elire() {
    const nouvelle = this.meilleure();
    if (nouvelle === this.elue) {
      this.pretendante = null;
      clearTimeout(this.minuterie);
      return;
    }
    // L'élue n'est plus la meilleure : elle s'arrête tout de suite.
    if (this.elue) {
      const ancienne = this.elue;
      this.elue = null;
      this.rappels.get(ancienne)?.(false);
    }
    if (!nouvelle || nouvelle === this.pretendante) return;
    this.pretendante = nouvelle;
    clearTimeout(this.minuterie);
    this.minuterie = setTimeout(() => {
      const confirmee = this.meilleure();
      this.pretendante = null;
      if (confirmee !== nouvelle) return this.elire();
      this.elue = nouvelle;
      this.rappels.get(nouvelle)?.(true);
    }, defilement.election * 1000);
  }
}
