import { useRef } from "react";
import { Link } from "react-router";
import type { VoyageResume } from "../api/types";
import { useVolEntrant } from "../hooks/useVolEntrant";
import { useNavigationPage } from "../layout/contexte";
import { chemins } from "../lib/chemins";
import { periode, pluriel } from "../lib/dates";
import { volVoyage } from "../lib/mouvement";
import { variablesPalette } from "../lib/palette";
import { idVoyage } from "../lib/transitions";
import Photo from "./Photo";
import styles from "./CarteVoyage.module.css";

/**
 * Carte d'un voyage sur l'accueil, teintée par la palette du voyage. Même
 * transitionId que l'en-tête du voyage : au retour, l'en-tête revient s'y poser.
 */
export default function CarteVoyage({ voyage, priorite }: { voyage: VoyageResume; priorite?: boolean }) {
  const visuel = useRef<HTMLDivElement>(null);
  const nav = useNavigationPage();
  useVolEntrant(
    idVoyage(voyage.slug),
    () => visuel.current,
    () => (nav.genre === "voyage" && nav.sens === -1 ? { transition: volVoyage(-1) } : null),
  );

  return (
    <Link to={chemins.voyage(voyage.slug)} className={styles.carte} style={variablesPalette(voyage.palette)}>
      <div ref={visuel} className={styles.visuel} data-transition-id={idVoyage(voyage.slug)}>
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
        <span className={styles.filet} aria-hidden />
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
