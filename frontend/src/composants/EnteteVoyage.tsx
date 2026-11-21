import { useRef } from "react";
import type { VoyageDetail } from "../api/types";
import { useVolEntrant } from "../hooks/useVolEntrant";
import { useNavigationPage } from "../layout/contexte";
import { periode, pluriel } from "../lib/dates";
import { volEnTete } from "../lib/mouvement";
import { idVoyage } from "../lib/transitions";
import Photo from "./Photo";
import styles from "./EnteteVoyage.module.css";

/**
 * Grande couverture + titre. Même transitionId que la carte de l'accueil :
 * en venant de l'accueil, la carte « vole » jusqu'ici et devient l'en-tête.
 */
export default function EnteteVoyage({ voyage }: { voyage: VoyageDetail }) {
  const visuel = useRef<HTMLDivElement>(null);
  const nav = useNavigationPage();
  useVolEntrant(
    idVoyage(voyage.slug),
    () => visuel.current,
    () =>
      nav.genre === "voyage" && nav.sens === 1 ? { transition: volEnTete(1) } : null,
  );

  return (
    <header className={styles.entete}>
      <div ref={visuel} className={styles.visuel} data-transition-id={idVoyage(voyage.slug)}>
        {voyage.couverture && (
          <Photo photo={voyage.couverture} mode="couvrir" sizes="100vw" priorite alt="" />
        )}
        <div className={styles.voile} />
        <div className={styles.texte}>
          <h1 className={styles.titre}>{voyage.titre}</h1>
          <p className={styles.meta}>
            {periode(voyage.date_debut, voyage.date_fin)}
            <span aria-hidden> · </span>
            {pluriel(voyage.nb_jours, "jour")}, {pluriel(voyage.nb_photos, "photo")}
          </p>
        </div>
      </div>
      <div className={styles.filet} aria-hidden />
    </header>
  );
}
