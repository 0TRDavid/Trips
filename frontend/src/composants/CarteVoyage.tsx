import { Link } from "react-router";
import type { VoyageResume } from "../api/types";
import { chemins } from "../lib/chemins";
import { periode, pluriel } from "../lib/dates";
import { idVoyage } from "../lib/transitions";
import Photo from "./Photo";
import styles from "./CarteVoyage.module.css";

/** Carte d'un voyage sur l'accueil. Même transitionId que l'en-tête du voyage. */
export default function CarteVoyage({ voyage, priorite }: { voyage: VoyageResume; priorite?: boolean }) {
  return (
    <Link to={chemins.voyage(voyage.slug)} className={styles.carte}>
      <div className={styles.visuel} data-transition-id={idVoyage(voyage.slug)}>
        {voyage.couverture ? (
          <Photo
            photo={voyage.couverture}
            mode="couvrir"
            sizes="(min-width: 1100px) 33vw, (min-width: 700px) 50vw, 100vw"
            priorite={priorite}
            alt=""
          />
        ) : (
          <div className={styles.vide} />
        )}
      </div>
      <div className={styles.texte}>
        <h2 className={styles.titre}>{voyage.titre}</h2>
        <p className={styles.meta}>
          {periode(voyage.date_debut, voyage.date_fin)}
          <span aria-hidden> · </span>
          {pluriel(voyage.nb_jours, "jour")}, {pluriel(voyage.nb_photos, "photo")}
        </p>
      </div>
    </Link>
  );
}
