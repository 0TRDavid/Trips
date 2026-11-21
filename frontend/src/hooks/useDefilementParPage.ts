import { useEffect, type RefObject } from "react";
import { defilement } from "../lib/mouvement";
import { mouvementReduit } from "./useMouvementReduit";

/**
 * Défilement page par page (galerie plein écran, ordinateur) :
 * un geste de molette (ou flèche, Page suivante/précédente, Espace) amène le
 * point d'arrêt suivant ou précédent, en un glissement joué par le navigateur
 * (`scrollTo` smooth, instantané en mouvement réduit).
 *
 * La molette est interceptée (`preventDefault`) : pendant le glissement et
 * tant que les crans continuent d'arriver (`defilement.aimant.calme`), ils
 * sont absorbés. Plusieurs crans rapides = un seul geste = une seule page ;
 * rien ne vient contrarier le glissement (c'est ce qui le rendait saccadé).
 *
 * Points d'arrêt : le haut de la page, les éléments `[data-ancre]` (pages de la
 * mosaïque, blocs du récit) sous la barre et l'heure (`haut`, px), et le bas de page.
 * Un bloc plus haut que l'écran (long récit) se lit librement : la molette
 * garde son comportement normal tant qu'il reste du bloc à parcourir.
 *
 * Couverture : si le récit y est posé (`[data-recit-couverture]`, EnteteJour),
 * le premier cran vers le bas le révèle sans défiler (événement
 * `carnet:recit-couverture`), le suivant glisse vers la journée ; vers le haut,
 * l'inverse. Un récit trop long pour l'écran défile dans son cadre.
 *
 * Au bout de la journée, un cran de plus mène au jour suivant (`auBout`) ;
 * l'élan de ce geste est absorbé par la nouvelle page (dernier cran partagé).
 */
let dernierCran = 0; // horodatage du dernier cran, partagé d'une page à l'autre

export const EVENEMENT_RECIT = "carnet:recit-couverture";
export function useDefilementParPage(
  racine: RefObject<HTMLElement | null>,
  actif: boolean,
  haut: number,
  auBout?: () => void,
) {
  useEffect(() => {
    const el = racine.current;
    if (!actif || !el) return;
    const calme = defilement.aimant.calme * 1000;
    const avecScrollend = "onscrollend" in window;
    let enCours = false; // glissement lancé par nous

    const blocs = () =>
      [...el.querySelectorAll<HTMLElement>("[data-ancre]")].map((b) => {
        const r = b.getBoundingClientRect();
        return { haut: r.top + window.scrollY - haut, bas: r.bottom + window.scrollY };
      });

    /** Dans un bloc plus haut que l'écran, reste-t-il à lire dans ce sens ? */
    const lectureLibre = (sens: 1 | -1) => {
      const y = window.scrollY;
      const ecran = window.innerHeight;
      return blocs().some(
        (b) =>
          b.bas - b.haut > ecran &&
          (sens > 0 ? b.haut <= y + 1 && b.bas > y + ecran + 1 : b.haut < y - 1 && b.bas >= y + ecran - 1),
      );
    };

    const terminer = () => {
      enCours = false;
    };

    /** Étape « récit » de la couverture : vrai si le geste l'a consommée. */
    const etapeCouverture = (sens: 1 | -1) => {
      const recit = document.querySelector<HTMLElement>("[data-recit-couverture]");
      if (!recit || window.scrollY > 1) return false;
      const montre = recit.hasAttribute("data-montre");
      if (sens > 0 === montre) return false;
      window.dispatchEvent(new CustomEvent(EVENEMENT_RECIT, { detail: sens > 0 }));
      return true;
    };

    const aller = (sens: 1 | -1) => {
      if (etapeCouverture(sens)) return;
      const y = window.scrollY;
      const max = document.documentElement.scrollHeight - window.innerHeight;
      const ancres = blocs().map((b) => b.haut);
      // Avec un jour suivant, la dernière page mène directement à lui (le bas
      // de page, jour précédent / suivant, n'est plus un arrêt).
      const fin = auBout && ancres.length ? [] : [max];
      const points = [0, ...ancres, ...fin].filter((p) => p >= 0 && p <= max).sort((a, b) => a - b);
      const cible = sens > 0 ? points.find((p) => p > y + 1) : [...points].reverse().find((p) => p < y - 1);
      if (cible === undefined) {
        if (sens > 0 && auBout) auBout();
        return;
      }
      enCours = true;
      window.scrollTo({ top: cible, behavior: mouvementReduit() ? "auto" : "smooth" });
      // Fin du glissement : `scrollend` si le navigateur le connaît, sinon un délai.
      if (avecScrollend) window.addEventListener("scrollend", terminer, { once: true });
      else setTimeout(terminer, 900);
    };

    const pause = () => document.documentElement.classList.contains("sans-defilement");

    const molette = (e: WheelEvent) => {
      if (pause() || e.ctrlKey || Math.abs(e.deltaY) < Math.abs(e.deltaX)) return;
      const sens = e.deltaY > 0 ? 1 : -1;
      if (!enCours && lectureLibre(sens)) return;
      // Récit de la couverture plus long que son cadre : il défile chez lui.
      const cadre = (e.target as HTMLElement | null)?.closest<HTMLElement>("[data-recit-couverture][data-montre] [data-defile]");
      if (cadre && (sens > 0 ? cadre.scrollTop + cadre.clientHeight < cadre.scrollHeight - 1 : cadre.scrollTop > 0)) return;
      e.preventDefault();
      const maintenant = performance.now();
      const nouveauGeste = !enCours && maintenant - dernierCran > calme;
      dernierCran = maintenant;
      if (nouveauGeste) aller(sens);
    };

    const touches: Record<string, 1 | -1> = { ArrowDown: 1, PageDown: 1, " ": 1, ArrowUp: -1, PageUp: -1 };
    const clavier = (e: KeyboardEvent) => {
      const sens = touches[e.key];
      const cible = e.target as HTMLElement | null;
      if (!sens || pause() || e.altKey || e.ctrlKey || e.metaKey) return;
      if (cible?.closest("input, textarea, select, [contenteditable]")) return;
      const s = e.key === " " && e.shiftKey ? -1 : sens;
      if (lectureLibre(s)) return;
      e.preventDefault();
      if (!enCours) aller(s);
    };

    window.addEventListener("wheel", molette, { passive: false });
    window.addEventListener("keydown", clavier);
    return () => {
      window.removeEventListener("wheel", molette);
      window.removeEventListener("keydown", clavier);
      window.removeEventListener("scrollend", terminer);
    };
  }, [racine, actif, haut, auBout]);
}
