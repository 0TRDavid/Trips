import { useEffect, useLayoutEffect, useRef, useState, type RefObject } from "react";
import { mouvementReduit } from "../hooks/useMouvementReduit";
import { libelleHeure } from "../lib/dates";
import { roulementHeure, type Sens } from "../lib/mouvement";
import ProgressionJour from "./ProgressionJour";
import styles from "./GaleriePhotos.module.css";

type Etat = { index: number; heure: number | null; precedente: number | null | undefined; sens: Sens };

/**
 * Variante « bandeau » de l'intitulé collant : un seul bandeau en haut de la
 * galerie, qui affiche l'heure du moment en cours et la progression de la
 * journée. Le moment en cours est celui qui croise une ligne fine près du
 * haut de l'écran (IntersectionObserver, aucun calcul au défilement). Au
 * changement d'heure, l'ancienne s'en va et la nouvelle arrive, dans le sens
 * du défilement (element.animate, joué par le navigateur).
 *
 * Les intitulés des moments restent dans la page (titres pour les lecteurs
 * d'écran) ; le bandeau est décoratif (aria-hidden).
 */
export default function BandeauHeure({ racine, bornes }: { racine: RefObject<HTMLElement | null>; bornes: [number, number] }) {
  const [etat, setEtat] = useState<Etat>({ index: 0, heure: bornes[0], precedente: undefined, sens: 1 });
  const entrant = useRef<HTMLSpanElement>(null);
  const sortant = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    const conteneur = racine.current;
    if (!conteneur) return;
    const sections = [...conteneur.querySelectorAll<HTMLElement>("section[data-heure]")];
    const observateur = new IntersectionObserver(
      (entrees) => {
        const croise = entrees.find((e) => e.isIntersecting);
        if (!croise) return;
        const index = sections.indexOf(croise.target as HTMLElement);
        const brut = (croise.target as HTMLElement).dataset.heure;
        const heure = brut ? Number(brut) : null;
        setEtat((e) =>
          e.index === index ? e : { index, heure, precedente: e.heure, sens: index > e.index ? 1 : -1 },
        );
      },
      // Ligne de lecture : une bande de 1 % de la hauteur, à 10 % du haut.
      { rootMargin: "-10% 0px -89% 0px" },
    );
    sections.forEach((s) => observateur.observe(s));
    return () => observateur.disconnect();
  }, [racine]);

  useLayoutEffect(() => {
    if (etat.precedente === undefined) return;
    const r = roulementHeure(etat.sens, mouvementReduit());
    entrant.current?.animate(r.entree.images, r.entree.options);
    sortant.current?.animate(r.sortie.images, r.sortie.options);
  }, [etat]);

  return (
    <div className={`${styles.heure} ${styles.bandeau}`} aria-hidden="true">
      <span className={styles.libelles}>
        <span key={`e${etat.index}`} ref={entrant} className={styles.libelle}>
          {libelleHeure(etat.heure)}
        </span>
        {etat.precedente !== undefined && (
          <span key={`s${etat.index}`} ref={sortant} className={`${styles.libelle} ${styles.sortant}`}>
            {libelleHeure(etat.precedente)}
          </span>
        )}
      </span>
      <ProgressionJour racine={racine} fin={bornes[1]} />
    </div>
  );
}
