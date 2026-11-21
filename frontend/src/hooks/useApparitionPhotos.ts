import { useEffect, type RefObject } from "react";
import { apparitionPhoto, reglages } from "../lib/mouvement";
import { mouvementReduit } from "./useMouvementReduit";

/**
 * Apparition des photos (et des blocs du récit) de la galerie à leur entrée
 * dans l'écran, UNE fois. Les éléments concernés portent `data-apparition`.
 *
 * - Un seul IntersectionObserver pour toute la galerie, pas un par photo.
 * - Mesure une image après le montage, quand le défilement a été restauré
 *   (retour arrière) : tout ce qui est déjà à l'écran ou au-dessus est
 *   considéré comme vu et ne bouge pas. Seuls les éléments sous l'écran
 *   passent en attente (`data-apparition="attente"` → opacity 0, invisible
 *   puisque hors de l'écran).
 * - À l'entrée : element.animate() (joué par le navigateur, hors du fil
 *   principal), décalé dans le lot d'entrées, puis l'élément n'est plus
 *   observé : jamais rejoué. La page reste montée sous la visionneuse : rien
 *   ne rejoue à sa fermeture.
 */
export function useApparitionPhotos(racine: RefObject<HTMLElement | null>, actif: boolean) {
  useEffect(() => {
    const conteneur = racine.current;
    if (!actif || !conteneur) return;
    const variante = reglages().apparition;
    if (variante === "aucune") return;

    let observateur: IntersectionObserver | null = null;
    const image = requestAnimationFrame(() => {
      const reduit = mouvementReduit();
      const bas = window.innerHeight;
      const enAttente: HTMLElement[] = [];
      for (const el of conteneur.querySelectorAll<HTMLElement>("[data-apparition]")) {
        if (el.getBoundingClientRect().top < bas) continue;
        el.dataset.apparition = "attente";
        enAttente.push(el);
      }
      if (enAttente.length === 0) return;
      observateur = new IntersectionObserver(
        (entrees) => {
          let rang = 0;
          for (const e of entrees) {
            if (!e.isIntersecting) continue;
            const el = e.target as HTMLElement;
            observateur?.unobserve(el);
            el.dataset.apparition = "vue";
            const a = apparitionPhoto(variante, reduit, rang++);
            if (a) el.animate(a.images, a.options);
          }
        },
        // Un peu avant le bas de l'écran : l'élément est déjà apparu quand on le regarde.
        { rootMargin: "0px 0px -6% 0px" },
      );
      enAttente.forEach((el) => observateur!.observe(el));
    });

    return () => {
      cancelAnimationFrame(image);
      observateur?.disconnect();
      // Démontage ou réglage changé : plus rien ne doit rester caché.
      for (const el of conteneur.querySelectorAll<HTMLElement>('[data-apparition="attente"]')) el.dataset.apparition = "vue";
    };
  }, [racine, actif]);
}
