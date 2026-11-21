import { useMouvementReduit } from "../hooks/useMouvementReduit";
import { useReglages } from "../hooks/useReglages";
import styles from "./FondPage.module.css";

/**
 * Fond d'une page : trois halos pastel aux couleurs du voyage ou du jour
 * (`--halo-1..3`, calculés par le serveur assez clairs pour que tout texte y
 * reste AA), posés sur le papier teinté, et qui s'estompent vers le bas.
 * Purement décoratif : sous le contenu (z-index -1 dans le cadre de page).
 *
 * Variantes (labo) : A fixes, B qui dérivent lentement (transform seulement,
 * arrêtées en mouvement réduit), C avec un grain de papier.
 */
export default function FondPage() {
  const variante = useReglages().variantes.fond;
  const reduit = useMouvementReduit();
  return (
    <div className={styles.fond} data-variante={variante} data-reduit={reduit || undefined} aria-hidden>
      <span className={`${styles.halo} ${styles.h1}`} />
      <span className={`${styles.halo} ${styles.h2}`} />
      <span className={`${styles.halo} ${styles.h3}`} />
      {variante === "C" && <span className={styles.grain} />}
    </div>
  );
}
