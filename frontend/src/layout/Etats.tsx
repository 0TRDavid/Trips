import { Link } from "react-router";
import { Introuvable } from "../api/client";
import IntrouvablePage from "../pages/IntrouvablePage";
import styles from "./Etats.module.css";

/** Chargement : on réserve de la place sans afficher de spinner qui clignote. */
export function EtatChargement({ libelle = "Chargement…" }: { libelle?: string }) {
  return (
    <div className={styles.chargement} role="status" aria-live="polite">
      <span className="visuellement-cache">{libelle}</span>
    </div>
  );
}

/** Erreur d'une requête : 404 → page introuvable ; sinon message + réessayer. */
export function EtatErreur({ erreur, reessayer }: { erreur: unknown; reessayer: () => void }) {
  if (erreur instanceof Introuvable) return <IntrouvablePage />;
  return (
    <div className={styles.erreur} role="alert">
      <h1>Impossible de charger la page</h1>
      <p>{erreur instanceof Error ? erreur.message : String(erreur)}</p>
      <div className={styles.actions}>
        <button type="button" className={styles.bouton} onClick={reessayer}>
          Réessayer
        </button>
        <Link to="/">Retour à l’accueil</Link>
      </div>
    </div>
  );
}
