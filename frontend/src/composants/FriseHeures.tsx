import { useEffect, useLayoutEffect, useRef, useState, type CSSProperties, type RefObject } from "react";
import { mouvementReduit } from "../hooks/useMouvementReduit";
import { libelleHeure } from "../lib/dates";
import { deplacementFrise } from "../lib/mouvement";
import styles from "./GaleriePhotos.module.css";

/**
 * Frise des heures (variantes plein écran, ordinateur) : à gauche de l'écran,
 * toutes les heures de la journée de haut en bas ; celle des photos affichées
 * est mise en valeur (repère qui glisse jusqu'à elle, libellé plein). Un clic
 * sur une heure fait glisser jusqu'à ses premières photos. Cachée tant que
 * la journée n'est pas arrivée sous la barre du jour (couverture, titre).
 *
 * L'heure en cours est celle du moment qui croise le milieu de l'écran (un
 * seul IntersectionObserver, aucun calcul au défilement). Le repère est
 * déplacé par element.animate (transform) ; les libellés changent d'opacité
 * (transition CSS, durée des tokens).
 *
 * Teinte : le repère et l'heure en cours prennent la couleur vive de la page
 * à l'écran (`data-couleur`, API `couleur_vive`) ; page terne = accent du jour.
 */
export default function FriseHeures({
  racine,
  heures,
  haut,
}: {
  racine: RefObject<HTMLElement | null>;
  /** Heure de chaque moment, dans l'ordre de la page (index = rang du moment). */
  heures: (number | null)[];
  /** Hauteur de la barre du jour (px) : décalage des points d'arrivée. */
  haut: number;
}) {
  const [courant, setCourant] = useState(0);
  const [visible, setVisible] = useState(false);
  const [teinte, setTeinte] = useState<string | null>(null);
  const liste = useRef<HTMLOListElement>(null);
  const repere = useRef<HTMLSpanElement>(null);
  const position = useRef<number | null>(null);

  useEffect(() => {
    const conteneur = racine.current;
    if (!conteneur) return;
    const sections = [...conteneur.querySelectorAll<HTMLElement>("section[data-heure]")];
    const observateur = new IntersectionObserver(
      (entrees) => {
        const croise = entrees.find((e) => e.isIntersecting);
        if (croise) setCourant(sections.indexOf(croise.target as HTMLElement));
      },
      // Ligne de lecture : le milieu de l'écran.
      { root: document, rootMargin: "-50% 0px -49% 0px" },
    );
    sections.forEach((s) => observateur.observe(s));
    // Couleur de la page qui croise la même ligne de lecture.
    const pages = new IntersectionObserver(
      (entrees) => {
        const croise = entrees.find((e) => e.isIntersecting);
        if (croise) setTeinte((croise.target as HTMLElement).dataset.couleur ?? null);
      },
      { root: document, rootMargin: "-50% 0px -49% 0px" },
    );
    conteneur.querySelectorAll<HTMLElement>("[data-ancre]").forEach((p) => pages.observe(p));
    // Visible quand la journée occupe la ligne juste sous la barre du jour.
    const ligne = new IntersectionObserver(([e]) => setVisible(e.isIntersecting), {
      root: document,
      rootMargin: `-${haut}px 0px -${Math.max(window.innerHeight - haut - 2, 0)}px 0px`,
    });
    ligne.observe(conteneur);
    return () => {
      observateur.disconnect();
      pages.disconnect();
      ligne.disconnect();
    };
  }, [racine, heures, haut]);

  // Le repère glisse jusqu'au libellé de l'heure en cours.
  useLayoutEffect(() => {
    const item = liste.current?.children[courant] as HTMLElement | undefined;
    const el = repere.current;
    if (!item || !el) return;
    const cible = item.offsetTop + item.offsetHeight / 2;
    const depart = position.current;
    position.current = cible;
    el.style.transform = `translate(0px, ${cible}px)`;
    if (depart !== null && depart !== cible) {
      const a = deplacementFrise(depart, cible, mouvementReduit());
      el.animate(a.images, a.options);
    }
  }, [courant, heures]);

  const aller = (rang: number) => {
    const section = racine.current?.querySelectorAll<HTMLElement>("section[data-heure]")[rang];
    const premier = section?.querySelector<HTMLElement>("[data-ancre]") ?? section;
    if (!premier) return;
    const y = premier.getBoundingClientRect().top + window.scrollY - haut;
    window.scrollTo({ top: y, behavior: mouvementReduit() ? "auto" : "smooth" });
  };

  return (
    <nav
      className={styles.frise}
      aria-label="Heures de la journée"
      data-visible={visible ? "" : undefined}
      data-teinte={teinte ? "" : undefined}
      style={teinte ? ({ "--couleur-frise": teinte } as CSSProperties) : undefined}
    >
      <span className={styles.friseFil} aria-hidden />
      <span ref={repere} className={styles.friseRepere} aria-hidden />
      <ol ref={liste} className={styles.friseListe}>
        {heures.map((h, i) => (
          <li key={i}>
            <button
              type="button"
              className={styles.friseHeure}
              data-courant={i === courant ? "" : undefined}
              aria-current={i === courant ? "time" : undefined}
              onClick={() => aller(i)}
            >
              {libelleHeure(h)}
            </button>
          </li>
        ))}
      </ol>
    </nav>
  );
}
