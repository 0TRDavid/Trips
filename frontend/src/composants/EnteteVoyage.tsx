import type { VoyageDetail } from "../api/types";
import { periode, pluriel } from "../lib/dates";
import { idVoyage } from "../lib/transitions";
import Photo from "./Photo";
import styles from "./EnteteVoyage.module.css";

/** Grande couverture + titre. Même transitionId que la carte de l'accueil. */
export default function EnteteVoyage({ voyage }: { voyage: VoyageDetail }) {
  return (
    <header className={styles.entete}>
      <div className={styles.visuel} data-transition-id={idVoyage(voyage.slug)}>
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
    </header>
  );
}
