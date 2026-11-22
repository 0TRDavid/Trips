import { useEffect, type RefObject } from "react";
import { animate, scroll } from "motion";

type Decalage = "start start" | "end start" | "end end" | "start end";

/**
 * Anime `element` en fonction du défilement de la page, entre deux positions
 * de `cible` (offset Motion). Motion branche l'animation sur une ViewTimeline
 * native quand le navigateur la connaît : c'est alors le compositeur qui la
 * joue, sans aucun JavaScript à chaque image. Sinon, Motion mesure une fois
 * par image pour toutes les animations liées au défilement.
 *
 * N'utiliser qu'avec transform et opacity (règle du mouvement, lib/mouvement.ts).
 */
export function useAuDefilement(
  element: RefObject<HTMLElement | null>,
  cible: RefObject<HTMLElement | null>,
  images: Record<string, string[] | number[]> | null,
  decalage: [Decalage, Decalage],
) {
  const cle = images ? JSON.stringify(images) : "";
  useEffect(() => {
    const el = element.current;
    const target = cible.current;
    if (!el || !target || !images) return;
    const animation = animate(el, images, { duration: 1, ease: "linear" });
    const arreter = scroll(animation, { target, offset: decalage });
    return () => {
      arreter();
      animation.stop();
      el.style.removeProperty("transform");
      el.style.removeProperty("opacity");
    };
    // `images` est comparé par sa valeur (cle).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [element, cible, cle, decalage[0], decalage[1]]);
}
