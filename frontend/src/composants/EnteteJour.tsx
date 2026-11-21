import { useRef } from "react";
import { Link } from "react-router";
import type { JourDetail } from "../api/types";
import { useVolEntrant } from "../hooks/useVolEntrant";
import { useNavigationPage } from "../layout/contexte";
import { chemins } from "../lib/chemins";
import { dateLongue, pluriel } from "../lib/dates";
import { volEnTete } from "../lib/mouvement";
import { idJour } from "../lib/transitions";
import Photo from "./Photo";
import styles from "./EnteteJour.module.css";

/**
 * En-tête d'un jour : couverture (premier favori du jour, sinon sa première
 * photo, comme la vignette de la timeline), puis date et titre. En venant de
 * la page du voyage, la vignette du jour « vole » jusqu'ici et devient la
 * couverture ; au retour, elle regagne la timeline.
 */
export default function EnteteJour({ jour }: { jour: JourDetail }) {
  const visuel = useRef<HTMLDivElement>(null);
  const nav = useNavigationPage();
  const couverture = jour.photos.find((p) => p.favori) ?? jour.photos[0];
  const id = idJour(jour.voyage.slug, jour.date);
  useVolEntrant(
    id,
    () => visuel.current,
    () => (nav.genre === "ouvrirJour" && nav.sens === 1 ? { transition: volEnTete(1) } : null),
  );

  return (
    <header className={styles.entete}>
      <Link to={chemins.voyage(jour.voyage.slug)} className={styles.retour}>
        <span aria-hidden>←</span> {jour.voyage.titre}
      </Link>
      {couverture && (
        <>
          <div ref={visuel} className={styles.visuel} data-transition-id={id}>
            <Photo photo={couverture} mode="couvrir" sizes="100vw" priorite alt="" />
          </div>
          <div className={styles.filet} aria-hidden />
        </>
      )}
      <p className={styles.date}>{dateLongue(jour.date)}</p>
      <h1 className={styles.titre}>{jour.titre || "Sans titre"}</h1>
      <p className={styles.meta}>
        {[jour.lieu, pluriel(jour.photos.length, "photo")].filter(Boolean).join(" · ")}
      </p>
    </header>
  );
}
