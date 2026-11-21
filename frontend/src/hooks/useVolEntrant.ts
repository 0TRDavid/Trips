import { useLayoutEffect } from "react";
import { lancerVol, selecteurTransition, trouverSource } from "../lib/vol";
import type { Transition } from "motion/react";

type Vol = { transition: Transition };

/**
 * À l'arrivée d'un élément partagé (`data-transition-id`), le fait « voler »
 * depuis l'élément de même identifiant encore affiché par l'écran qu'on
 * quitte (voir lib/vol.ts). `vol()` renvoie null quand il ne faut pas voler
 * (premier affichage, réduction des animations…).
 *
 * Au montage seulement : la cible est masquée avant la première peinture,
 * puis le vol est lancé à l'image suivante, quand la restauration du
 * défilement a eu lieu (sinon on mesurerait l'arrivée au mauvais endroit).
 */
export function useVolEntrant(id: string, cible: () => HTMLElement | null, vol: () => Vol | null) {
  useLayoutEffect(() => {
    const el = cible();
    const options = el ? vol() : null;
    if (!el || !options) return;
    // Rien à faire si l'écran qu'on quitte n'a pas d'élément de même
    // identifiant (sinon chaque vignette d'une liste clignoterait une image).
    if (document.querySelectorAll(selecteurTransition(id)).length < 2) return;
    el.style.opacity = "0";
    const image = requestAnimationFrame(() => {
      el.style.opacity = "";
      const source = trouverSource(id, el);
      if (source) lancerVol({ source, cible: el, ...options });
    });
    return () => {
      cancelAnimationFrame(image);
      el.style.opacity = "";
    };
    // Au montage seulement : un nouveau rendu ne relance pas le vol.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
}
