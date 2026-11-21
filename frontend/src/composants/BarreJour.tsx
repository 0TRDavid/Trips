import { useEffect, useRef, useState, type RefObject } from "react";
import { Link } from "react-router";
import type { JourDetail, PhotoJour } from "../api/types";
import { useMouvementReduit } from "../hooks/useMouvementReduit";
import { chemins } from "../lib/chemins";
import { dateLongue } from "../lib/dates";
import { barreJour } from "../lib/mouvement";
import Photo from "./Photo";
import styles from "./EnteteJour.module.css";

/**
 * Barre du jour : quand la date et le titre vont passer sous le haut de
 * l'écran, ils deviennent un en-tête compact, fixé en haut, sur la photo de
 * couverture (voile clair ou sombre, comme l'ouverture), avec le retour vers
 * le voyage à droite. Elle repart quand le titre revient.
 *
 * Un seul IntersectionObserver sur le bloc des titres (aucun calcul au
 * défilement) ; apparition et départ joués par le navigateur (element.animate).
 * La barre est décorative pour les lecteurs d'écran (le titre reste le h1 de
 * la page) mais son lien de retour est utilisable au clavier quand elle est là.
 */
export default function BarreJour({
  jour,
  couverture,
  titres,
}: {
  jour: JourDetail;
  couverture: PhotoJour;
  titres: RefObject<HTMLElement | null>;
}) {
  const barre = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);
  const reduit = useMouvementReduit();
  const premier = useRef(true);

  useEffect(() => {
    const cible = titres.current;
    const el = barre.current;
    if (!cible || !el) return;
    const hauteur = el.offsetHeight;
    const observateur = new IntersectionObserver(
      ([e]) => setVisible(!e.isIntersecting && e.boundingClientRect.top < hauteur),
      // Le titre « disparaît » quand il passe sous la barre.
      // root: document = la fenêtre de CETTE page, même dans une iframe (labo).
      { root: document, rootMargin: `-${hauteur}px 0px 0px 0px` },
    );
    observateur.observe(cible);
    return () => observateur.disconnect();
  }, [titres]);

  useEffect(() => {
    if (premier.current) {
      premier.current = false;
      return;
    }
    const a = barreJour(visible, reduit);
    barre.current?.animate(a.images, a.options);
  }, [visible, reduit]);

  return (
    <div ref={barre} className={styles.barre} data-visible={visible ? "" : undefined} inert={!visible || undefined} aria-hidden={!visible || undefined}>
      <div className={styles.barreFond} aria-hidden>
        <Photo photo={couverture} mode="couvrir" sizes="100vw" alt="" />
      </div>
      <p className={styles.barreTitre}>
        <span className={styles.barreDate}>{dateLongue(jour.date)}</span>
        <span className={styles.barreNom}>{jour.titre || "Sans titre"}</span>
      </p>
      <Link to={chemins.voyage(jour.voyage.slug)} className={styles.barreRetour}>
        <span aria-hidden>←</span> {jour.voyage.titre}
      </Link>
    </div>
  );
}
