import styles from "./FondPage.module.css";

/**
 * Fond d'une page : trois halos pastel aux couleurs du voyage ou du jour
 * (`--halo-1..3`, calculés par le serveur assez clairs pour que tout texte y
 * reste AA), posés sur le papier teinté, et qui s'estompent vers le bas.
 * Purement décoratif et immobile : sous le contenu (z-index -1 dans le cadre
 * de page). À retravailler lors d'une passe ultérieure.
 */
export default function FondPage() {
  return (
    <div className={styles.fond} aria-hidden>
      <span className={`${styles.halo} ${styles.h1}`} />
      <span className={`${styles.halo} ${styles.h2}`} />
      <span className={`${styles.halo} ${styles.h3}`} />
    </div>
  );
}
